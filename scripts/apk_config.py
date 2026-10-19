#!/usr/bin/env python
"""Write the build-time configuration the APK is born with, from the laptop's own .env and live network state.

    python scripts/apk_config.py            -> apps/mobile/.dart_defines.json  (+ the CA the phone's video player trusts)

What gets baked in (so a phone needs nothing typed):
  SERVER_URLS   every address the laptop currently has on an allowed network (hotspot, ...), plus APK_EXTRA_URLS from .env
  SERVER_ID     which laptop this build belongs to
  TLS_PINS      SHA-256 pin of the laptop's TLS key (the key is stable even when the laptop's address changes)
  CAMERA_ENROLLMENT_CODE  shared secret: proves the laptop to the app and the app to discovery
  ACCOUNTS      the built-in admin tiles
The CA certificate is copied into the Android resources so Android's own TLS stack (video playback) trusts the laptop.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "contracts" / "src", ROOT / "services" / "api"):
    sys.path.insert(0, str(entry))

from app import network_policy, settings, tls  # noqa: E402

HOTSPOT_FALLBACK = "http://10.11.229.33:8000"   # the Nothing Phone hotspot address the laptop is given


def main() -> int:
    policy = network_policy.policy()
    network_policy.set_listeners(settings.HTTP_PORT, settings.HTTPS_PORT if settings.TLS_ENABLED else None, [])
    urls: list[str] = []
    for route in network_policy.advertised_routes():
        if route["route"] in ("trusted_lan", "ibus_lan", "tailnet", "relay", "configured") and route["url"] not in urls:
            urls.append(route["url"])
    for extra in [u.strip() for u in os.getenv("APK_EXTRA_URLS", "").split(",") if u.strip()]:
        if extra not in urls:
            urls.append(extra)
    if HOTSPOT_FALLBACK not in urls:
        urls.append(HOTSPOT_FALLBACK)

    pins: list[str] = []
    if settings.TLS_ENABLED:
        material = tls.ensure_all()
        pins = [material.pin]
        target = ROOT / "apps" / "mobile" / "android" / "app" / "src" / "main" / "res" / "raw" / "safespace_ca.pem"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(material.ca, target)
        print(f"CA copied to {target.relative_to(ROOT)}")

    accounts = ",".join(f"{email}|{name}" for email, _, name in __import__("app.security", fromlist=["x"])._parse_seed_accounts())
    defines = {
        "SERVER_URLS": ",".join(urls),
        "SERVER_ID": settings.SERVER_ID,
        "TLS_PINS": ",".join(pins),
        "CAMERA_ENROLLMENT_CODE": settings.CAMERA_ENROLLMENT_CODE,
        "DISCOVERY_PORT": str(settings.DISCOVERY_PORT),
        "ACCOUNTS": accounts,
        "DEMO_PASSWORD": os.getenv("DEMO_PASSWORD", "admin123"),
        "DEMO_AUTOFILL": "true" if settings.DEMO_AUTOFILL_PASSWORD else "false",
    }
    out = ROOT / "apps" / "mobile" / ".dart_defines.json"
    out.write_text(json.dumps(defines, indent=2), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}  (network mode: {policy.mode})")
    print("  server urls :", defines["SERVER_URLS"])
    print("  tls pin     :", defines["TLS_PINS"] or "(none: TLS disabled)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
