"""Frozen DINOv2 frame encoder shared by violence training and runtime inference."""
import torch

MODEL_ID = 'facebook/dinov2-base'
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
FEATURE_DIM = 1536  # CLS (768) + mean patch token (768)


def load_encoder(device='cuda'):
    from transformers import AutoModel
    model = AutoModel.from_pretrained(MODEL_ID, torch_dtype=torch.float16 if device != 'cpu' else torch.float32)
    return model.to(device).eval()


@torch.inference_mode()
def encode_frames(model, frames_uint8, batch=64):
    """frames_uint8: N,H,W,3 RGB uint8 (H,W multiples of 14 after resize) -> N,1536 float32 on device."""
    device = next(model.parameters()).device
    dtype = next(model.parameters()).dtype
    mean = torch.tensor(MEAN, device=device, dtype=dtype).view(1, 3, 1, 1)
    std = torch.tensor(STD, device=device, dtype=dtype).view(1, 3, 1, 1)
    out = []
    for i in range(0, len(frames_uint8), batch):
        x = frames_uint8[i:i + batch].to(device).permute(0, 3, 1, 2).to(dtype) / 255.0
        x = (x - mean) / std
        h = model(pixel_values=x).last_hidden_state
        out.append(torch.cat([h[:, 0], h[:, 1:].mean(1)], dim=1).float())
    return torch.cat(out)
