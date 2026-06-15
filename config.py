import os
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------- Config ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HUGGINGFACE_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN", "")
FASHIONCLIP_MODEL = os.environ.get("FASHIONCLIP_MODEL", "patrickjohncyh/fashion-clip")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
GEMINI_FALLBACK_MODELS = os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.0-flash")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRIPE_SECRET_KEY=os.environ.get("STRIPE_SECRET_KEY")

UPLOADS_BUCKET = "uploads"
GARMENTS_BUCKET = "garments"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aura")


def configured_gemini_models() -> List[str]:
    models = [GEMINI_MODEL]
    models.extend(m.strip() for m in GEMINI_FALLBACK_MODELS.split(",") if m.strip())
    deduped = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_ANON_KEY)
