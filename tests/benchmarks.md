# Programmable rules: Phase 0 runtime benchmark

Measured at 2026-10-16T10:46:25.056200+00:00 on this machine. The bundled AVI is a functional probe, not night-footage accuracy evidence.

## Detector

```json
{
  "clip": "v001_converted 3.avi",
  "frames": 24,
  "rule_classes": [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush"
  ],
  "track_ids_seen": 12,
  "tracking_median_ms": 10.6,
  "threat_median_ms": 40.9,
  "combined_fps": 4.8,
  "steady_fps": 17.82,
  "meets_configured_fps": true,
  "threat_models": [
    "fire_smoke",
    "weapons"
  ],
  "threat_warnings": []
}
```

## Llm

```json
{
  "model": "gemma4:e2b",
  "images": 3,
  "elapsed_s": 92.31,
  "output": {
    "image_count": 3,
    "visible_evidence": "The three camera frames show an outdoor or semi-outdoor area, likely a bar or restaurant patio, with a paved walkway on the left and a tiled patio area on the right.",
    "uncertainty": "The specific identities of the people are unclear due to distance and motion. The exact nature of the gathering (e.g., a party, a casual social event) is inferred but not explicitly stated. The specific contents of the tables are not clearly discernible."
  }
}
```

## Gate

PASS
