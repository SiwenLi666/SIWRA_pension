import json
import os
from dataclasses import dataclass
from typing import List, Optional
import logging
from src.utils.config import SUMMARY_JSON_PATH
import traceback
print("[INFO] Loading summary.json from:")
traceback.print_stack(limit=3)


logger = logging.getLogger('presentation_db')


SUMMARY_FILE = SUMMARY_JSON_PATH

@dataclass
class PensionAgreementData:
    name: str
    summary: str

@dataclass
class PensionFactorSet:
    agreements: List[str]

class PensionAnalysisManager:
    def __init__(self):
        self.data = self._load_summary_data()

    def _load_summary_data(self) -> List[PensionAgreementData]:
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            logger.info(f"✅ Loaded {len(raw)} agreements from summary.json")
            agreements = raw.get("agreements", [])  # <- correctly extract the list
            return [PensionAgreementData(name=entry["name"], summary="; ".join([doc["summary"] for doc in entry.get("documents", [])])) for entry in agreements]

        except Exception as e:
            logger.warning(f"⚠️ Failed to load summary.json: {e}")
            return []

    def get_factors(self) -> PensionFactorSet:
        if not self.data:
            return PensionFactorSet(agreements=[])
        return PensionFactorSet(agreements=[entry.summary for entry in self.data])

    def get_agreement_titles(self) -> List[str]:
        return [entry.name for entry in self.data]

    def get_summary_for_agreement(self, agreement_name: str) -> Optional[str]:
        for entry in self.data:
            if agreement_name.lower() in entry.name.lower():
                return entry.summary
        return None
