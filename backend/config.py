"""Configuration management for AppCrawler backend."""

import os
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Android SDK ────────────────────────────────────────────────────
_default_sdk = os.path.expanduser("~/Library/Android/sdk")
ANDROID_HOME = os.getenv("ANDROID_HOME", os.getenv("ANDROID_SDK_ROOT", _default_sdk if os.path.isdir(_default_sdk) else ""))
ADB_PATH = os.getenv("ADB_PATH", os.path.join(ANDROID_HOME, "platform-tools", "adb") if ANDROID_HOME else "adb")
EMULATOR_PATH = os.getenv("EMULATOR_PATH", os.path.join(ANDROID_HOME, "emulator", "emulator") if ANDROID_HOME else "emulator")
AVDMANAGER_PATH = os.getenv("AVDMANAGER_PATH", os.path.join(ANDROID_HOME, "cmdline-tools", "latest", "bin", "avdmanager") if ANDROID_HOME else "avdmanager")

# ── Appium ─────────────────────────────────────────────────────────
APPIUM_HOST = os.getenv("APPIUM_HOST", "http://127.0.0.1:4723")

# ── AI / Gemini ────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Crawl defaults ─────────────────────────────────────────────────
DEFAULT_MAX_STEPS = int(os.getenv("DEFAULT_MAX_STEPS", "40"))
SCREENSHOT_DELAY = float(os.getenv("SCREENSHOT_DELAY", "1.5"))  # seconds between steps
HASH_SIMILARITY_THRESHOLD = int(os.getenv("HASH_SIMILARITY_THRESHOLD", "8"))  # pHash hamming distance
