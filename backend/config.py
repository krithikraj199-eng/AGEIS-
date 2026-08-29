"""
AEGIS Ω — Global Configuration
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

# ─── Server ──────────────────────────────────────────────
HOST = os.getenv("AEGIS_HOST", "0.0.0.0")
PORT = int(os.getenv("AEGIS_PORT", "8000"))
DEBUG = os.getenv("AEGIS_DEBUG", "true").lower() == "true"

# ─── Database ────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./aegis_omega.db"
)

# ─── Google AI ───────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ─── Digital World ───────────────────────────────────────
INSTITUTION_NAME = "AEGIS Digital University"
SIMULATION_SPEED = float(os.getenv("SIMULATION_SPEED", "1.0"))  # 1.0 = real-time
EVENT_GENERATION_INTERVAL = float(os.getenv("EVENT_INTERVAL", "2.0"))  # seconds
METRICS_UPDATE_INTERVAL = float(os.getenv("METRICS_INTERVAL", "3.0"))  # seconds

# ─── Risk Thresholds ────────────────────────────────────
RISK_AUTO_EXECUTE = 30    # 0-30: auto execute
RISK_SUPERVISOR = 60      # 31-60: supervisor review
RISK_HUMAN = 80           # 61-80: human approval
RISK_BLOCK = 100          # 81-100: block

# ─── Agent Config ────────────────────────────────────────
MAX_REPLAN_ATTEMPTS = 3
VERIFICATION_TIMEOUT = 30  # seconds
AGENT_HEARTBEAT_INTERVAL = 10  # seconds
