import os
from pathlib import Path


def _read_api_key() -> str:
    key_file = Path(__file__).parent / "api-key.txt"
    if not key_file.exists():
        return ""
    for line in key_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("sk-"):
            return line
    return ""


class Config:
    DEEPSEEK_API_KEY = _read_api_key()
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat"
    DEEPSEEK_FALLBACK_MODEL = "deepseek-reasoner"

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "outputs")
    MINERU_CACHE = "mineru_cache"

    PAPER_SIZES = {
        "A4": (210, 297),
        "B5": (176, 250),
        "Letter": (215.9, 279.4),
    }
    DEFAULT_PAPER_SIZE = "A4"
    DEFAULT_COMPRESS_QUALITY = 80
    DEFAULT_MARGIN_MM = 10
    MAX_IMAGE_LONG_SIDE = 1600
    OCR_TIMEOUT = 120
    DEEPSEEK_TIMEOUT = 20
    DEEPSEEK_RETRIES = 2
