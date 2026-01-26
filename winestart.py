# run.py
import os
import subprocess
from pathlib import Path

# ==================== ASCII BANNER ====================
BANNER = r"""
   Ⓜ ⓣ ⑤ ⊖ Ⓙ Ⓞ Ⓤ Ⓡ Ⓝ Ⓐ Ⓛ

"""

print(BANNER)

# ==================== PATHS ====================
# Base project directory (use Wine Z: mapping for Linux home)
BASE_DIR = Path(r"Z:\home\jesse\mt5-v2")
REQUIREMENTS = BASE_DIR / "requirements.txt"

# Windows Python inside Wine (change if different)
PYTHON = Path(r"C:\users\jesse\AppData\Local\Programs\Python\Python312\python.exe")

# ==================== HELPERS ====================
def run(cmd):
    """Run a subprocess and print the command"""
    print(f"[>] Running: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd, shell=False)
    except subprocess.CalledProcessError as e:
        print(f"[!] Command failed with code {e.returncode}")
        exit(e.returncode)

# ==================== PIP UPGRADE ====================
print("[+] Upgrading pip inside Wine Python...")
run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"])

# ==================== INSTALL REQUIREMENTS ====================
if REQUIREMENTS.exists():
    print("[+] Installing Python requirements inside Wine...")
    run([str(PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
else:
    print("[!] requirements.txt not found — skipping.")

# ==================== ENV SETUP ====================
os.environ.setdefault("PYTHONPATH", str(BASE_DIR))

# ==================== RUN UVICORN ====================
print("[🚀] Starting MT5 Journal API inside Wine...\n")
run([
    str(PYTHON),
    "-m", "uvicorn",
    "app.main:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--reload",
    "--log-level", "info"
])
