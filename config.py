import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-reasoner"
    DEEPSEEK_FALLBACK_MODEL = "deepseek-chat"

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
    OCR_TIMEOUT = 30
    DEEPSEEK_TIMEOUT = 20
    DEEPSEEK_RETRIES = 2
