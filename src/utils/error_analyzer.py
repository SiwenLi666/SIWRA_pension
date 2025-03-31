import logging
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
from src.database.presentation_db import PensionAnalysisManager
from src.graph.state import GraphState

logger = logging.getLogger(__name__)

class ErrorType(str, Enum):
    MISSING_INFO = "missing_info"
    CALCULATION_ERROR = "calculation_error"
    UNKNOWN = "unknown"

@dataclass
class ErrorAnalysis:
    error_type: ErrorType
    can_recover: bool
    user_message: str
    missing_factors: Optional[List[str]] = None

class ErrorAnalyzer:
    def __init__(self):
        self.presentation_manager = PensionAnalysisManager()

    def analyze_error(self, error: str, state: GraphState) -> ErrorAnalysis:
        """Analyzes the error message and classifies the type"""
        logger.debug(f"Analyzing error: {error}")

        # Simple detection of missing info
        if "information" in error.lower() or "saknar" in error.lower() or "missing" in error.lower():
            missing_fields = self.detect_missing_factors(state)
            message = "Jag saknar fortfarande lite information. Kan du hjälpa mig med följande:\n" + ", ".join(missing_fields)
            return ErrorAnalysis(
                error_type=ErrorType.MISSING_INFO,
                can_recover=True,
                user_message=message,
                missing_factors=missing_fields
            )

        if "calculation" in error.lower() or "beräkning" in error.lower():
            return ErrorAnalysis(
                error_type=ErrorType.CALCULATION_ERROR,
                can_recover=True,
                user_message="Jag hade lite problem med beräkningen. Jag försöker igen med bättre parametrar."
            )

        # Default fallback
        return ErrorAnalysis(
            error_type=ErrorType.UNKNOWN,
            can_recover=False,
            user_message="Tyvärr uppstod ett oväntat fel. Jag gör mitt bästa för att hjälpa dig vidare!"
        )

    def detect_missing_factors(self, state: GraphState) -> List[str]:
        """Uses the presentation manager to identify required but missing fields"""
        user_profile = state.get("user_profile", {})
        required_fields = self.presentation_manager.get_required_factors()
        return [field.name for field in required_fields if field.name not in user_profile]

    def update_presentation_db(self, analysis: ErrorAnalysis, state: GraphState) -> None:
        """(Optional) Save error insights into a presentation summary or memory"""
        logger.debug(f"Logging error insight: {analysis.error_type}")
        # Could append to memory or notify admin/dev team in production
        # Here we just log for now
        logger.info(f"Error insight: {analysis}")
        return

# Shared instance
error_analyzer = ErrorAnalyzer()
