"""Small supervisor that keeps one rule worker process per active camera."""

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
LOGS = ROOT / "storage/logs"
RECORD = ROOT / "storage/worker-processes.json"


def main():
    api = os.getenv("SAFESPACE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    if not token:
        raise RuntimeError("INTERNAL_SERVICE_TOKEN is required")
    LOGS.mkdir(parents=True, exist_ok=True)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    workers = {}
    streams = {}
    try:
        with httpx.Client(timeout=10) as client:
            while not stopped.is_set():
                try:
                    response = client.get(api + "/api/v1/internal/cameras",
                                          headers={"Authorization": f"Bearer {token}"})
                    response.raise_for_status()
                    desired = {camera["id"] for camera in response.json()}
                except httpx.HTTPError:
                    stopped.wait(5)
                    continue
                for camera_id, process in list(workers.items()):
                    if camera_id not in desired or process.poll() is not None:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                        workers.pop(camera_id, None)
                        for stream in streams.pop(camera_id, ()):
                            stream.close()
                for camera_id in desired - workers.keys():
                    safe = re.sub(r"[^A-Za-z0-9_-]", "_", camera_id)
                    stdout = (LOGS / f"rules-{safe}.log").open("a", encoding="utf-8")
                    stderr = (LOGS / f"rules-{safe}.error.log").open("a", encoding="utf-8")
                    streams[camera_id] = (stdout, stderr)
                    workers[camera_id] = subprocess.Popen(
                        [sys.executable, "-m", "services.rules.worker", "--camera-id", camera_id],
                        cwd=ROOT, stdout=stdout, stderr=stderr,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                temp = RECORD.with_suffix(".tmp")
                temp.write_text(json.dumps({camera_id: process.pid for camera_id, process in workers.items()}), encoding="utf-8")
                temp.replace(RECORD)
                stopped.wait(5)
    finally:
        for process in workers.values():
            process.terminate()
        for process in workers.values():
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for pair in streams.values():
            for stream in pair:
                stream.close()
        RECORD.write_text("{}", encoding="utf-8")


if __name__ == "__main__":
    main()
