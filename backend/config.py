# backend/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
INDEX_DIR = DATA_DIR / "index"

# Create dirs on import
CACHE_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GOOGLE_CLIENT_SECRETS_FILE = Path(__file__).parent / "client_secret.json"
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "1R22isu0HXNka5aU3X9KYqDraW9esTeyW")

GROQ_MODEL = "llama-3.1-8b-instant"  # free tier, fast
TOP_K_PAGES = 8          # pages retrieved per query
MAX_PAGE_CHARS = 3000    # truncate very long pages
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
