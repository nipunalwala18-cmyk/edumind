#!/usr/bin/env python3
"""
colab_tunnel.py
---------------
Google Colab / Kaggle Notebook setup script for "The Notebook Tunnel" method using ngrok.

Copy this script's contents and run it in a single cell of your Google Colab
or Kaggle Notebook (with T4 GPU accelerator enabled) to borrow a free GPU,
spin up the Ollama server, pull Qwen2.5:7b (~8B parameters), and expose the server
port 11434 via a secure ngrok Tunnel.
"""

import os
import subprocess
import time
import sys

def run_cmd(cmd: str, abort_on_error: bool = True) -> bool:
    """
    Utility to run a shell command and print its output immediately.
    Returns True on success, False on failure.
    If abort_on_error=True (default), raises SystemExit on non-zero exit code.
    """
    print(f"Executing: {cmd}")
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    for line in process.stdout:
        print(line, end="")
    process.wait()
    if process.returncode != 0:
        msg = f"Command failed with exit code {process.returncode}: {cmd}"
        print(f"\n[ERROR] {msg}")
        if abort_on_error:
            print("[ABORT] Cannot continue — fix the error above and re-run the cell.")
            raise SystemExit(1)
        return False
    return True

def setup_tunnel():
    print("======================================================================")
    print("             VIT AGENTIC AI - COLAB TUNNEL INFERENCE SETUP            ")
    print("======================================================================")
    
    # 1. Install system dependencies (zstd required by Ollama installer)
    print("\n[STEP 1/5] Installing system dependencies (zstd)...")
    run_cmd("apt-get update && apt-get install -y zstd")
    
    # 2. Install Ollama Linux binary
    print("\n[STEP 2/5] Installing Ollama...")
    run_cmd("curl -fsSL https://ollama.com/install.sh | sh")
    
    # 3. Run Ollama serve in the background
    print("\n[STEP 3/5] Starting Ollama service in the background...")
    ollama_log = open("ollama_server.log", "w")
    ollama_proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=ollama_log,
        stderr=ollama_log
    )
    time.sleep(5)  # Allow server to fully start

    # Sanity check — confirm Ollama is responding
    import urllib.request, urllib.error
    for attempt in range(6):
        try:
            urllib.request.urlopen("http://localhost:11434", timeout=3)
            print("  Ollama server is up and responding.")
            break
        except Exception:
            if attempt == 5:
                print("\n[ERROR] Ollama server did not start within 30 seconds. Check ollama_server.log.")
                ollama_proc.terminate()
                raise SystemExit(1)
            time.sleep(5)
    
    # 4. Pull Qwen2.5:7b
    print("\n[STEP 4/5] Pulling qwen2.5:7b model (this takes ~1-2 mins on T4)...")
    run_cmd("ollama pull qwen2.5:7b")
    
    # 5. Install pyngrok and configure ngrok tunnel
    print("\n[STEP 5/5] Establishing secure ngrok tunnel...")
    run_cmd("pip install -q pyngrok")
    
    from pyngrok import ngrok
    
    # Get ngrok token from environment, Colab secrets, .env file, or interactive prompt
    token = os.environ.get("NGROK_AUTHTOKEN")
    
    # Try Google Colab Secrets (userdata)
    if not token:
        try:
            from google.colab import userdata
            token = userdata.get("NGROK_AUTHTOKEN")
        except Exception:
            pass

    if not token:
        if os.path.exists(".env"):
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("NGROK_AUTHTOKEN="):
                        token = line.split("=", 1)[1].strip()
                        break
        if not token:
            print("\nAn ngrok Auth Token is required to host the tunnel.")
            print("Get one for free at: https://dashboard.ngrok.com/get-started/your-authtoken")
            try:
                token = input("Enter your NGROK_AUTHTOKEN: ").strip()
            except Exception:
                print("\n[ERROR] NGROK_AUTHTOKEN not found in environment and stdin is not interactive.")
                print("Please set the NGROK_AUTHTOKEN secret in your Google Colab notebook (left key icon) and re-run.")
                ollama_proc.terminate()
                return

    if token:
        ngrok.set_auth_token(token)
    else:
        print("\n[WARNING] Running without authtoken — may fail or be heavily rate-limited.")
    
    tunnel = None
    try:
        tunnel = ngrok.connect(11434, "http")
        print("\n" + "=" * 60)
        print(" SUCCESS: SECURE INFERENCE TUNNEL ACTIVE")
        print("-" * 60)
        print(" Copy the URL below into your local '.env' file:")
        print(f" OLLAMA_BASE_URL={tunnel.public_url}")
        print("\n (Keep this notebook tab open to maintain the tunnel!)")
        print("=" * 60 + "\n")
        
        # Keep alive until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nInterrupted — shutting down tunnel...")
    except Exception as e:
        print(f"\n[ERROR] Failed to establish ngrok tunnel: {e}")
    finally:
        if tunnel:
            try:
                ngrok.disconnect(tunnel.public_url)
            except Exception:
                pass
        ollama_proc.terminate()
        print("Cleanup complete.")

if __name__ == "__main__":
    setup_tunnel()
