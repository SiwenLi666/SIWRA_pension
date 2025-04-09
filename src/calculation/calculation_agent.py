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
        
        # Define calculation intent patterns (both English and Swedish)
        self.calculation_intents = {
            "retirement_estimate": [
                # English patterns
                r"retirement\s*estimate",
                r"pension\s*estimate",
                r"how\s*much\s*(?:will|would)\s*(?:I|my)\s*(?:get|receive|have)\s*(?:in|as|for)\s*(?:my)?\s*pension",
                r"calculate\s*(?:my)?\s*pension",
                r"estimate\s*(?:my)?\s*retirement",
                r"what\s*(?:will|would)\s*(?:my)?\s*pension\s*be",
                # Swedish patterns
                r"hur\s*mycket\s*pension\s*(?:kan|kommer|får|skulle)\s*(?:jag|man)\s*(?:få|ha)",
                r"beräkna\s*(?:min)?\s*pension",
                r"uppskatta\s*(?:min)?\s*pension",
                r"vad\s*(?:blir|skulle|kommer)\s*(?:min)?\s*pension\s*(?:bli|vara)",
                r"hur\s*stor\s*(?:blir|är)\s*(?:min)?\s*pension",
                r"pensionsbelopp",
                r"pensionsberäkning"
            ],
            "contribution_calculation": [
                # English patterns
                r"contribution\s*(?:amount|calculation)",
                r"how\s*much\s*(?:is|will|would)\s*(?:be)?\s*(?:contributed|paid|set aside)",
                r"calculate\s*(?:my)?\s*contribution",
                r"what\s*(?:is|are)\s*the\s*contributions",
                # Swedish patterns
                r"pensionsavsättning",
                r"hur\s*mycket\s*(?:avsätts|betalas|sätts)\s*(?:in|undan)",
                r"beräkna\s*(?:mina)?\s*avsättningar",
                r"vad\s*(?:är|blir)\s*(?:mina)?\s*avsättningar"
            ],
            "early_retirement": [
                # English patterns
                r"early\s*retirement",
                r"retire\s*early",
                r"before\s*(?:normal|standard)\s*retirement\s*age",
                # Swedish patterns
                r"förtidspension",
                r"gå\s*i\s*pension\s*(?:i\s*förtid|tidigt)",
                r"pension\s*före\s*(?:normal|vanlig)\s*pensionsålder"
            ],
            "comparison": [
                # English patterns
                r"compare\s*(?:between|with)?",
                r"difference\s*between",
                r"which\s*(?:is|gives)\s*(?:better|more|higher)",
                # Swedish patterns
                r"jämför\s*(?:mellan)?",
                r"skillnad\s*mellan",
                r"vilken\s*(?:är|ger)\s*(?:bättre|mer|högre)"
            ]
        }
        
        # Define parameter extraction patterns (both English and Swedish)
        self.parameter_patterns = {
            "monthly_salary": [
                # English patterns
                r"(?:monthly\s*)?salary\s*(?:of|is)?\s*(\d+(?:\,\d+)?(?:\.\d+)?)",
                r"(?:I|my)\s*(?:earn|make|get|have)\s*(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:per|a|each)?\s*month",
                # Swedish patterns
                r"(?:månads)?lön\s*(?:på|av|är)?\s*(\d+(?:\s*\d+)*(?:\,\d+)?(?:\.\d+)?)",
                r"(?:jag|min)\s*(?:tjänar|får|har)\s*(\d+(?:\s*\d+)*(?:\,\d+)?(?:\.\d+)?)\s*(?:per|i|varje)?\s*månad",
                r"månadsinkomst\s*(?:på|av|är)?\s*(\d+(?:\s*\d+)*(?:\,\d+)?(?:\.\d+)?)"
            ],
            "age": [
                # English patterns
                r"(?:I\s*am|my\s*age\s*is)\s*(\d+)(?:\s*years\s*old)?",
                r"age\s*(?:of|is)?\s*(\d+)",
                # Swedish patterns
                r"(?:jag\s*är|min\s*ålder\s*är)\s*(\d+)(?:\s*år(?:\s*gammal)?)?",
                r"ålder\s*(?:på|är)?\s*(\d+)",
                r"(\d+)\s*år\s*(?:gammal)?"
            ],
            "years_of_service": [
                # English patterns
                r"(?:I\s*have\s*worked|service|worked)\s*(?:for)?\s*(\d+)\s*years",
                r"(\d+)\s*years\s*(?:of\s*service|working)",
                # Swedish patterns
                r"(?:jag\s*har\s*arbetat|tjänstgjort|arbetat)\s*(?:i)?\s*(\d+)\s*år",
                r"(\d+)\s*års?\s*(?:tjänstgöring|anställning|arbete)"
            ],
            "years_until_retirement": [
                # English patterns
                r"(\d+)\s*years\s*(?:until|before|to)\s*retirement",
                r"retire\s*in\s*(\d+)\s*years",
                # Swedish patterns
                r"(\d+)\s*år\s*(?:till|innan|före)\s*pension",
                r"gå\s*i\s*pension\s*om\s*(\d+)\s*år"
            ],
            "return_rate": [
                # English patterns
                r"return\s*rate\s*(?:of|is)?\s*(\d+(?:\.\d+)?)(?:\s*)?%",
                r"(\d+(?:\.\d+)?)(?:\s*)?%\s*return",
                # Swedish patterns
                r"avkastning\s*(?:på|är)?\s*(\d+(?:\,\d+)?)(?:\s*)?%",
                r"(\d+(?:\,\d+)?)(?:\s*)?%\s*(?:i\s*)?avkastning"
            ]
        }
    
    def detect_calculation_intent(self, question: str) -> Tuple[bool, str, float]:
        """Detect if the question is asking for a calculation.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple of (is_calculation, calculation_type, confidence)
        """
        # Log the input for debugging
        logger.info(f"DEBUG: detect_calculation_intent - Analyzing question: '{question}'")
        
        # For MVP: Simple pattern matching for common calculation questions
        retirement_patterns = [
            r"(hur mycket|hur stor) .* pension",
            r"(beräkna|räkna) .* pension",
            r"(hur mycket|hur stor) .* få .* pension",
            r"(hur mycket|hur stor) .* bli .* pension",
            r"(hur mycket|hur stor) .* pensionsbelopp",
            r"(vad|hur) .* pension .* bli",
            r"(vad|hur) .* få .* pension",
            r"pension .* (beräkna|räkna)",
            r"pension .* (hur mycket|hur stor)",
            r"(beräkna|räkna) .* (få|bli)",
        ]
        
        contribution_patterns = [
            r"(hur mycket|hur stor) .* avsättning",
            r"(beräkna|räkna) .* avsättning",
            r"(hur mycket|hur stor) .* pensionsavsättning",
            r"(hur mycket|hur stor) .* sätta av .* pension",
            r"(hur mycket|hur stor) .* betala .* pension",
            r"(vad|hur) .* avsättning .* bli",
            r"(vad|hur) .* betala .* pension",
            r"avsättning .* (beräkna|räkna)",
            r"(sätta av|betala) .* pension",
        ]
        
        # Simple keyword check as backup
        calculation_keywords = [
            "beräkna", "räkna", "pension", "pensionsbelopp", "pensionsavsättning",
            "hur mycket", "hur stor", "lön", "månadslön", "ålder", "avkastning"
        ]
        
        # Count keywords in the question
        keyword_count = sum(1 for keyword in calculation_keywords if keyword.lower() in question.lower())
        logger.info(f"DEBUG: detect_calculation_intent - Found {keyword_count} calculation keywords")
        
        # Check for retirement estimate patterns
        for pattern in retirement_patterns:
            if re.search(pattern, question.lower()):
                logger.info(f"DEBUG: detect_calculation_intent - Matched retirement pattern: {pattern}")
                return True, "retirement_estimate", 0.9
        
        # Check for contribution calculation patterns
        for pattern in contribution_patterns:
            if re.search(pattern, question.lower()):
                logger.info(f"DEBUG: detect_calculation_intent - Matched contribution pattern: {pattern}")
                return True, "contribution_calculation", 0.9
        
        # If no pattern matches but we have enough keywords, consider it a calculation
        if keyword_count >= 2:
            logger.info(f"DEBUG: detect_calculation_intent - Detected calculation based on {keyword_count} keywords")
            # Default to retirement estimate for now
            return True, "retirement_estimate", 0.7
        
        # If no pattern matches and not enough keywords, it's not a calculation question
        logger.info("DEBUG: detect_calculation_intent - Not a calculation question")
        return False, "", 0.0
    
    def extract_parameters(self, query: str, agreement: str) -> Dict[str, Any]:
        """
        Extract calculation parameters from a user query.
        
        Args:
            query: User query.
            agreement: Selected pension agreement.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        parameters = {}
        
        # Log the query for debugging
        logger.info(f"DEBUG: extract_parameters - Analyzing query: '{query}'")
        
        # Extract age
        age_patterns = [
            r"jag är (\d+) år",
            r"(\d+) år gammal",
            r"ålder.{1,10}(\d+)",
            r"(\d+).{1,10}ålder",
            r"jag är (\d+)",  # More flexible pattern
            r"min ålder är (\d+)",
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    age = int(match.group(1))
                    parameters["age"] = age
                    logger.info(f"DEBUG: extract_parameters - Extracted age: {age}")
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract monthly salary
        salary_patterns = [
            r"lön.{1,15}(\d[\d\s]*)[\s]*kr",
            r"(\d[\d\s]*)[\s]*kr.{1,15}lön",
            r"månadslön.{1,15}(\d[\d\s]*)[\s]*kr",
            r"(\d[\d\s]*)[\s]*kr.{1,15}månadslön",
            r"tjänar.{1,15}(\d[\d\s]*)[\s]*kr",
            r"inkomst.{1,15}(\d[\d\s]*)[\s]*kr",
            r"lön.{1,15}(\d[\d\s]*)",  # More flexible pattern
            r"månadslön.{1,15}(\d[\d\s]*)",
            r"tjänar.{1,15}(\d[\d\s]*)",
            r"inkomst.{1,15}(\d[\d\s]*)",
        ]
        
        for pattern in salary_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    # Remove spaces and convert to integer
                    salary_str = match.group(1).replace(" ", "")
                    salary = int(salary_str)
                    parameters["monthly_salary"] = salary
                    logger.info(f"DEBUG: extract_parameters - Extracted monthly_salary: {salary}")
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract retirement age (if specified)
        retirement_age_patterns = [
            r"gå i pension vid (\d+)",
            r"pensionera mig vid (\d+)",
            r"pensionsålder.{1,10}(\d+)",
            r"(\d+).{1,10}pensionsålder",
            r"pension vid (\d+)",  # More flexible pattern
            r"vid (\d+) års ålder",
        ]
        
        for pattern in retirement_age_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    retirement_age = int(match.group(1))
                    parameters["retirement_age"] = retirement_age
                    logger.info(f"DEBUG: extract_parameters - Extracted retirement_age: {retirement_age}")
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract years of service (if specified)
        service_patterns = [
            r"arbetat i (\d+) år",
            r"jobbat i (\d+) år",
            r"(\d+) års tjänst",
            r"(\d+) år i tjänst",
            r"(\d+) år på jobbet",
        ]
        
        for pattern in service_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                try:
                    years = int(match.group(1))
                    parameters["years_of_service"] = years
                    logger.info(f"DEBUG: extract_parameters - Extracted years_of_service: {years}")
                    break
                except (ValueError, IndexError):
                    pass
        
        # Handle direct number mentions that might be salary or age
        if "monthly_salary" not in parameters:
            # Try to find standalone numbers that might be salary
            salary_match = re.search(r"\b(\d{4,6})\b", query)
            if salary_match:
                try:
                    potential_salary = int(salary_match.group(1))
                    # If it's in a reasonable salary range (4000-100000 kr)
                    if 4000 <= potential_salary <= 100000:
                        parameters["monthly_salary"] = potential_salary
                        logger.info(f"DEBUG: extract_parameters - Extracted potential monthly_salary: {potential_salary}")
                except (ValueError, IndexError):
                    pass
        
        # Set agreement if specified
        if agreement:
            parameters["agreement"] = agreement
            logger.info(f"DEBUG: extract_parameters - Using agreement: {agreement}")
        
        logger.info(f"DEBUG: extract_parameters - Final extracted parameters: {parameters}")
        return parameters
    
    def get_required_parameters(self, calculation_type: str, agreement: str = "") -> List[str]:
        """Get the required parameters for a specific calculation type.
        
        Args:
            calculation_type: Type of calculation
            agreement: The pension agreement to use
            
        Returns:
            List of required parameter names
        """
        # For MVP, define basic required parameters for each calculation type
        if calculation_type == "retirement_estimate":
            return ["age", "monthly_salary"]
        elif calculation_type == "contribution_calculation":
            return ["monthly_salary"]
        elif calculation_type == "early_retirement":
            return ["age", "monthly_salary", "years_of_service"]
        elif calculation_type == "comparison":
            return ["age", "monthly_salary", "years_of_service"]
        else:
            # Default parameters for unknown calculation types
            return ["age", "monthly_salary"]
            
    def perform_calculation(self, calculation_type: str, parameters: Dict[str, Any], agreement: str = "") -> Dict[str, Any]:
        """Perform a pension calculation based on the provided parameters.
        
        Args:
            calculation_type: Type of calculation to perform
            parameters: Dictionary of parameters for the calculation
            agreement: The pension agreement to use for calculation
            
        Returns:
            Dictionary containing the calculation results
        """
        # For MVP, implement simple calculations
        if calculation_type == "retirement_estimate":
            # Simple retirement estimate calculation
            monthly_salary = parameters.get("monthly_salary", 0)
            age = parameters.get("age", 65)
            years_of_service = parameters.get("years_of_service", 0)
            
            # Very basic calculation for MVP
            # In a real system, this would use agreement-specific formulas
            replacement_rate = 0.5  # 50% of salary
            age_factor = max(0, min(1, (age - 25) / 40))  # Factor based on age
            service_factor = min(1, years_of_service / 30)  # Factor based on service years
            
            # Calculate monthly pension
            monthly_pension = monthly_salary * replacement_rate * age_factor * service_factor
            monthly_pension = round(monthly_pension, 0)  # Round to nearest krona
            
            # Calculate total pension capital (simple estimate)
            years_in_retirement = 20  # Assume 20 years in retirement
            months_in_retirement = years_in_retirement * 12
            total_pension = monthly_pension * months_in_retirement
            total_pension = round(total_pension, -3)  # Round to nearest thousand
            
            return {
                "monthly_pension": monthly_pension,
                "total_pension": total_pension,
                "replacement_rate": replacement_rate,
                "age_factor": age_factor,
                "service_factor": service_factor
            }
            
        elif calculation_type == "contribution_calculation":
            # Calculate pension contributions
            monthly_salary = parameters.get("monthly_salary", 0)
            
            # Basic contribution calculation
            # In a real system, this would use agreement-specific rates and thresholds
            contribution_rate = 0.045  # 4.5% contribution rate
            monthly_contribution = monthly_salary * contribution_rate
            yearly_contribution = monthly_contribution * 12
            
            monthly_contribution = round(monthly_contribution, 0)  # Round to nearest krona
            yearly_contribution = round(yearly_contribution, 0)  # Round to nearest krona
            
            return {
                "monthly_contribution": monthly_contribution,
                "yearly_contribution": yearly_contribution,
                "contribution_rate": contribution_rate
            }
            
        else:
            # Default empty result for unsupported calculation types
            return {"error": f"Calculation type '{calculation_type}' not supported"}
    
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
        required_params = self.get_required_parameters(calculation_type, agreement)
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
