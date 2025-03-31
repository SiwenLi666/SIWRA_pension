import os
from dotenv import load_dotenv
import logging
from datetime import datetime
load_dotenv()


# Project root (where "vectorstore" and "src" live)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


VECTORSTORE_DIR = os.path.join(BASE_DIR, "vectorstore")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
SUMMARY_JSON_PATH = os.path.join(MEMORY_DIR, "summary.json")

# === Environment Configuration ===

# Load OpenAI API key from environment variable or .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Vectorstore (FAISS) settings
VECTORSTORE_PATH = "data/vectorstore_index"

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# LLM model config
DEFAULT_MODEL = "gpt-4"
FAST_MODEL = "gpt-3.5-turbo"

# Directory for optional logs
LOG_DIR = "logs"

# Token cost config (used by cost tracker)
GPT4_PRICING = {
    "prompt_per_1k": 0.03,
    "completion_per_1k": 0.06,
}




def setup_logger(name: str = "siwra", level=logging.INFO) -> logging.Logger:
    """Sets up and returns a configured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Format for console and file logs
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Optional file handler
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(log_dir, f"log_{timestamp}.log")
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
