# Ollama Setup & VLM Service Guide

Ollama runs as a native system service on `127.0.0.1:11434`.

## 1. Installation
Install Ollama via official installer or package manager.

## 2. Pulling VLM Model
```bash
ollama pull qwen2.5-vl:7b
```

## 3. Verifying Endpoint
```bash
curl http://127.0.0.1:11434/api/tags
```
