# run.py
import os
import sys
import subprocess
from pathlib import Path

# ==================== ASCII BANNER ====================
BANNER = r"""
   Ⓜ ⓣ ⑤ ⊖ Ⓙ Ⓞ Ⓤ Ⓡ Ⓝ Ⓐ Ⓛ

"""

print(BANNER)

BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
REQUIREMENTS = BASE_DIR / "requirements.txt"

# ==================== HELPERS ====================
def run(cmd):
    subprocess.check_call(cmd, shell=False)

def venv_python():
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"

# ==================== VENV CHECK ====================
if not VENV_DIR.exists():
    print("[+] No virtual environment found. Creating venv...")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])
else:
    print("[✓] Virtual environment found.")

PYTHON = venv_python()

# ==================== PIP UPGRADE ====================
print("[+] Upgrading pip...")
run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"])

# ==================== INSTALL REQUIREMENTS ====================
if REQUIREMENTS.exists():
    print("[+] Installing requirements...")
    run([str(PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
else:
    print("[!] requirements.txt not found — skipping.")

# ==================== ENV SETUP ====================
os.environ.setdefault("PYTHONPATH", str(BASE_DIR))

# ==================== RUN UVICORN ====================
print("[🚀] Starting MT5 Journal API...\n")

run([
    str(PYTHON),
    "-m", "uvicorn",
    "app.main:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--reload",
    "--log-level", "info"
])
