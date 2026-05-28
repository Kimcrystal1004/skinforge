# 환경변수, API 키 설정
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

SKIN_WIDTH = 64
SKIN_HEIGHT = 64