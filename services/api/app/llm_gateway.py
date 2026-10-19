"""Single-model Priority LLM Gateway (P0: Alert summary, P1: Interactive chat/compile, P2: Background review)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import heapq
import os
import time
from typing import Any
import httpx

from . import settings

P0_ALERT_SUMMARY = 0
P1_INTERACTIVE = 1
P2_BACKGROUND = 2


def ollama_runtime() -> dict[str, int]:
    """Shared load-time options so Ollama never unloads/reloads the model between callers."""
    return {
        "num_ctx": 6144,
        "num_gpu": int(os.getenv("OLLAMA_NUM_GPU", "99")),
    }


class PriorityLLMGateway:
    """Serializes local LLM calls with strict priority ordering (P0 > P1 > P2)."""

    def __init__(self):
        self._busy = False
        self._seq = 0
        self._waiters: list[tuple[int, int, asyncio.Future[None]]] = []
        self.stats = {
            "p0_completed": 0,
            "p1_completed": 0,
            "p2_completed": 0,
            "active_priority": None,
            "last_latency_ms": 0.0,
        }

    @property
    def queue_depth(self) -> int:
        return len(self._waiters) + (1 if self._busy else 0)

    @asynccontextmanager
    async def slot(self, priority: int = P1_INTERACTIVE):
        loop = asyncio.get_running_loop()
        if not self._busy and not self._waiters:
            self._busy = True
        else:
            fut: asyncio.Future[None] = loop.create_future()
            self._seq += 1
            heapq.heappush(self._waiters, (int(priority), self._seq, fut))
            try:
                await fut
            except asyncio.CancelledError:
                self._waiters = [w for w in self._waiters if w[2] is not fut]
                heapq.heapify(self._waiters)
                raise

        t0 = time.perf_counter()
        self.stats["active_priority"] = priority
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.stats["last_latency_ms"] = round(elapsed_ms, 1)
            if priority == P0_ALERT_SUMMARY:
                self.stats["p0_completed"] += 1
            elif priority == P1_INTERACTIVE:
                self.stats["p1_completed"] += 1
            else:
                self.stats["p2_completed"] += 1
            self.stats["active_priority"] = None

            while self._waiters:
                _, _, next_fut = heapq.heappop(self._waiters)
                if not next_fut.done():
                    next_fut.set_result(None)
                    break
            else:
                self._busy = False

    async def describe(
        self,
        images_b64: list[str],
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        priority: int = P2_BACKGROUND,
        model: str | None = None,
        timeout_s: float = 45.0,
    ) -> str:
        chosen_model = model or os.getenv("OLLAMA_MODEL", "gemma4:e2b")
        body: dict[str, Any] = {
            "model": chosen_model,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {**ollama_runtime(), "temperature": 0.1, "num_predict": 512},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt, "images": images_b64},
            ],
        }
        if json_schema is not None:
            body["format"] = json_schema

        async with self.slot(priority=priority):
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(f"{settings.OLLAMA_URL}/api/chat", json=body)
                resp.raise_for_status()
                payload = resp.json()
                return payload.get("message", {}).get("content", "")


GATEWAY = PriorityLLMGateway()
