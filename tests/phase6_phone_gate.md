# Phase 6 Android phone gate

Measured on 2026-10-16 with Android device A069 (Android 16) and the isolated
`com.safespace.safespace_mobile.phase6` debug package. The app connected to an
isolated SafeSpace SQLite API through ADB USB port forwarding. The normal
installed SafeSpace package and database were not changed.

The rule was typed and confirmed on the phone: “Notify when a person is
visible.” The server stored version 2 as `SUPPORTED` with readback “Alert when
a tracked person is visible.” `scripts/phase6_phone_replay.py` replayed the
actual YOLO/ByteTrack Observation fixture from `TestVideos/v001_converted 3.avi`
at its original five processed frames per second, selecting stable person
track 1. Each run emitted one event after the 1.5-second hold. Repeating each
submission with the same event ID created no duplicate. A clip attached as a
later change played on the phone; clip updates did not post a second alert.

Android notification post times were read from `dumpsys notification` and
matched to the event episode start timestamps. Seconds:

| Event sequence | Episode start to phone post |
| --- | ---: |
| 3 | 1.714 |
| 4 | 1.874 |
| 12 | 1.668 |
| 14 | 1.668 |
| 16 | 1.664 |

For these five repeated fixture runs, p50 was 1.668 s and p95 (linear
interpolation) was 1.842 s. All were below the 3-second foreground target.
This measures the full default hold plus delivery, not camera capture or
real-world detection accuracy. The sample is small and reuses the same clip.

Reconnect recovery: the test package was disabled while event change 10 and
clip change 11 were committed. After re-enabling it, the saved cursor fetched
both changes in order. Android logged change 10 as a new rule alert and change
11 as an update; the recovered clip played in event details.

Direct Wi-Fi was not verified. The phone (`10.12.253.129`) and PC
(`10.12.253.133`) were on the same /16 subnet, but `curl` from the phone to
the isolated API on port 8003 timed out. The measured delivery path used USB
port forwarding. The first untraced replay appeared in the phone event list;
notification timing for that initial probe could not be verified.
