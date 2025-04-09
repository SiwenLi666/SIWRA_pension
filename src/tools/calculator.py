import re
import logging
from typing import Dict, Any, List, Optional
from src.agents.tool_using_agent import BaseTool

logger = logging.getLogger(__name__)

class CalculatorTool(BaseTool):
    """Tool for handling pension calculations"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Performs pension calculations based on user parameters"
        )
    
    def can_handle(self, question: str, state: Dict[str, Any]) -> bool:
        """Determine if this tool can handle the given question"""
        question_lower = question.lower()
        
        # Specific calculation-related patterns
        calculation_patterns = [
            r'hur\s+mycket\s+pension',
            r'hur\s+stor\s+blir\s+min\s+pension',
            r'vad\s+får\s+jag\s+i\s+pension',
            r'beräkna\s+min\s+pension',
            r'räkna\s+ut\s+min\s+pension',
            r'min\s+månadslön\s+är',
            r'jag\s+tjänar',
            r'min\s+lön\s+är'
        ]
        
        # Check for specific calculation patterns
        has_calculation_pattern = any(re.search(pattern, question_lower) for pattern in calculation_patterns)
        
        # Check for salary and age patterns together (strong indicator of calculation intent)
        has_salary_pattern = bool(re.search(r'(\d[\d\s]*\s*kr|\d[\d\s]*\s*kronor|\d[\d\s]*\s*sek)', question_lower))
        has_age_pattern = bool(re.search(r'(\d+)\s*år', question_lower))
        has_salary_and_age = has_salary_pattern and has_age_pattern
        
        # Check if we're in an ongoing calculation conversation with existing parameters
        has_calculation_context = "calculation_parameters" in state and state.get("calculation_parameters")
        
        # Short follow-up in a calculation context
        is_followup = has_calculation_context and len(question.split()) < 10 and bool(re.search(r'\d+', question_lower))
        
        # Exclude questions that are clearly not about calculations
        exclusion_patterns = [
            r'hur\s+länge',
            r'kan\s+man',
            r'tillåtet\s+att',
            r'möjligt\s+att',
            r'enligt\s+överenskommelsen',
            r'enligt\s+avtalet',
            r'rättigheter',
            r'skyldigheter'
        ]
        
        is_excluded = any(re.search(pattern, question_lower) for pattern in exclusion_patterns)
        
        # Final decision logic
        result = (has_calculation_pattern or has_salary_and_age or is_followup) and not is_excluded
        
        logger.info(f"Calculator can_handle: {result} (calculation pattern: {has_calculation_pattern}, "
                   f"salary+age: {has_salary_and_age}, followup: {is_followup}, excluded: {is_excluded})")
        return result
    
    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the calculation based on the question"""
        logger.info("Running calculator tool")
        
        # Get existing parameters from state if available
        existing_parameters = state.get("calculation_parameters", {})
        
        # Extract parameters from the current question
        new_parameters = self._extract_parameters(question)
        
        # Merge parameters, prioritizing new parameters over existing ones
        parameters = {**existing_parameters, **new_parameters}
        
        # Save parameters back to state for future questions
        state["calculation_parameters"] = parameters
        
        # Check if we have all required parameters
        missing_params = self._check_missing_parameters(parameters)
        if missing_params:
            # Ask for missing parameters
            state["response"] = self._generate_missing_params_response(missing_params)
            return state
        
        # Perform the calculation
        result = self._perform_calculation(parameters)
        
        # Format the response
        state["response"] = self._format_result(result, parameters)
        return state
    
    def _extract_parameters(self, question: str) -> Dict[str, Any]:
        """Extract calculation parameters from the question"""
        parameters = {}
        
        # Extract age
        age_match = re.search(r'(\d+)\s*år', question, re.IGNORECASE)
        if age_match:
            parameters["age"] = int(age_match.group(1))
        
        # Extract salary
        salary_match = re.search(r'(\d[\d\s]*)\s*kr', question, re.IGNORECASE)
        if salary_match:
            salary_str = salary_match.group(1).replace(" ", "")
            parameters["monthly_salary"] = int(salary_str)
        
        # Extract retirement age if specified
        retirement_match = re.search(r'pension\s*vid\s*(\d+)', question, re.IGNORECASE)
        if retirement_match:
            parameters["retirement_age"] = int(retirement_match.group(1))
        
        # Set defaults for missing parameters
        if "age" not in parameters:
            parameters["age"] = 40  # Default age
        
        if "retirement_age" not in parameters:
            parameters["retirement_age"] = 65  # Default retirement age
        
        logger.info(f"Extracted parameters: {parameters}")
        return parameters
    
    def _check_missing_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """Check if any required parameters are missing"""
        required_params = ["monthly_salary"]
        return [param for param in required_params if param not in parameters]
    
    def _generate_missing_params_response(self, missing_params: List[str]) -> str:
        """Generate a response asking for missing parameters"""
        if "monthly_salary" in missing_params:
            return "För att beräkna din pension behöver jag veta din månadslön. Kan du ange hur mycket du tjänar per månad?"
        
        return "Jag behöver mer information för att kunna beräkna din pension."
    
    def _perform_calculation(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual pension calculation"""
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 40)
        retirement_age = parameters.get("retirement_age", 65)
        
        # Simple calculation logic (can be expanded)
        years_until_retirement = retirement_age - age
        monthly_contribution = monthly_salary * 0.175  # 17.5% contribution
        
        # Assume 3% annual growth
        total_pension = monthly_contribution * 12 * years_until_retirement * 1.5
        monthly_pension = total_pension / (20 * 12)  # Assume 20 years of retirement
        
        return {
            "monthly_pension": round(monthly_pension),
            "total_pension": round(total_pension),
            "monthly_contribution": round(monthly_contribution)
        }
    
    def _format_result(self, result: Dict[str, Any], parameters: Dict[str, Any]) -> str:
        """Format the calculation result as a response with detailed explanation"""
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 40)
        retirement_age = parameters.get("retirement_age", 65)
        years_until_retirement = retirement_age - age
        
        # Create a detailed explanation
        response = f"Baserat på din månadslön på {monthly_salary} kr och din ålder på {age} år, "
        response += f"uppskattar jag att din månatliga pension vid {retirement_age} års ålder blir cirka {result['monthly_pension']} kr.\n\n"
        
        # Add calculation breakdown
        response += "**Så här beräknades pensionen:**\n"
        response += f"1. Månatlig avsättning: {monthly_salary} kr × 17.5% = {result['monthly_contribution']} kr\n"
        response += f"2. Årlig avsättning: {result['monthly_contribution']} kr × 12 månader = {result['monthly_contribution'] * 12} kr\n"
        response += f"3. Antal år till pension: {retirement_age} - {age} = {years_until_retirement} år\n"
        response += f"4. Tillväxtfaktor: 1.5 (baserat på 3% årlig tillväxt)\n"
        response += f"5. Totalt pensionskapital: {result['monthly_contribution']} kr × 12 månader × {years_until_retirement} år × 1.5 = {result['total_pension']} kr\n"
        response += f"6. Månatlig pension: {result['total_pension']} kr ÷ (20 år × 12 månader) = {result['monthly_pension']} kr\n\n"
        
        response += "Observera att detta är en förenklad beräkning. Din faktiska pension påverkas av flera faktorer som avtalspension, "
        response += "premiepension, inkomstpension, och eventuellt privat pensionssparande."
        
        return response
