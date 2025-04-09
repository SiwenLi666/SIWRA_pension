"""
Pension Calculation Manager module.

This module provides functionality for performing pension calculations based on
different pension agreements (ITP1, ITP2, SAF-LO, PA16) and calculation types.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import os
import json
from pathlib import Path

from src.utils.config import BASE_DIR

logger = logging.getLogger('calculation_manager')

class CalculationManager:
    """
    Manager class for handling pension calculations.
    
    This class provides methods for calculating pension amounts, retirement estimates,
    and other pension-related calculations based on different pension agreements.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the CalculationManager.
        
        Args:
            data_dir: Directory to store calculation data. Defaults to BASE_DIR/data/calculations.
        """
        if data_dir is None:
            self.data_dir = os.path.join(BASE_DIR, "data", "calculations")
        else:
            self.data_dir = data_dir
            
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Path to the calculation parameters database
        self.parameters_db_path = os.path.join(self.data_dir, "calculation_parameters.json")
        
        # Path to the calculation history database
        self.history_db_path = os.path.join(self.data_dir, "calculation_history.json")
        
        # Load or create calculation parameters database
        self.parameters_db = self._load_or_create_db(self.parameters_db_path)
        
        # Load or create calculation history database
        self.history_db = self._load_or_create_db(self.history_db_path)
        
        # Get available agreements from config
        from src.utils.config import AVAILABLE_AGREEMENTS
        self.available_agreements = AVAILABLE_AGREEMENTS
        
        # Initialize calculation formulas for different pension agreements
        self.calculation_formulas = {
            "ITP1": self._calculate_itp1,
            "ITP2": self._calculate_itp2,
            "SAF-LO": self._calculate_saflo,
            "PA16": self._calculate_pa16,
            "SKR2023": self._calculate_skr2023  # Add SKR2023 formula
        }
    
    def _load_or_create_db(self, db_path: str) -> Dict:
        """
        Load database from file or create a new one if it doesn't exist.
        
        Args:
            db_path: Path to the database file.
            
        Returns:
            Dict: Loaded database.
        """
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading database from {db_path}: {str(e)}")
                return {}
        else:
            return {}
    
    def _save_db(self, db: Dict, db_path: str) -> bool:
        """
        Save database to file.
        
        Args:
            db: Database to save.
            db_path: Path to save the database to.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving database to {db_path}: {str(e)}")
            return False
    
    def calculate(self, 
                  agreement: str, 
                  calculation_type: str, 
                  parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a pension calculation.
        
        Args:
            agreement: Pension agreement type (ITP1, ITP2, SAF-LO, PA16, SKR2023).
            calculation_type: Type of calculation to perform (retirement, early_retirement, etc.).
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        try:
            # If no agreement specified, use a default or generic calculation
            if not agreement or agreement.strip() == "":
                # Use the first available agreement or a generic calculation
                if self.available_agreements:
                    agreement = self.available_agreements[0]
                    logger.info(f"No agreement specified, using default: {agreement}")
                else:
                    # Use a generic calculation if no agreements are available
                    return self._calculate_generic(calculation_type, parameters)
            
            # Validate agreement
            if agreement not in self.calculation_formulas:
                logger.warning(f"Unsupported agreement: {agreement}, using generic calculation")
                return self._calculate_generic(calculation_type, parameters)
            
            # Get calculation function
            calculation_func = self.calculation_formulas[agreement]
            
            # Perform calculation
            result = calculation_func(calculation_type, parameters)
            
            # Record calculation in history
            self._record_calculation(agreement, calculation_type, parameters, result)
            
            return result
        except Exception as e:
            logger.error(f"Error performing calculation: {str(e)}")
            return {
                "error": str(e),
                "success": False
            }
    
    def _calculate_generic(self, calculation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a generic pension calculation when no specific agreement is selected.
        This provides a reasonable estimate based on Swedish pension system basics.
        
        Args:
            calculation_type: Type of calculation to perform.
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        # Default parameters for generic calculations
        generic_params = {
            "contribution_rate": 0.175,        # 17.5% of salary (typical Swedish system)
            "income_base_amount": 71000,      # SEK per year (2023)
            "price_base_amount": 52500,       # SEK per year (2023)
            "income_cap_base_amount": 7.5,    # 7.5 income base amounts
            "default_return_rate": 0.03,      # 3% annual return
            "admin_fee_percentage": 0.003,    # 0.3% annual admin fee
        }
        
        # Extract required parameters
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 40)
        years_until_retirement = parameters.get("years_until_retirement", 65 - age)
        return_rate = parameters.get("return_rate", generic_params["default_return_rate"])
        
        # Calculate annual salary
        annual_salary = monthly_salary * 12
        
        # Calculate income cap
        income_cap = generic_params["income_cap_base_amount"] * generic_params["income_base_amount"]
        
        if calculation_type == "retirement_estimate":
            # Calculate annual contribution
            annual_contribution = min(annual_salary, income_cap) * generic_params["contribution_rate"]
            
            # Project future value of contributions
            future_value = 0
            for year in range(1, years_until_retirement + 1):
                # Add this year's contribution
                future_value += annual_contribution
                
                # Apply return for the year
                future_value *= (1 + return_rate - generic_params["admin_fee_percentage"])
            
            # Convert to monthly pension (simple conversion assuming 20 years of payments)
            monthly_pension = future_value / (20 * 12)
            
            return {
                "success": True,
                "monthly_pension": round(monthly_pension, 2),
                "annual_pension": round(monthly_pension * 12, 2),
                "future_value": round(future_value, 2),
                "calculation_type": calculation_type,
                "note": "Detta är en generisk beräkning eftersom inget specifikt avtal valdes.",
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "age": age,
                    "years_until_retirement": years_until_retirement,
                    "return_rate": return_rate,
                    "generic_parameters": generic_params
                }
            }
        
        elif calculation_type == "contribution_calculation":
            # Calculate annual contribution
            annual_contribution = min(annual_salary, income_cap) * generic_params["contribution_rate"]
            
            return {
                "success": True,
                "annual_contribution": round(annual_contribution, 2),
                "monthly_contribution": round(annual_contribution / 12, 2),
                "calculation_type": calculation_type,
                "note": "Detta är en generisk beräkning eftersom inget specifikt avtal valdes.",
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "generic_parameters": generic_params
                }
            }
        
        else:
            return {
                "error": f"Unsupported calculation type for generic calculation: {calculation_type}",
                "success": False
            }
    
    def _calculate_skr2023(self, calculation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform SKR2023 pension calculation.
        
        Args:
            calculation_type: Type of calculation to perform.
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        # Get SKR2023 parameters
        skr_params = self.get_calculation_parameters("SKR2023")
        
        # Default parameters if none are stored
        if not skr_params:
            skr_params = {
                "contribution_rate": 0.045,         # 4.5% of salary
                "income_base_amount": 71000,       # SEK per year (2023)
                "price_base_amount": 52500,        # SEK per year (2023)
                "income_cap_base_amount": 7.5,     # 7.5 income base amounts
                "default_return_rate": 0.03,       # 3% annual return
                "admin_fee_percentage": 0.003,     # 0.3% annual admin fee
                "additional_contribution": 0.02,    # 2% additional contribution
            }
        
        # Extract required parameters
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 40)
        years_until_retirement = parameters.get("years_until_retirement", 65 - age)
        return_rate = parameters.get("return_rate", skr_params["default_return_rate"])
        
        # Calculate annual salary
        annual_salary = monthly_salary * 12
        
        # Calculate income cap
        income_cap = skr_params["income_cap_base_amount"] * skr_params["income_base_amount"]
        
        if calculation_type == "retirement_estimate":
            # Calculate annual contribution
            base_contribution = min(annual_salary, income_cap) * skr_params["contribution_rate"]
            
            # Additional contribution for salaries above cap
            additional_contribution = 0
            if annual_salary > income_cap:
                additional_contribution = (annual_salary - income_cap) * skr_params["additional_contribution"]
            
            total_annual_contribution = base_contribution + additional_contribution
            
            # Project future value of contributions
            future_value = 0
            for year in range(1, years_until_retirement + 1):
                # Add this year's contribution
                future_value += total_annual_contribution
                
                # Apply return for the year
                future_value *= (1 + return_rate - skr_params["admin_fee_percentage"])
            
            # Convert to monthly pension (simple conversion assuming 20 years of payments)
            monthly_pension = future_value / (20 * 12)
            
            return {
                "success": True,
                "monthly_pension": round(monthly_pension, 2),
                "annual_pension": round(monthly_pension * 12, 2),
                "future_value": round(future_value, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "age": age,
                    "years_until_retirement": years_until_retirement,
                    "return_rate": return_rate,
                    "skr_parameters": skr_params
                }
            }
        
        elif calculation_type == "contribution_calculation":
            # Calculate annual contribution
            base_contribution = min(annual_salary, income_cap) * skr_params["contribution_rate"]
            
            # Additional contribution for salaries above cap
            additional_contribution = 0
            if annual_salary > income_cap:
                additional_contribution = (annual_salary - income_cap) * skr_params["additional_contribution"]
            
            total_annual_contribution = base_contribution + additional_contribution
            
            return {
                "success": True,
                "annual_contribution": round(total_annual_contribution, 2),
                "monthly_contribution": round(total_annual_contribution / 12, 2),
                "base_contribution": round(base_contribution, 2),
                "additional_contribution": round(additional_contribution, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "skr_parameters": skr_params
                }
            }
        
        else:
            return {
                "error": f"Unsupported calculation type for SKR2023: {calculation_type}",
                "success": False
            }
    
    def _record_calculation(self, 
                           agreement: str, 
                           calculation_type: str, 
                           parameters: Dict[str, Any], 
                           result: Dict[str, Any]) -> None:
        """
        Record a calculation in the history database.
        
        Args:
            agreement: Pension agreement type.
            calculation_type: Type of calculation performed.
            parameters: Parameters used for the calculation.
            result: Calculation results.
        """
        calculation_id = f"calc_{len(self.history_db) + 1}"
        
        self.history_db[calculation_id] = {
            "agreement": agreement,
            "calculation_type": calculation_type,
            "parameters": parameters,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
        self._save_db(self.history_db, self.history_db_path)
    
    def get_calculation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get calculation history.
        
        Args:
            limit: Maximum number of history items to return.
            
        Returns:
            List[Dict[str, Any]]: List of calculation history items.
        """
        # Sort by timestamp (newest first)
        sorted_history = sorted(
            self.history_db.items(),
            key=lambda x: x[1]["timestamp"],
            reverse=True
        )
        
        # Limit results
        limited_history = sorted_history[:limit]
        
        # Convert to list of dictionaries with ID included
        return [{"id": item[0], **item[1]} for item in limited_history]
    
    def get_calculation_parameters(self, agreement: str) -> Dict[str, Any]:
        """
        Get calculation parameters for a specific agreement.
        
        Args:
            agreement: Pension agreement type.
            
        Returns:
            Dict[str, Any]: Calculation parameters.
        """
        if agreement in self.parameters_db:
            return self.parameters_db[agreement]
        else:
            return {}
    
    def update_calculation_parameters(self, agreement: str, parameters: Dict[str, Any]) -> bool:
        """
        Update calculation parameters for a specific agreement.
        
        Args:
            agreement: Pension agreement type.
            parameters: New calculation parameters.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        self.parameters_db[agreement] = parameters
        return self._save_db(self.parameters_db, self.parameters_db_path)
    
    def _calculate_itp1(self, calculation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform ITP1 pension calculation.
        
        Args:
            calculation_type: Type of calculation to perform.
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        # Get ITP1 parameters
        itp1_params = self.get_calculation_parameters("ITP1")
        
        # Default parameters if none are stored
        if not itp1_params:
            itp1_params = {
                "contribution_rate_below_cap": 0.045,  # 4.5% below income cap
                "contribution_rate_above_cap": 0.30,   # 30% above income cap
                "income_cap_base_amount": 7.5,         # 7.5 income base amounts
                "income_base_amount": 71000,           # SEK per year (2023)
                "default_return_rate": 0.03,           # 3% annual return
                "admin_fee_percentage": 0.003          # 0.3% annual admin fee
            }
        
        # Extract required parameters
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 25)
        years_until_retirement = parameters.get("years_until_retirement", 65 - age)
        return_rate = parameters.get("return_rate", itp1_params["default_return_rate"])
        
        # Calculate annual salary
        annual_salary = monthly_salary * 12
        
        # Calculate income cap
        income_cap = itp1_params["income_cap_base_amount"] * itp1_params["income_base_amount"]
        
        # Calculate contributions
        if annual_salary <= income_cap:
            annual_contribution = annual_salary * itp1_params["contribution_rate_below_cap"]
            contribution_below_cap = annual_contribution
            contribution_above_cap = 0
        else:
            contribution_below_cap = income_cap * itp1_params["contribution_rate_below_cap"]
            contribution_above_cap = (annual_salary - income_cap) * itp1_params["contribution_rate_above_cap"]
            annual_contribution = contribution_below_cap + contribution_above_cap
        
        # Calculate future value based on calculation type
        if calculation_type == "retirement_estimate":
            # Simple future value calculation with compound interest
            future_value = 0
            for year in range(years_until_retirement):
                # Add this year's contribution
                future_value += annual_contribution
                # Apply return rate and admin fee
                future_value *= (1 + return_rate - itp1_params["admin_fee_percentage"])
            
            # Calculate estimated monthly pension
            # Simplified: divide by 20 years (240 months) of retirement
            monthly_pension = future_value / 240
            
            return {
                "success": True,
                "monthly_pension": round(monthly_pension, 2),
                "total_pension_capital": round(future_value, 2),
                "annual_contribution": round(annual_contribution, 2),
                "contribution_below_cap": round(contribution_below_cap, 2),
                "contribution_above_cap": round(contribution_above_cap, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "age": age,
                    "years_until_retirement": years_until_retirement,
                    "return_rate": return_rate,
                    "itp1_parameters": itp1_params
                }
            }
        
        elif calculation_type == "contribution_calculation":
            return {
                "success": True,
                "annual_contribution": round(annual_contribution, 2),
                "monthly_contribution": round(annual_contribution / 12, 2),
                "contribution_below_cap": round(contribution_below_cap, 2),
                "contribution_above_cap": round(contribution_above_cap, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "itp1_parameters": itp1_params
                }
            }
        
        else:
            raise ValueError(f"Unsupported calculation type for ITP1: {calculation_type}")
    
    def _calculate_itp2(self, calculation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform ITP2 pension calculation.
        
        Args:
            calculation_type: Type of calculation to perform.
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        # Get ITP2 parameters
        itp2_params = self.get_calculation_parameters("ITP2")
        
        # Default parameters if none are stored
        if not itp2_params:
            itp2_params = {
                "income_base_amount": 71000,           # SEK per year (2023)
                "price_base_amount": 52500,            # SEK per year (2023)
                "itpk_contribution_rate": 0.02,        # 2% of salary
                "income_cap_base_amount": 7.5,         # 7.5 income base amounts
                "default_return_rate": 0.03,           # 3% annual return
                "admin_fee_percentage": 0.003,         # 0.3% annual admin fee
                "accrual_rate_30_years": 0.10,         # 10% for 30 years of service or less
                "accrual_rate_over_30_years": 0.0725,  # 7.25% for more than 30 years of service
                "family_protection_cost": 0.002        # 0.2% for family protection
            }
        
        # Extract required parameters
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 40)
        years_of_service = parameters.get("years_of_service", 10)
        years_until_retirement = parameters.get("years_until_retirement", 65 - age)
        return_rate = parameters.get("return_rate", itp2_params["default_return_rate"])
        
        # Calculate annual salary
        annual_salary = monthly_salary * 12
        
        # Calculate income cap
        income_cap = itp2_params["income_cap_base_amount"] * itp2_params["income_base_amount"]
        
        # Calculate ITPK contribution
        itpk_contribution = annual_salary * itp2_params["itpk_contribution_rate"]
        
        if calculation_type == "retirement_estimate":
            # Calculate defined benefit portion
            # For ITP2, the defined benefit is based on final salary and years of service
            
            # Project final salary (simple projection with no real salary growth)
            final_salary = annual_salary
            
            # Calculate final years of service
            final_years_of_service = years_of_service + years_until_retirement
            
            # Calculate defined benefit percentage based on years of service
            if final_years_of_service <= 30:
                defined_benefit_percentage = itp2_params["accrual_rate_30_years"] * final_years_of_service / 30
            else:
                defined_benefit_percentage = (
                    itp2_params["accrual_rate_30_years"] + 
                    itp2_params["accrual_rate_over_30_years"] * (final_years_of_service - 30) / 30
                )
            
            # Cap the percentage at the maximum (varies by salary level)
            defined_benefit_percentage = min(defined_benefit_percentage, 0.70)  # Max 70%
            
            # Calculate defined benefit amount
            if final_salary <= 7.5 * itp2_params["price_base_amount"]:
                defined_benefit = final_salary * defined_benefit_percentage
            else:
                # Different percentages for different salary brackets
                defined_benefit = (
                    7.5 * itp2_params["price_base_amount"] * defined_benefit_percentage +
                    (min(final_salary, 20 * itp2_params["price_base_amount"]) - 
                     7.5 * itp2_params["price_base_amount"]) * defined_benefit_percentage * 0.65 +
                    (min(final_salary, 30 * itp2_params["price_base_amount"]) - 
                     20 * itp2_params["price_base_amount"]) * defined_benefit_percentage * 0.325
                )
            
            # Calculate ITPK future value
            itpk_future_value = 0
            for year in range(years_until_retirement):
                # Add this year's contribution
                itpk_future_value += itpk_contribution
                # Apply return rate and admin fee
                itpk_future_value *= (1 + return_rate - itp2_params["admin_fee_percentage"])
            
            # Calculate ITPK monthly pension
            # Simplified: divide by 20 years (240 months) of retirement
            itpk_monthly_pension = itpk_future_value / 240
            
            # Calculate total monthly pension
            monthly_pension = defined_benefit / 12 + itpk_monthly_pension
            
            return {
                "success": True,
                "monthly_pension": round(monthly_pension, 2),
                "defined_benefit_monthly": round(defined_benefit / 12, 2),
                "itpk_monthly": round(itpk_monthly_pension, 2),
                "defined_benefit_percentage": round(defined_benefit_percentage * 100, 2),
                "itpk_capital": round(itpk_future_value, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "age": age,
                    "years_of_service": years_of_service,
                    "years_until_retirement": years_until_retirement,
                    "return_rate": return_rate,
                    "itp2_parameters": itp2_params
                }
            }
        
        elif calculation_type == "contribution_calculation":
            return {
                "success": True,
                "itpk_annual_contribution": round(itpk_contribution, 2),
                "itpk_monthly_contribution": round(itpk_contribution / 12, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "itp2_parameters": itp2_params
                }
            }
        
        else:
            raise ValueError(f"Unsupported calculation type for ITP2: {calculation_type}")
    
    def _calculate_saflo(self, calculation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform SAF-LO pension calculation.
        
        Args:
            calculation_type: Type of calculation to perform.
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        # Get SAF-LO parameters
        saflo_params = self.get_calculation_parameters("SAF-LO")
        
        # Default parameters if none are stored
        if not saflo_params:
            saflo_params = {
                "contribution_rate": 0.045,            # 4.5% of salary
                "income_base_amount": 71000,           # SEK per year (2023)
                "default_return_rate": 0.03,           # 3% annual return
                "admin_fee_percentage": 0.003          # 0.3% annual admin fee
            }
        
        # Extract required parameters
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 25)
        years_until_retirement = parameters.get("years_until_retirement", 65 - age)
        return_rate = parameters.get("return_rate", saflo_params["default_return_rate"])
        
        # Calculate annual salary
        annual_salary = monthly_salary * 12
        
        # Calculate annual contribution
        annual_contribution = annual_salary * saflo_params["contribution_rate"]
        
        if calculation_type == "retirement_estimate":
            # Calculate future value
            future_value = 0
            for year in range(years_until_retirement):
                # Add this year's contribution
                future_value += annual_contribution
                # Apply return rate and admin fee
                future_value *= (1 + return_rate - saflo_params["admin_fee_percentage"])
            
            # Calculate monthly pension
            # Simplified: divide by 20 years (240 months) of retirement
            monthly_pension = future_value / 240
            
            return {
                "success": True,
                "monthly_pension": round(monthly_pension, 2),
                "total_pension_capital": round(future_value, 2),
                "annual_contribution": round(annual_contribution, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "age": age,
                    "years_until_retirement": years_until_retirement,
                    "return_rate": return_rate,
                    "saflo_parameters": saflo_params
                }
            }
        
        elif calculation_type == "contribution_calculation":
            return {
                "success": True,
                "annual_contribution": round(annual_contribution, 2),
                "monthly_contribution": round(annual_contribution / 12, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "saflo_parameters": saflo_params
                }
            }
        
        else:
            raise ValueError(f"Unsupported calculation type for SAF-LO: {calculation_type}")
    
    def _calculate_pa16(self, calculation_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform PA16 pension calculation.
        
        Args:
            calculation_type: Type of calculation to perform.
            parameters: Parameters for the calculation.
            
        Returns:
            Dict[str, Any]: Calculation results.
        """
        # Get PA16 parameters
        pa16_params = self.get_calculation_parameters("PA16")
        
        # Default parameters if none are stored
        if not pa16_params:
            pa16_params = {
                "contribution_rate_below_cap": 0.045,  # 4.5% below income cap
                "contribution_rate_above_cap": 0.30,   # 30% above income cap
                "income_cap_base_amount": 7.5,         # 7.5 income base amounts
                "income_base_amount": 71000,           # SEK per year (2023)
                "default_return_rate": 0.03,           # 3% annual return
                "admin_fee_percentage": 0.003          # 0.3% annual admin fee
            }
        
        # Extract required parameters
        monthly_salary = parameters.get("monthly_salary", 0)
        age = parameters.get("age", 25)
        years_until_retirement = parameters.get("years_until_retirement", 65 - age)
        return_rate = parameters.get("return_rate", pa16_params["default_return_rate"])
        
        # Calculate annual salary
        annual_salary = monthly_salary * 12
        
        # Calculate income cap
        income_cap = pa16_params["income_cap_base_amount"] * pa16_params["income_base_amount"]
        
        # Calculate contributions
        if annual_salary <= income_cap:
            annual_contribution = annual_salary * pa16_params["contribution_rate_below_cap"]
            contribution_below_cap = annual_contribution
            contribution_above_cap = 0
        else:
            contribution_below_cap = income_cap * pa16_params["contribution_rate_below_cap"]
            contribution_above_cap = (annual_salary - income_cap) * pa16_params["contribution_rate_above_cap"]
            annual_contribution = contribution_below_cap + contribution_above_cap
        
        if calculation_type == "retirement_estimate":
            # Calculate future value
            future_value = 0
            for year in range(years_until_retirement):
                # Add this year's contribution
                future_value += annual_contribution
                # Apply return rate and admin fee
                future_value *= (1 + return_rate - pa16_params["admin_fee_percentage"])
            
            # Calculate monthly pension
            # Simplified: divide by 20 years (240 months) of retirement
            monthly_pension = future_value / 240
            
            return {
                "success": True,
                "monthly_pension": round(monthly_pension, 2),
                "total_pension_capital": round(future_value, 2),
                "annual_contribution": round(annual_contribution, 2),
                "contribution_below_cap": round(contribution_below_cap, 2),
                "contribution_above_cap": round(contribution_above_cap, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "age": age,
                    "years_until_retirement": years_until_retirement,
                    "return_rate": return_rate,
                    "pa16_parameters": pa16_params
                }
            }
        
        elif calculation_type == "contribution_calculation":
            return {
                "success": True,
                "annual_contribution": round(annual_contribution, 2),
                "monthly_contribution": round(annual_contribution / 12, 2),
                "contribution_below_cap": round(contribution_below_cap, 2),
                "contribution_above_cap": round(contribution_above_cap, 2),
                "calculation_type": calculation_type,
                "parameters_used": {
                    "monthly_salary": monthly_salary,
                    "pa16_parameters": pa16_params
                }
            }
        
        else:
            raise ValueError(f"Unsupported calculation type for PA16: {calculation_type}")
