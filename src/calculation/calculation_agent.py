"""
Pension Calculation Agent module.

This module provides a specialized agent for handling pension calculation queries.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
import os
import json
from datetime import datetime

from src.calculation.calculation_manager import CalculationManager
from src.calculation.data_extractor import PensionDataExtractor

logger = logging.getLogger('calculation_agent')

class CalculationAgent:
    """
    Agent for handling pension calculation queries.
    
    This class provides methods for detecting calculation intents, extracting
    calculation parameters from user queries, and performing pension calculations.
    """
    
    def __init__(self):
        """Initialize the CalculationAgent."""
        self.calculation_manager = CalculationManager()
        self.data_extractor = PensionDataExtractor()
        
        # Define calculation intent patterns
        self.calculation_intents = {
            "retirement_estimate": [
                r"retirement\s*estimate",
                r"pension\s*estimate",
                r"how\s*much\s*(?:will|would)\s*(?:I|my)\s*(?:get|receive|have)\s*(?:in|as|for)\s*(?:my)?\s*pension",
                r"calculate\s*(?:my)?\s*pension",
                r"estimate\s*(?:my)?\s*retirement",
                r"what\s*(?:will|would)\s*(?:my)?\s*pension\s*be"
            ],
            "contribution_calculation": [
                r"contribution\s*(?:amount|calculation)",
                r"how\s*much\s*(?:is|will|would)\s*(?:be)?\s*(?:contributed|paid|set aside)",
                r"calculate\s*(?:my)?\s*contribution",
                r"what\s*(?:is|are)\s*the\s*contributions"
            ],
            "early_retirement": [
                r"early\s*retirement",
                r"retire\s*early",
                r"before\s*(?:normal|standard)\s*retirement\s*age"
            ],
            "comparison": [
                r"compare\s*(?:between|with)?",
                r"difference\s*between",
                r"which\s*(?:is|gives)\s*(?:better|more|higher)"
            ]
        }
        
        # Define parameter extraction patterns
        self.parameter_patterns = {
            "monthly_salary": [
                r"(?:monthly\s*)?salary\s*(?:of|is)?\s*(\d+(?:\,\d+)?(?:\.\d+)?)",
                r"(?:I|my)\s*(?:earn|make|get|have)\s*(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:per|a|each)?\s*month"
            ],
            "age": [
                r"(?:I\s*am|my\s*age\s*is)\s*(\d+)(?:\s*years\s*old)?",
                r"age\s*(?:of|is)?\s*(\d+)"
            ],
            "years_of_service": [
                r"(?:I\s*have\s*worked|service|worked)\s*(?:for)?\s*(\d+)\s*years",
                r"(\d+)\s*years\s*(?:of\s*service|working)"
            ],
            "years_until_retirement": [
                r"(\d+)\s*years\s*(?:until|before|to)\s*retirement",
                r"retire\s*in\s*(\d+)\s*years"
            ],
            "return_rate": [
                r"return\s*rate\s*(?:of|is)?\s*(\d+(?:\.\d+)?)(?:\s*)?%",
                r"(\d+(?:\.\d+)?)(?:\s*)?%\s*return"
            ]
        }
    
    def detect_calculation_intent(self, query: str) -> Tuple[bool, str, float]:
        """
        Detect if a query contains a calculation intent.
        
        Args:
            query: User query.
            
        Returns:
            Tuple[bool, str, float]: (is_calculation, calculation_type, confidence)
        """
        query = query.lower()
        
        # Check for calculation intents
        for calc_type, patterns in self.calculation_intents.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    # Simple confidence score based on pattern match
                    confidence = 0.7
                    
                    # Increase confidence if multiple patterns match
                    for additional_pattern in patterns:
                        if additional_pattern != pattern and re.search(additional_pattern, query, re.IGNORECASE):
                            confidence += 0.1
                    
                    # Cap confidence at 0.95
                    confidence = min(confidence, 0.95)
                    
                    return True, calc_type, confidence
        
        return False, "", 0.0
    
    def extract_parameters(self, query: str, agreement: str) -> Dict[str, Any]:
        """
        Extract calculation parameters from a user query.
        
        Args:
            query: User query.
            agreement: Pension agreement type.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        parameters = {}
        
        # Extract parameters using patterns
        for param_name, patterns in self.parameter_patterns.items():
            for pattern in patterns:
                matches = re.search(pattern, query, re.IGNORECASE)
                if matches:
                    # Extract value and convert to appropriate type
                    value = matches.group(1).replace(',', '')
                    
                    if param_name in ["monthly_salary", "return_rate"]:
                        parameters[param_name] = float(value)
                    else:
                        parameters[param_name] = int(value)
                    
                    # Break once we've found a match for this parameter
                    break
        
        # Convert return rate from percentage to decimal if present
        if "return_rate" in parameters:
            parameters["return_rate"] = parameters["return_rate"] / 100
        
        # Set default retirement age if years_until_retirement is not provided
        if "age" in parameters and "years_until_retirement" not in parameters:
            # Default retirement age is 65
            parameters["years_until_retirement"] = 65 - parameters["age"]
        
        return parameters
    
    def handle_calculation_query(self, query: str, agreement: str) -> Dict[str, Any]:
        """
        Handle a calculation query.
        
        Args:
            query: User query.
            agreement: Pension agreement type.
            
        Returns:
            Dict[str, Any]: Response with calculation results or follow-up questions.
        """
        # Detect calculation intent
        is_calculation, calculation_type, confidence = self.detect_calculation_intent(query)
        
        if not is_calculation or confidence < 0.6:
            return {
                "is_calculation": False,
                "message": "This doesn't appear to be a calculation query."
            }
        
        # Extract parameters from query
        parameters = self.extract_parameters(query, agreement)
        
        # Check if we have the required parameters
        required_params = ["monthly_salary"]
        if calculation_type == "retirement_estimate":
            required_params.extend(["age"])
        
        missing_params = [param for param in required_params if param not in parameters]
        
        if missing_params:
            # Return request for missing parameters
            return {
                "is_calculation": True,
                "calculation_type": calculation_type,
                "requires_more_info": True,
                "missing_parameters": missing_params,
                "current_parameters": parameters,
                "message": f"I need more information to calculate your {calculation_type.replace('_', ' ')}."
            }
        
        # Perform calculation
        result = self.calculation_manager.calculate(agreement, calculation_type, parameters)
        
        if "error" in result:
            return {
                "is_calculation": True,
                "calculation_type": calculation_type,
                "success": False,
                "message": f"Error performing calculation: {result['error']}"
            }
        
        # Format response based on calculation type
        if calculation_type == "retirement_estimate":
            response_message = self._format_retirement_estimate(result, agreement)
        elif calculation_type == "contribution_calculation":
            response_message = self._format_contribution_calculation(result, agreement)
        else:
            response_message = f"Calculation completed successfully for {agreement}."
        
        return {
            "is_calculation": True,
            "calculation_type": calculation_type,
            "success": True,
            "result": result,
            "message": response_message
        }
    
    def _format_retirement_estimate(self, result: Dict[str, Any], agreement: str) -> str:
        """
        Format retirement estimate calculation results.
        
        Args:
            result: Calculation results.
            agreement: Pension agreement type.
            
        Returns:
            str: Formatted message.
        """
        monthly_pension = result.get("monthly_pension", 0)
        total_pension_capital = result.get("total_pension_capital", 0)
        annual_contribution = result.get("annual_contribution", 0)
        
        message = f"Based on your {agreement} pension agreement, here's your retirement estimate:\n\n"
        message += f"• Estimated monthly pension: {monthly_pension:,.2f} SEK\n"
        message += f"• Total pension capital at retirement: {total_pension_capital:,.2f} SEK\n"
        message += f"• Current annual contribution: {annual_contribution:,.2f} SEK\n"
        
        # Add agreement-specific details
        if agreement == "ITP1" or agreement == "PA16":
            contribution_below_cap = result.get("contribution_below_cap", 0)
            contribution_above_cap = result.get("contribution_above_cap", 0)
            
            if contribution_above_cap > 0:
                message += f"• Contribution below income cap: {contribution_below_cap:,.2f} SEK\n"
                message += f"• Contribution above income cap: {contribution_above_cap:,.2f} SEK\n"
        
        elif agreement == "ITP2":
            defined_benefit_monthly = result.get("defined_benefit_monthly", 0)
            itpk_monthly = result.get("itpk_monthly", 0)
            defined_benefit_percentage = result.get("defined_benefit_percentage", 0)
            
            message += f"• Defined benefit portion: {defined_benefit_monthly:,.2f} SEK per month\n"
            message += f"• ITPK portion: {itpk_monthly:,.2f} SEK per month\n"
            message += f"• Defined benefit percentage: {defined_benefit_percentage}%\n"
        
        # Add calculation assumptions
        parameters_used = result.get("parameters_used", {})
        
        message += "\nCalculation assumptions:\n"
        message += f"• Monthly salary: {parameters_used.get('monthly_salary', 0):,.2f} SEK\n"
        message += f"• Current age: {parameters_used.get('age', 0)} years\n"
        message += f"• Years until retirement: {parameters_used.get('years_until_retirement', 0)} years\n"
        message += f"• Annual return rate: {parameters_used.get('return_rate', 0) * 100:.1f}%\n"
        
        if agreement == "ITP2":
            message += f"• Years of service: {parameters_used.get('years_of_service', 0)} years\n"
        
        return message
    
    def _format_contribution_calculation(self, result: Dict[str, Any], agreement: str) -> str:
        """
        Format contribution calculation results.
        
        Args:
            result: Calculation results.
            agreement: Pension agreement type.
            
        Returns:
            str: Formatted message.
        """
        annual_contribution = result.get("annual_contribution", 0)
        monthly_contribution = result.get("monthly_contribution", 0)
        
        message = f"Based on your {agreement} pension agreement, here are your contribution details:\n\n"
        message += f"• Annual contribution: {annual_contribution:,.2f} SEK\n"
        message += f"• Monthly contribution: {monthly_contribution:,.2f} SEK\n"
        
        # Add agreement-specific details
        if agreement == "ITP1" or agreement == "PA16":
            contribution_below_cap = result.get("contribution_below_cap", 0)
            contribution_above_cap = result.get("contribution_above_cap", 0)
            
            if contribution_above_cap > 0:
                message += f"• Contribution below income cap: {contribution_below_cap:,.2f} SEK\n"
                message += f"• Contribution above income cap: {contribution_above_cap:,.2f} SEK\n"
        
        elif agreement == "ITP2":
            itpk_annual_contribution = result.get("itpk_annual_contribution", 0)
            itpk_monthly_contribution = result.get("itpk_monthly_contribution", 0)
            
            message += f"• ITPK annual contribution: {itpk_annual_contribution:,.2f} SEK\n"
            message += f"• ITPK monthly contribution: {itpk_monthly_contribution:,.2f} SEK\n"
        
        # Add calculation assumptions
        parameters_used = result.get("parameters_used", {})
        
        message += "\nCalculation assumptions:\n"
        message += f"• Monthly salary: {parameters_used.get('monthly_salary', 0):,.2f} SEK\n"
        
        return message
    
    def update_parameters_from_documents(self) -> Dict[str, Any]:
        """
        Update calculation parameters from pension agreement documents.
        
        Returns:
            Dict[str, Any]: Dictionary of changes by agreement type.
        """
        agreement_types = ["ITP1", "ITP2", "SAF-LO", "PA16"]
        changes = {}
        
        for agreement in agreement_types:
            # Extract parameters from documents
            parameters = self.data_extractor.extract_parameters(agreement, force_refresh=True)
            
            # Update calculation parameters
            if parameters:
                self.calculation_manager.update_calculation_parameters(agreement, parameters)
                changes[agreement] = parameters
        
        return changes
    
    def detect_parameter_changes(self) -> Dict[str, Any]:
        """
        Detect changes in calculation parameters from pension agreement documents.
        
        Returns:
            Dict[str, Any]: Dictionary of changes by agreement type.
        """
        agreement_types = ["ITP1", "ITP2", "SAF-LO", "PA16"]
        all_changes = {}
        
        for agreement in agreement_types:
            # Detect changes
            has_changes, changes = self.data_extractor.detect_parameter_changes(agreement)
            
            if has_changes:
                all_changes[agreement] = changes
                
                # Update calculation parameters with new values
                current_params = self.calculation_manager.get_calculation_parameters(agreement)
                updated_params = current_params.copy()
                
                for param, change_info in changes.items():
                    updated_params[param] = change_info["new_value"]
                
                self.calculation_manager.update_calculation_parameters(agreement, updated_params)
        
        return all_changes
