import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent

# Load only the backend-local .env file to avoid probing outside the repo.
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not GROQ_API_KEY or not SERPAPI_KEY:
    raise ValueError("GROQ_API_KEY or SERPAPI_KEY not found in environment variables.")
client = Groq(api_key=GROQ_API_KEY)