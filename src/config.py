import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

# OpenAI API配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.chatanywhere.tech")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

# SerpAPI配置
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# 图像API配置 #智普 flash v api
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "")

# 应用程序配置
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# 文件路径配置
BASE_DIR = Path(__file__).parent.parent
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
IMG_FOLDER = "static/frontend/img"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# 数据存储配置
DATA_PATH = Path("src/static/backend/output_data.json")
INDEX_PERSIST_DIR = Path("src/static/backend/storage")
CACHE_DIR = os.getenv("CACHE_DIR", os.path.join(BASE_DIR, "cache"))

# 模型配置
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cuda")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gpt-neo-2.7B")
LOCAL_MODEL_REF_PATH = os.getenv("LOCAL_MODEL_REF_PATH", "text_aigc/local_infer_ref")
LOCAL_MODEL_CACHE_DIR = os.getenv("LOCAL_MODEL_CACHE_DIR", "../cache")

# 查询配置
SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", "3"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# 性能配置
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# 其他配置
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
USE_OPENAI_API = os.getenv("USE_OPENAI_API", "True").lower() == "true"

# 默认配置字典（用于talk_with_data.py等）
CONFIG = {
    "data_path": DATA_PATH,
    "index_persist_dir": INDEX_PERSIST_DIR,
    "openai_api_key": OPENAI_API_KEY,
    "openai_api_base": OPENAI_BASE_URL,
    "model": OPENAI_MODEL,
    "temperature": OPENAI_TEMPERATURE,
    "chunk_size": CHUNK_SIZE,
    "similarity_top_k": SIMILARITY_TOP_K,
    "cache_dir": CACHE_DIR,
    "log_level": LOG_LEVEL,
    "max_workers": MAX_WORKERS,
    "request_timeout": REQUEST_TIMEOUT
}
