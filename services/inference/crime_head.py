"""Crime-type head: pooled DINOv2 frame features + VideoMAE clip features -> one of 12 DCSASS crime types or 'none'.

Trained by scripts/crime/train.py on the same frozen encoders the violence stack uses (vision_features.py, motion.py), so the
features of one clip can be shared between the violence stack and this head. Evaluation caveats live in docs/ml-pipeline.md.
"""
import numpy as np
import torch
from torch import nn

# Arson (visible fire) is deliberately absent: fire/smoke detection was removed and this head never saw an Arson clip.
TYPES = ['Abuse', 'Arrest', 'Assault', 'Burglary', 'Explosion', 'Fighting', 'RoadAccidents', 'Robbery', 'Shooting', 'Shoplifting', 'Stealing', 'Vandalism']
CLASSES = TYPES + ['none']
DINO_DIM = 1536
VMAE_DIM = 768 + 400
FEATURE_DIM = 2 * DINO_DIM + VMAE_DIM


def pool_features(dino, vmae):
    """dino: (N,T,1536) per-frame DINOv2 features, vmae: (N,1168) -> (N, 4240) float32 = [mean over T | std over T | VideoMAE]."""
    dino = np.asarray(dino, np.float32)
    return np.concatenate([dino.mean(1), dino.std(1), np.asarray(vmae, np.float32)], axis=1)


class CrimeHead(nn.Module):
    """Block-wise LayerNorm -> (optional hidden layer) -> class logits. hidden=0 is a plain linear (softmax regression) head."""

    def __init__(self, n_classes=len(CLASSES), hidden=256, dropout=0.5, blocks=(DINO_DIM, DINO_DIM, VMAE_DIM)):
        super().__init__()
        self.blocks = tuple(blocks)
        self.norms = nn.ModuleList([nn.LayerNorm(d) for d in self.blocks])
        dim = sum(self.blocks)
        self.net = nn.Sequential(nn.Dropout(dropout), nn.Linear(dim, n_classes)) if not hidden else \
            nn.Sequential(nn.Dropout(dropout), nn.Linear(dim, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, n_classes))

    def forward(self, x):
        parts = torch.split(x, self.blocks, dim=1)
        return self.net(torch.cat([norm(p) for norm, p in zip(self.norms, parts)], dim=1))


def softmax(logits, temperature=1.0):
    z = np.asarray(logits, np.float64) / temperature
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def surfaced_type(prob, sidecar):
    """Crime type an operator may be shown for one clip's class probabilities (len(CLASSES)), or None.

    Only types listed in sidecar['supported'] (those that met the pre-registered bar on blind parents) with a calibrated threshold can fire; every other
    type, `none`, and anything uncalibrated never raises. An empty/missing `supported` list therefore switches the head off.
    """
    supported = set(sidecar.get('supported') or [])
    best = max(range(len(TYPES)), key=lambda i: prob[i])
    name = TYPES[best]
    tau = (sidecar.get('thresholds') or {}).get(name)
    if name in supported and tau is not None and prob[best] >= tau:
        return name, float(prob[best])
    return None
