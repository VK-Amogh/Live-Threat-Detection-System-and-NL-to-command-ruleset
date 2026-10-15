# 00 — Specification Analysis and Assumptions Register

## System Overview
SafeSpace is an on-premises, local-first intelligent video surveillance and threat detection system. It monitors camera streams (webcam, uploaded video files, and future RTSP), detects physical threats (weapons, altercations) using an optimized YOLO detector, verifies candidates using a local Vision-Language Model (VLM via Ollama), and provides real-time alerting to a React web dashboard and Android Flutter mobile application.

## Assumptions Register
- **A1: Hardware Target**: Single PC equipped with dedicated NVIDIA GPU (>= 6GB VRAM) running native Python worker and Ollama.
- **A2: Sampling Rate**: 5 FPS frame sampling at 640x640 resolution in FP16 precision.
- **A3: Network Topology**: Dedicated or shared local area network (LAN / Wi-Fi) with DHCP reservation for the host PC.
- **A4: Locality Guarantee**: Zero reliance on external cloud services for core detection, verification, and alert delivery.
