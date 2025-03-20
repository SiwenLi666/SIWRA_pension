from pathlib import Path
from typing import List, Dict, Optional, Any  # Ensure Any is included
from dataclasses import dataclass, field  # 'field' is needed for default_factory
from contextlib import contextmanager
import logging
from dataclasses import dataclass, field  # Ensure field is included

logger = logging.getLogger(__name__)

@dataclass
class PensionAnalysisFactors:
    agreements: List[Dict[str, Any]]  # List of agreements with their details
    selected_agreement: Optional[Dict[str, Any]] = None  # Selected agreement
    age: Optional[int] = None
    years_worked: Optional[int] = None
    employment_type: Optional[str] = None  # Public, private, self-employed
    current_salary: Optional[float] = None
    union_membership: Optional[bool] = None
    retirement_goals: List[str] = field(default_factory=list)
    risk_tolerance: Optional[str] = None
    family_situation: Optional[str] = None
    current_pension_plans: List[str] = field(default_factory=list)

    def update_agreements(self, all_agreements: List[Dict[str, Any]], selected_agreement: Optional[Dict[str, Any]]):
        self.agreements = all_agreements  # Update with all agreements
        self.selected_agreement = selected_agreement  # Set the selected agreement

class PensionAnalysisManager:
    def __init__(self):
        self.factors = PensionAnalysisFactors(agreements=[])

    def update_agreements(self, new_agreements: List[Dict[str, Any]]):
        """Update the list of agreements."""
        self.factors.agreements = new_agreements

    def clear_factors(self):
        """Clear all factors."""
        self.factors = PensionAnalysisFactors(agreements=[])

    def get_factors(self) -> PensionAnalysisFactors:
        """Get the current factors."""
        return self.factors

    def save_agreement(self, agreement_name: str):
        """Save the agreement name to the factors."""
        self.factors.agreements.append({"name": agreement_name})  # Store agreement name