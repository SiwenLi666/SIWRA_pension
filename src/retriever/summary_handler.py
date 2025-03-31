# src/retriever/summary_handler.py
import os
import json
from langchain.docstore.document import Document
import logging
from src.database.presentation_db import PensionAnalysisManager
from src.utils.config import SUMMARY_JSON_PATH

SUMMARY_PATH = SUMMARY_JSON_PATH


logger = logging.getLogger(__name__)
presentation_manager = None

def get_presentation_manager():
    global presentation_manager
    if presentation_manager is None:
        presentation_manager = PensionAnalysisManager()
    return presentation_manager



def load_summary_json():
    try:
        with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("summary.json must be a list of summaries")
            return [Document(page_content=item["summary"], metadata={"source": item["title"]}) for item in data]
    except Exception as e:
        print(f"⚠️ Failed to load summary.json: {e}")
        return []


def get_summary_fallback(question: str) -> str:
    """
    Use fallback summaries (e.g. from summary.json) if no vector result is found.
    """
    try:
        agreements = get_presentation_manager().get_factors().agreements

        logger.info(f"📄 Loaded {len(agreements)} agreements for fallback")

        matches = [a for a in agreements if question.lower() in a.lower()]
        if not matches:
            return "Just nu hittar jag inget som direkt besvarar frågan, men jag hjälper dig gärna vidare!"

        return f"Jag hittade följande information i sammanfattningarna:\n\n" + "\n\n---\n\n".join(matches[:2])
    except Exception as e:
        logger.error(f"❌ Error in summary fallback: {e}")
        return "Jag kunde inte hämta information från sammanfattningarna just nu."
