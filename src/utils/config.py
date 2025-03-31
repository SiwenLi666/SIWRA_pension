import os
from dotenv import load_dotenv
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
