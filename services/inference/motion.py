"""Motion-aware violence scorer: VideoMAE-base (Kinetics-400) clip features + small trained head.

Complements the frame-wise DINOv2 head: it sees how people move over ~3-4 s rather than what a single frame looks like.
Used only for video/live streams that have buffered >= MIN_FRAMES frames; still images never reach it.
"""
from collections import deque

import cv2
import numpy as np
import torch
from torch import nn

MODEL_ID = 'MCG-NJU/videomae-base-finetuned-kinetics'
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
CLIP_FRAMES = 16
MIN_FRAMES = 8
FEATURE_DIM = 768 + 400


class Head(nn.Module):
    def __init__(self, dim=FEATURE_DIM, hidden=256, dropout=0.4):
        super().__init__()
        self.net = nn.Sequential(nn.LayerNorm(dim), nn.Dropout(dropout), nn.Linear(dim, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, 1))

    def forward(self, x):
        return self.net(x).squeeze(-1)


def prep(frame_rgb: np.ndarray) -> np.ndarray:
    """Short side -> 224 then centre crop, identical to training (scripts/violence/extract_videomae.py)."""
    h, w = frame_rgb.shape[:2]
    scale = 224 / min(h, w)
    frame = cv2.resize(frame_rgb, (max(224, round(w * scale)), max(224, round(h * scale))), interpolation=cv2.INTER_AREA)
    h, w = frame.shape[:2]
    y, x = (h - 224) // 2, (w - 224) // 2
    return frame[y:y + 224, x:x + 224]


class MotionScorer:
    def __init__(self, head_path, device='cuda'):
        from transformers import VideoMAEForVideoClassification
        self.device = device
        self.model = VideoMAEForVideoClassification.from_pretrained(MODEL_ID, dtype=torch.float16).to(device).eval()
        self.head = Head().to(device).eval()
        self.head.load_state_dict(torch.load(head_path, map_location=device, weights_only=True))
        self.buffers = {}

    def forget(self, stream_id):
        self.buffers.pop(stream_id, None)

    def push(self, stream_id, frame_rgb: np.ndarray):
        self.buffers.setdefault(stream_id, deque(maxlen=CLIP_FRAMES)).append(prep(frame_rgb))

    @torch.inference_mode()
    def score(self, stream_id):
        """Probability of violence over the buffered window, or None until MIN_FRAMES frames have arrived."""
        frames = self.buffers.get(stream_id)
        if not frames or len(frames) < MIN_FRAMES:
            return None
        idx = np.linspace(0, len(frames) - 1, CLIP_FRAMES).round().astype(int)     # resample to 16 frames
        clip = np.stack([frames[i] for i in idx]).astype(np.float32) / 255.0
        x = torch.from_numpy(((clip - MEAN) / STD).transpose(0, 3, 1, 2).copy())[None].to(self.device).half()
        out = self.model(pixel_values=x, output_hidden_states=True)
        feature = torch.cat([out.hidden_states[-1].mean(1).float(), out.logits.float()], dim=1)
        return float(torch.sigmoid(self.head(feature))[0])
