#!/usr/bin/env python3
"""
Genie OS v6 — System Diagnostic & Health Verification Utility
Run this script to test all core subsystems: Mic, Vosk Wake Word, Backend HTTP & WebSocket Auth.
"""
import sys
import os
import asyncio
import json
import time

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n{CYAN}{BOLD}=== {title} ==={RESET}")

def print_result(name, passed, detail=""):
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    msg = f" {detail}" if detail else ""
    print(f" {status} {BOLD}{name}{RESET}{msg}")

async def run_diagnostics():
    print(f"\n{BOLD}{CYAN}Genie OS v6 System Diagnostic Tool{RESET}")
    print("=" * 50)
    
    overall_pass = True

    # 1. Check Python Venv
    print_header("1. Environment & Path")
    print(f" Python Executable: {sys.executable}")
    print(f" Working Directory: {os.getcwd()}")

    # 2. Check Microphone Access
    print_header("2. Microphone Hardware Check")
    mic_ok = False
    mic_detail = ""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d.get('max_input_channels', 0) > 0]
        if input_devs:
            mic_ok = True
            mic_detail = f"Found {len(input_devs)} input device(s) via sounddevice ({input_devs[0]['name']})"
        else:
            mic_detail = "No input audio devices found"
    except Exception as e:
        mic_detail = f"sounddevice error: {e}"
    
    print_result("Microphone Hardware", mic_ok, mic_detail)
    if not mic_ok: overall_pass = False

    # 3. Check Vosk Model
    print_header("3. Vosk Wake-Word Model Check")
    vosk_ok = False
    vosk_detail = ""
    try:
        from vosk import Model
        local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend", "vosk-model-small-en-us-0.15"))
        if os.path.exists(local_path):
            model = Model(model_path=local_path)
            vosk_ok = True
            vosk_detail = f"Loaded model from {local_path}"
        else:
            vosk_detail = f"Local model path not found: {local_path}"
    except Exception as e:
        vosk_detail = f"Vosk load error: {e}"
    
    print_result("Vosk Model", vosk_ok, vosk_detail)
    if not vosk_ok: overall_pass = False

    # 4. Check Backend HTTP Health
    print_header("4. Backend HTTP Server Health Check")
    http_ok = False
    http_detail = ""
    try:
        import urllib.request
        req = urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=3)
        if req.status == 200:
            data = json.loads(req.read().decode('utf-8'))
            http_ok = data.get("status") == "ok" and data.get("ready") == True
            http_detail = f"HTTP 200 OK — service: {data.get('service')}, version: {data.get('version')}"
        else:
            http_detail = f"HTTP Status {req.status}"
    except Exception as e:
        http_detail = f"Backend not running or unreachable: {e}"

    print_result("HTTP /health Endpoint", http_ok, http_detail)
    if not http_ok: overall_pass = False

    # 5. Check WebSocket Authentication (PIN: 1234)
    print_header("5. WebSocket Authentication (PIN test)")
    ws_ok = False
    ws_detail = ""
    if http_ok:
        try:
            import websockets
            async with websockets.connect("ws://127.0.0.1:8765/ws", open_timeout=5) as ws:
                await ws.send(json.dumps({"type": "hello", "pin": "1234"}))
                resp_raw = await ws.recv()
                resp = json.loads(resp_raw)
                if resp.get("type") == "auth_ok":
                    ws_ok = True
                    ws_detail = f"Authenticated successfully (session_id: {resp.get('session_id')})"
                else:
                    ws_detail = f"Auth failed — server returned: {resp_raw}"
        except Exception as e:
            ws_detail = f"WebSocket error: {e}"
    else:
        ws_detail = "Skipped (Backend HTTP unavailable)"

    print_result("WebSocket Auth (PIN: 1234)", ws_ok, ws_detail)
    if not ws_ok: overall_pass = False

    # Summary
    print("\n" + "=" * 50)
    if overall_pass:
        print(f"{GREEN}{BOLD}ALL SYSTEMS OPERATIONAL! Genie OS v6 is ready.{RESET}\n")
    else:
        print(f"{YELLOW}{BOLD}DIAGNOSTIC NOTICE: Some checks require attention (see details above).{RESET}\n")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
