import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BITEBUDDY_DATA_DIR", str(ROOT / "data")))
PROFILE_PATH = DATA_DIR / "profile.json"
LOG_PATH = DATA_DIR / "log.json"
FOODS_PATH = DATA_DIR / "foods.json"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "openai/gpt-4o-mini"
)
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)
