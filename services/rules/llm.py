"""Only structured JSON and selected-image description leave this adapter."""

import base64
import json

import httpx


class LocalLLM:
    def __init__(self, base_url: str, model: str, timeout_s: float, num_gpu: int = 0, num_ctx: int | None = None,
                 think: bool | None = None):
        self.url = base_url.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout = timeout_s
        self.num_gpu = num_gpu
        self.num_ctx = num_ctx
        self.think = think        # None keeps the model's default; False is much faster but dropped clauses when compiling rules

    def _request(self, system: str, user: str, schema: dict, images: list[bytes] | None = None) -> dict:
        message = {"role": "user", "content": user}
        if images:
            message["images"] = [base64.b64encode(item).decode("ascii") for item in images]
        payload = {
            "model": self.model, "stream": False, "format": schema, "keep_alive": "30m", **({"think": self.think} if self.think is not None else {}),
            "options": {"temperature": 0, "num_gpu": self.num_gpu, **({"num_ctx": self.num_ctx} if self.num_ctx else {})},
            "messages": [{"role": "system", "content": system}, message],
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.url, json=payload)
            response.raise_for_status()
        return json.loads(response.json()["message"]["content"])

    def generate_json(self, system: str, user: str, json_schema: dict) -> dict:
        last = None
        for _ in range(2):
            try:
                return self._request(system, user, json_schema)
            except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                last = exc
        raise RuntimeError(f"LLM structured output unavailable: {last}")

    def describe(self, images: list[bytes], system: str, user: str, json_schema: dict) -> dict:
        if not 1 <= len(images) <= 6:
            raise ValueError("visual review needs 1 to 6 images")
        return self._request(system, user, json_schema, images)
