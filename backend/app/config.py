import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]

load_dotenv(REPO_ROOT / ".env")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()

_db_path = os.getenv("DB_PATH", "./data/market_sim.db")
DB_PATH = (BACKEND_DIR / _db_path).resolve() if not os.path.isabs(_db_path) else Path(_db_path)

FINNHUB_WS_URL = "wss://ws.finnhub.io"
FINNHUB_REST_URL = "https://finnhub.io/api/v1"
