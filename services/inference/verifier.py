"""Second-stage detection verifier: DINOv2 crop embedding + small MLP.

YOLO proposes boxes with high recall; this stage re-scores each proposed box from its pixels (with context) using the
same frozen DINOv2 encoder the violence recogniser uses. It was trained on real detections: true positives vs the
detector's own false alarms mined from thousands of ordinary frames (violins, bottles, shadows, tables, ice...).
The crop geometry below is shared by training and runtime so they cannot drift apart.
"""
import cv2
import numpy as np
import torch
from torch import nn

from vision_features import FEATURE_DIM

CLASSES = ['fire', 'smoke', 'gun', 'knife']
SIDE = 224
EXPAND = 1.35       # context around the box
MIN_SIDE = 48       # px in the source image


def crop_square(image_rgb: np.ndarray, box, expand=EXPAND, shift=(0.0, 0.0)):
    """Square crop around `box` (x1,y1,x2,y2) with context, edge-padded, resized to SIDE x SIDE."""
    h, w = image_rgb.shape[:2]
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    side = max(max(box[2] - box[0], box[3] - box[1]) * expand, MIN_SIDE)
    cx, cy = cx + shift[0] * side, cy + shift[1] * side
    x1, y1 = int(round(cx - side / 2)), int(round(cy - side / 2))
    x2, y2 = x1 + int(round(side)), y1 + int(round(side))
    pad = max(0, -x1, -y1, x2 - w, y2 - h)
    if pad:
        image_rgb = cv2.copyMakeBorder(image_rgb, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
        x1, y1, x2, y2 = x1 + pad, y1 + pad, x2 + pad, y2 + pad
    crop = image_rgb[y1:y2, x1:x2]
    return cv2.resize(crop, (SIDE, SIDE), interpolation=cv2.INTER_AREA if crop.shape[0] > SIDE else cv2.INTER_LINEAR)


class VerifierMLP(nn.Module):
    """Input = crop embedding (with context) + whole-frame embedding + claimed class. Output = logit(real instance)."""

    def __init__(self, dim=FEATURE_DIM, hidden=512, dropout=0.3):
        super().__init__()
        width = 2 * dim + len(CLASSES)
        self.net = nn.Sequential(nn.LayerNorm(width), nn.Dropout(dropout), nn.Linear(width, hidden), nn.GELU(),
                                 nn.Dropout(dropout), nn.Linear(hidden, 128), nn.GELU(), nn.Linear(128, 1))

    def forward(self, crop_feature, frame_feature, class_index):
        onehot = nn.functional.one_hot(class_index, len(CLASSES)).to(crop_feature.dtype)
        return self.net(torch.cat([crop_feature, frame_feature, onehot], dim=1)).squeeze(-1)


@torch.inference_mode()
def score_detections(encoder, mlp, image_rgb: np.ndarray, detections, frame_feature):
    """detections: list of (class_name, box); frame_feature: DINOv2 feature of the whole frame (1536,) already on device.
    Returns the probability that each detection is a real instance of its class."""
    if not detections:
        return []
    from vision_features import encode_frames
    crops = np.stack([crop_square(image_rgb, box) for _, box in detections])
    features = encode_frames(encoder, torch.from_numpy(crops))
    classes = torch.tensor([CLASSES.index(c) for c, _ in detections], device=features.device)
    return torch.sigmoid(mlp(features, frame_feature.expand(len(detections), -1), classes)).cpu().tolist()
