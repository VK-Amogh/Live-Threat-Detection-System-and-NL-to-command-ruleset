"""Temporal head over cached DINOv2 frame features; also scores single still frames."""
import torch
from torch import nn

from vision_features import FEATURE_DIM


class TemporalHead(nn.Module):
    """T frame features -> violence logit.  Works for any 1 <= T <= max_len (T=1 scores a still image)."""

    def __init__(self, dim=FEATURE_DIM, width=384, layers=2, heads=6, max_len=16, dropout=0.2):
        super().__init__()
        self.norm_in = nn.LayerNorm(dim)
        self.proj = nn.Sequential(nn.Dropout(dropout), nn.Linear(dim, width))
        self.pos = nn.Parameter(torch.zeros(1, max_len, width))
        nn.init.trunc_normal_(self.pos, std=0.02)
        block = nn.TransformerEncoderLayer(width, heads, width * 2, dropout, batch_first=True, norm_first=True, activation='gelu')
        self.encoder = nn.TransformerEncoder(block, layers)
        self.norm = nn.LayerNorm(width)
        self.clip_head = nn.Linear(width, 1)
        self.frame_head = nn.Linear(width, 1)  # per-frame auxiliary classifier

    def forward(self, x):  # x: B,T,D
        z = self.proj(self.norm_in(x))
        frame_logits = self.frame_head(z).squeeze(-1)  # B,T
        z = self.encoder(z + self.pos[:, : x.shape[1]])
        clip_logit = self.clip_head(self.norm(z).mean(1)).squeeze(-1)
        return clip_logit, frame_logits
