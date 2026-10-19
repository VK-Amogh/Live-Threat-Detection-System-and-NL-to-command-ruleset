"""MediaHub: SSF1 binary protocol, latest-only subscriber mailboxes, adaptive ladder, and overlay broadcast."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import os
import struct
import time
from typing import Any, Generic, TypeVar
import cv2
import numpy as np
from fastapi import WebSocket

from .. import database as db
from .. import settings
from .recorder import RECORDER_MANAGER, save_snapshot_bytes

T = TypeVar("T")

SSF1_MAGIC = b"SSF1"
SSF1_HEADER_STRUCT = struct.Struct(">4sBBHHIQ")  # 22 bytes: magic(4), flags(1), orientation(1), width(2), height(2), seq(4), captured_ms(8)

LADDER_PROFILES: dict[str, dict[str, int]] = {
    "normal": {"width": 1280, "height": 720, "fps": 12, "jpeg_quality": 72},
    "busy": {"width": 960, "height": 540, "fps": 8, "jpeg_quality": 65},
    "idle": {"width": 640, "height": 360, "fps": 5, "jpeg_quality": 60},
    "critical": {"width": 640, "height": 360, "fps": 3, "jpeg_quality": 55},
}


@dataclass
class FramePacket:
    camera_id: str
    seq: int
    captured_ms: int
    received_ts: float
    width: int
    height: int
    orientation: int
    flags: int
    jpeg_bytes: bytes
    wire: bytes = b""   # SSF1 header + JPEG, built once and sent unchanged to every viewer


def pack_ssf1_frame(
    jpeg_bytes: bytes,
    seq: int = 1,
    captured_ms: int | None = None,
    width: int = 640,
    height: int = 360,
    orientation: int = 0,
    flags: int = 0,
) -> bytes:
    if captured_ms is None:
        captured_ms = int(time.time() * 1000)
    header = SSF1_HEADER_STRUCT.pack(
        SSF1_MAGIC,
        flags & 0xFF,
        orientation & 0xFF,
        max(0, min(65535, int(width))),
        max(0, min(65535, int(height))),
        seq & 0xFFFFFFFF,
        int(captured_ms) & 0xFFFFFFFFFFFFFFFF,
    )
    return header + jpeg_bytes


def _crop_to_16_9(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    if w <= 0 or h <= 0:
        return img
    if abs(w * 9 - h * 16) <= 32:
        return img
    if w * 9 > h * 16:
        crop_w = ((h * 16) // 9) & ~1
        crop_h = h & ~1
    else:
        crop_w = w & ~1
        crop_h = ((w * 9) // 16) & ~1
    crop_w = max(2, min(w, crop_w))
    crop_h = max(2, min(h, crop_h))
    x0 = max(0, (w - crop_w) // 2)
    y0 = max(0, (h - crop_h) // 2)
    return img[y0 : y0 + crop_h, x0 : x0 + crop_w]


def parse_ssf1_frame(camera_id: str, payload: bytes, fallback_seq: int = 1) -> FramePacket:
    now_ts = time.time()
    if len(payload) > SSF1_HEADER_STRUCT.size and payload[:4] == SSF1_MAGIC:
        _, flags, orientation, width, height, seq, captured_ms = SSF1_HEADER_STRUCT.unpack_from(payload, 0)
        jpeg_bytes = payload[SSF1_HEADER_STRUCT.size :]
    else:
        flags = 0
        orientation = 0
        seq = fallback_seq
        captured_ms = int(now_ts * 1000)
        jpeg_bytes = payload
        width, height = 0, 0

    if not jpeg_bytes.startswith(b"\xff\xd8"):
        raise ValueError("Invalid JPEG payload inside frame packet")

    needs_crop = width == 0 or height == 0 or abs(int(width) * 9 - int(height) * 16) > 32
    if needs_crop and len(jpeg_bytes) > 4:
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            h0, w0 = img.shape[:2]
            if abs(w0 * 9 - h0 * 16) > 32:
                img = _crop_to_16_9(img)
                ok_enc, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok_enc:
                    jpeg_bytes = enc.tobytes()
            height, width = img.shape[:2]
        elif width == 0 or height == 0:
            width, height = 640, 360

    packet = FramePacket(
        camera_id=camera_id,
        seq=int(seq),
        captured_ms=int(captured_ms),
        received_ts=now_ts,
        width=int(width or 640),
        height=int(height or 360),
        orientation=int(orientation),
        flags=int(flags),
        jpeg_bytes=jpeg_bytes,
    )
    packet.wire = pack_ssf1_frame(jpeg_bytes, seq=packet.seq, captured_ms=packet.captured_ms, width=packet.width,
                                  height=packet.height, orientation=packet.orientation, flags=packet.flags)
    return packet


class LatestOnlyMailbox(Generic[T]):
    """Single-slot mailbox: slow consumers always receive the newest frame without blocking fast consumers."""

    def __init__(self, name: str = "subscriber"):
        self.name = name
        self._item: T | None = None
        self._has_item = False
        self._event = asyncio.Event()
        self.delivered_count = 0
        self.replaced_count = 0
        self.closed = False

    def put(self, item: T) -> None:
        if self.closed:
            return
        if self._has_item:
            self.replaced_count += 1
        self._item = item
        self._has_item = True
        self._event.set()

    async def get(self, timeout: float | None = None) -> T | None:
        if self.closed:
            return None
        if not self._has_item:
            if timeout is not None:
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None
            else:
                await self._event.wait()
        if self.closed or not self._has_item:
            return None
        item = self._item
        self._item = None
        self._has_item = False
        self._event.clear()
        self.delivered_count += 1
        return item

    def close(self) -> None:
        self.closed = True
        self._event.set()


@dataclass
class CameraChannel:
    camera_id: str
    seq_counter: int = 0
    latest_frame: FramePacket | None = None
    latest_overlay: dict[str, Any] = field(default_factory=lambda: {"type": "overlay", "tracks": [], "zones": {}, "lines": {}})
    recent_frames: deque[tuple[float, bytes]] = field(default_factory=lambda: deque(maxlen=90))
    frame_timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=30))
    viewers: set[LatestOnlyMailbox[FramePacket | dict[str, Any]]] = field(default_factory=set)
    publisher_ws: WebSocket | None = None
    device_id: str | None = None
    profile: str = "normal"
    stealth_mode: bool = False
    torch_enabled: bool = False
    lens_facing: str = "back"
    battery_pct: int | None = None
    charging: bool | None = None
    temp_c: float | None = None
    wifi_rssi: int | None = None
    dropped_frames: int = 0
    last_disk_preview_ts: float = 0.0
    last_tracks: list[dict[str, Any]] = field(default_factory=list)       # newest rule-tracker boxes
    last_observation: dict[str, Any] = field(default_factory=dict)
    latest_threats: dict[str, Any] = field(default_factory=dict)          # newest weapon/violence result
    analysis_times: deque[float] = field(default_factory=lambda: deque(maxlen=30))
    geometry_cache: tuple[float, dict[str, Any]] = (0.0, {})
    pending_full_snapshots: list[asyncio.Future[dict[str, Any]]] = field(default_factory=list)

    @property
    def fps(self) -> float:
        now_ts = time.time()
        while self.frame_timestamps and (now_ts - self.frame_timestamps[0]) > 10.0:
            self.frame_timestamps.popleft()
        if len(self.frame_timestamps) < 2:
            return 1.0 if self.frame_timestamps else 0.0
        span = max(0.2, self.frame_timestamps[-1] - self.frame_timestamps[0])
        return round((len(self.frame_timestamps) - 1) / span, 2)

    @property
    def is_online(self) -> bool:
        if self.publisher_ws is not None:
            return True
        if self.latest_frame and (time.time() - self.latest_frame.received_ts) < 12.0:
            return True
        return False

    @property
    def viewer_count(self) -> int:
        return len(self.viewers)

    def select_adaptive_profile(self, queue_depth: int = 0) -> dict[str, Any]:
        if (self.temp_c and self.temp_c >= 43.0) or (
            self.battery_pct is not None and self.battery_pct < 15 and not self.charging
        ):
            self.profile = "critical"
        elif queue_depth >= 2:
            self.profile = "busy"
        elif self.viewer_count == 0 and self._active_rules_count() == 0:
            self.profile = "idle"
        else:
            self.profile = "normal"
        target = LADDER_PROFILES.get(self.profile, LADDER_PROFILES["normal"])
        return {"profile": self.profile, **target}

    def _active_rules_count(self) -> int:
        try:
            return sum(1 for r in db.list_rules(self.camera_id) if r.get("status") == "active")
        except Exception:
            return 0


class MediaHub:
    def __init__(self):
        self._channels: dict[str, CameraChannel] = {}

    def channel(self, camera_id: str) -> CameraChannel:
        ch = self._channels.get(camera_id)
        if ch is None:
            ch = CameraChannel(camera_id=camera_id)
            self._channels[camera_id] = ch
        return ch

    def subscribe(self, camera_id: str, name: str = "viewer") -> LatestOnlyMailbox[FramePacket | dict[str, Any]]:
        ch = self.channel(camera_id)
        mb: LatestOnlyMailbox[FramePacket | dict[str, Any]] = LatestOnlyMailbox(name=name)
        ch.viewers.add(mb)
        if ch.latest_frame is not None:
            mb.put(ch.latest_frame)
        return mb

    def unsubscribe(self, camera_id: str, mb: LatestOnlyMailbox[Any]) -> None:
        ch = self._channels.get(camera_id)
        if ch:
            ch.viewers.discard(mb)
        mb.close()

    async def publish_frame(
        self,
        camera_id: str,
        raw_payload: bytes,
        forward_to_session: bool = True,
    ) -> dict[str, Any]:
        ch = self.channel(camera_id)
        ch.seq_counter += 1
        packet = parse_ssf1_frame(camera_id, raw_payload, fallback_seq=ch.seq_counter)
        ch.latest_frame = packet
        ch.recent_frames.append((packet.received_ts, packet.jpeg_bytes))
        ch.frame_timestamps.append(packet.received_ts)

        # Resolve any pending full-resolution snapshot futures if flag 0x01 is set (or any fresh frame)
        if ch.pending_full_snapshots and (packet.flags & 0x01 or len(ch.pending_full_snapshots) > 0):
            snap_meta = save_snapshot_bytes(
                camera_id,
                packet.jpeg_bytes,
                kind="full" if (packet.flags & 0x01) else "stream",
                ts=packet.received_ts,
            )
            while ch.pending_full_snapshots:
                fut = ch.pending_full_snapshots.pop(0)
                if not fut.done():
                    fut.set_result(snap_meta)

        # Fan-out to all viewer mailboxes (latest-only, zero head-of-line blocking)
        for mb in list(ch.viewers):
            if mb.closed:
                ch.viewers.discard(mb)
            else:
                mb.put(packet)

        # Write preview JPEG to disk (throttled to <= 4 writes/sec)
        if (packet.received_ts - ch.last_disk_preview_ts) >= 0.25:
            ch.last_disk_preview_ts = packet.received_ts
            try:
                base = settings.active_storage()
                preview = base / "previews" / f"{camera_id}.jpg"
                preview.parent.mkdir(parents=True, exist_ok=True)
                tmp = preview.with_suffix(".tmp")
                tmp.write_bytes(packet.jpeg_bytes)
                os.replace(tmp, preview)
                live_media = base / "media" / f"{camera_id}_live.jpg"
                live_media.write_bytes(packet.jpeg_bytes)
            except Exception:
                pass

        # Append to 10-second segmented MP4 recorder in background thread
        try:
            await asyncio.to_thread(
                RECORDER_MANAGER.append_frame,
                camera_id,
                packet.jpeg_bytes,
                packet.received_ts,
                packet.width,
                packet.height,
            )
        except Exception:
            pass

        # Ensure camera object in DB is marked online
        cam = db.get("camera", camera_id)
        if cam:
            if not cam.get("is_online") or cam.get("status") != "LIVE":
                cam["is_online"] = True
                cam["status"] = "LIVE"
                cam["width"] = packet.width
                cam["height"] = packet.height
                db.put("camera", cam)

        if ch.device_id:
            db.update_device_telemetry(
                ch.device_id,
                {
                    "fps": ch.fps,
                    "status": "streaming",
                    "last_seen": packet.received_ts,
                    "capture_profile": ch.profile,
                },
            )

        queue_depth = 0
        if forward_to_session:
            from .. import mobile_camera

            session = mobile_camera.SESSIONS.get(camera_id)
            if session is None:
                session = mobile_camera.PhoneCameraSession(camera_id)
                mobile_camera.SESSIONS[camera_id] = session
            session.start()
            await session.submit(packet.jpeg_bytes)
            queue_depth = session.queue.qsize()

        ladder = ch.select_adaptive_profile(queue_depth=queue_depth)
        return {
            "type": "ack",
            "seq": packet.seq,
            "received_ts": round(packet.received_ts, 3),
            "fps": ch.fps,
            "viewer_count": ch.viewer_count,
            "server_queue_depth": queue_depth,
            **ladder,
        }

    def _geometry(self, ch: CameraChannel) -> dict[str, Any]:
        cached_at, geometry = ch.geometry_cache
        if time.time() - cached_at > 5.0:
            geometry = db.get_geometry(ch.camera_id)[0] or {}
            ch.geometry_cache = (time.time(), geometry)
        return geometry

    def _push_overlay(self, ch: CameraChannel, triggered_rules: list[str] | None = None) -> None:
        """One overlay message: rule-tracker boxes plus fresh weapon/violence boxes, with the stats viewers display."""
        now_ts = time.time()
        threats = ch.latest_threats if now_ts - ch.latest_threats.get("ts", 0.0) < 2.5 else {}
        geometry = self._geometry(ch)
        frame = ch.latest_frame
        meta = ch.last_observation
        ch.analysis_times.append(now_ts)
        span = ch.analysis_times[-1] - ch.analysis_times[0] if len(ch.analysis_times) > 1 else 0.0
        boxes = list(ch.last_tracks) + list(threats.get("boxes", []))
        overlay = {
            "type": "overlay",
            "camera_id": ch.camera_id,
            "seq": meta.get("frame_id", ch.seq_counter),
            "frame_id": meta.get("frame_id", ch.seq_counter),
            "ts": meta.get("ts", now_ts),
            "captured_at_ms": int(meta.get("ts", now_ts) * 1000),
            "width": frame.width if frame else 0,
            "height": frame.height if frame else 0,
            "tracks": list(ch.last_tracks),
            "boxes": boxes,
            "triggered_rules": triggered_rules or [],
            "zones": geometry.get("zones", {}),
            "lines": geometry.get("lines", {}),
            "threat": {"detected": bool(threats.get("boxes")) or (threats.get("violence") or 0) > 0,
                       "violence": threats.get("violence"), "inference_ms": threats.get("inference_ms")},
            "fps_in": ch.fps,
            "fps_inference": round((len(ch.analysis_times) - 1) / span, 1) if span > 0 else 0.0,
            # how long after the frame arrived this analysis finished: the lag between video and its boxes
            "latency_ms": int(max(0.0, now_ts - meta.get("ts", now_ts)) * 1000),
            "profile": ch.profile,
            "viewer_count": ch.viewer_count,
        }
        ch.latest_overlay = overlay
        for mb in list(ch.viewers):
            if not mb.closed:
                mb.put(overlay)

    def publish_overlay(self, camera_id: str, observation: Any, triggered_rules: list[str] | None = None) -> None:
        ch = self.channel(camera_id)
        ch.last_tracks = [
            {
                "track_id": getattr(tr, "track_id", 0),
                "class_name": getattr(tr, "cls", None) or getattr(tr, "class_name", "object"),
                "confidence": round(float(getattr(tr, "conf", getattr(tr, "confidence", 0.0))), 3),
                "bbox": [round(float(v), 1) for v in getattr(tr, "bbox", (0, 0, 0, 0))],
                "kind": "object",
            }
            for tr in (getattr(observation, "tracks", []) or [])
        ]
        ch.last_observation = {"frame_id": getattr(observation, "frame_id", ch.seq_counter), "ts": getattr(observation, "ts", time.time())}
        self._push_overlay(ch, triggered_rules)

    def publish_threats(self, camera_id: str, result: Any) -> None:
        """Weapon / violence detections from the threat pipeline, shown on the live view as soon as they are known."""
        ch = self.channel(camera_id)
        boxes, violence = [], None
        for d in getattr(result, "detections", []) or []:
            if d.model == "violence":
                violence = max(violence or 0.0, float(d.confidence))
                continue
            boxes.append({"track_id": None, "class_name": d.class_name, "confidence": round(float(d.confidence), 3),
                          "bbox": [round(float(v), 1) for v in d.box], "kind": "threat", "model": d.model})
        ch.latest_threats = {"ts": time.time(), "boxes": boxes, "violence": violence, "inference_ms": round(float(getattr(result, "inference_ms", 0.0)), 1)}
        self._push_overlay(ch)

    async def send_device_command(self, camera_id: str, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        ch = self.channel(camera_id)
        params = params or {}
        if action == "set_profile" and "profile" in params:
            ch.profile = str(params["profile"])
        elif action == "toggle_torch":
            ch.torch_enabled = bool(params.get("enabled", not ch.torch_enabled))
        elif action == "switch_lens":
            ch.lens_facing = str(params.get("lens", "front" if ch.lens_facing == "back" else "back"))
        elif action == "enter_stealth":
            ch.stealth_mode = True
        elif action == "exit_stealth":
            ch.stealth_mode = False

        if ch.device_id:
            db.update_device_telemetry(
                ch.device_id,
                {
                    "capture_profile": ch.profile,
                    "torch_enabled": ch.torch_enabled,
                    "lens_facing": ch.lens_facing,
                    "stealth_mode": ch.stealth_mode,
                },
            )

        msg = {"type": "command", "action": action, "params": params, "ts": time.time()}
        delivered = False
        if ch.publisher_ws is not None:
            try:
                await ch.publisher_ws.send_json(msg)
                delivered = True
            except Exception:
                delivered = False
        return {"ok": True, "delivered": delivered, "camera_id": camera_id, "command": msg}

    async def request_snapshot(self, camera_id: str, kind: str = "stream") -> dict[str, Any] | None:
        ch = self.channel(camera_id)
        if kind == "full" and ch.publisher_ws is not None:
            loop = asyncio.get_running_loop()
            fut: asyncio.Future[dict[str, Any]] = loop.create_future()
            ch.pending_full_snapshots.append(fut)
            try:
                await ch.publisher_ws.send_json({"type": "command", "action": "take_full_snapshot", "ts": time.time()})
                return await asyncio.wait_for(fut, timeout=2.5)
            except Exception:
                if fut in ch.pending_full_snapshots:
                    ch.pending_full_snapshots.remove(fut)

        # Fallback to latest stream frame in memory or preview on disk
        if ch.latest_frame is not None:
            return save_snapshot_bytes(camera_id, ch.latest_frame.jpeg_bytes, kind=kind, ts=time.time())
        preview_path = settings.active_storage() / "previews" / f"{camera_id}.jpg"
        if preview_path.exists():
            return save_snapshot_bytes(camera_id, preview_path.read_bytes(), kind=kind, ts=time.time())
        return None


HUB = MediaHub()
