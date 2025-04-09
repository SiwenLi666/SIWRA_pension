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

# === Feature Flags ===
# Phase 1: Retrieval Improvements
USE_HYBRID_RETRIEVAL = True  # Enable hybrid BM25 + vector search
BM25_WEIGHT = 0.4  # Weight for BM25 results (1-BM25_WEIGHT for vector)
LOG_RETRIEVAL_METRICS = True  # Log retrieval performance metrics

# Phase 2: Document Processing Enhancements
ENHANCED_METADATA_EXTRACTION = True  # Extract acronyms and definitions
STRUCTURED_TRANSITIONAL_PROVISIONS = True  # Extract structured metadata for transitional rules

# Phase 3: Answer Generation Improvements
VERIFY_ANSWERS = True  # Verify answers to prevent empty referrals
STRUCTURED_ANSWER_TEMPLATES = True  # Use structured templates for different question types
ANSWER_POST_PROCESSING = True  # Post-process answers to ensure they include requested information
ENHANCED_COMPARISON_HANDLING = True  # Improve handling of comparison questions with specialized templates
CONFIDENCE_SCORING = True  # Add confidence scoring for generated answers

# Phase 4: User Experience and Feedback
USER_FEEDBACK_MECHANISM = True  # Simple feedback mechanism for answers
CONVERSATION_CONTEXT = True     # Conversation context management
PERFORMANCE_DASHBOARD = False   # Not implemented yet
QUESTION_CATEGORIZATION = False # Not implemented yet
FOLLOW_UP_SUGGESTIONS = True    # Follow-up question suggestions

# Phase 5: Domain Memory & Personalization
USE_USER_PREFERENCES = False  # Not implemented yet



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
