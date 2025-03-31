# src/graph/state.py

from enum import Enum
from dataclasses import dataclass, field, fields
from typing import Optional, List
import uuid


class AgentState(Enum):
    STARTING = "starting"
    GATHERING_INFO = "gathering_info"
    NEEDS_MORE_INFO = "needs_more_info"
    ANALYZING_NEEDS = "analyzing_needs"
    RETRIEVING_CONTEXT = "retrieving_context"
    CALCULATING = "calculating"
    GENERATING_ADVICE = "generating_advice"
    GENERATING_RECOMMENDATIONS = "generating_recommendations"
    AWAITING_FEEDBACK = "awaiting_feedback"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class UserProfile:
    age: Optional[int] = None
    current_salary: Optional[float] = None
    employment_type: Optional[str] = None
    years_of_service: Optional[int] = None
    retirement_goals: List[str] = field(default_factory=list)
    risk_tolerance: Optional[str] = None
    family_situation: Optional[str] = None
    current_pension_plans: List[str] = field(default_factory=list)

    @classmethod
    def required_fields(cls) -> List[str]:
        """
        Return the names of the fields we consider 'required'.
        You can do any logic here—this example is a simple, explicit list.
        """
        return [
            "age",
            "current_salary",
            "employment_type",
            "years_of_service",
            "risk_tolerance",
            "family_situation",
        ]


class GraphState(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 🔁 OVERRIDE - säkerställ att 'question' blir korrekt
        if "question" in kwargs:
            self["question"] = kwargs["question"]
        elif hasattr(self, "question"):
            self["question"] = self.question
        else:
            self["question"] = ""

        self.setdefault("conversation_id", str(uuid.uuid4()))
        self.setdefault("token_usage", [])
        self.setdefault("state", AgentState.STARTING.value)
        self.setdefault("user_profile", {})
        self.setdefault("conversation_history", [])

