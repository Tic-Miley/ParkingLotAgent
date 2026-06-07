import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "parking_lot.db"))

# Ensure data directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# Agent config
MAX_ITERATIONS = 8
SQL_TIMEOUT_SECONDS = 5
SQL_MAX_ROWS = 1000
TOKEN_WARNING_THRESHOLD = 80_000
