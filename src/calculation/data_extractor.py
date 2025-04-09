"""
Pension Data Extraction module.

This module provides functionality for extracting calculation parameters
from pension agreement documents.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
import os
import json
from pathlib import Path

from src.utils.config import BASE_DIR
# Fixed import path for DocumentProcessor
from src.retriever.document_processor import DocumentProcessor

logger = logging.getLogger('data_extractor')

class PensionDataExtractor:
    """
    Extracts calculation parameters from pension agreement documents.
    
    This class provides methods for identifying and extracting numerical parameters,
    percentages, thresholds, and other calculation-relevant data from pension agreements.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the PensionDataExtractor.
        
        Args:
            data_dir: Directory to store extracted data. Defaults to BASE_DIR/data/extracted_parameters.
        """
        if data_dir is None:
            self.data_dir = os.path.join(BASE_DIR, "data", "extracted_parameters")
        else:
            self.data_dir = data_dir
            
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Path to the extracted parameters database
        self.parameters_db_path = os.path.join(self.data_dir, "extracted_parameters.json")
        
        # Load or create extracted parameters database
        self.parameters_db = self._load_or_create_db(self.parameters_db_path)
        
        # Initialize document processor for accessing documents
        self.doc_processor = DocumentProcessor()
        
        # Define regex patterns for parameter extraction
        self.patterns = {
            "percentage": r"(\d+(?:\.\d+)?)(?:\s*)?%",
            "money_amount": r"(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:kr|kronor|SEK)",
            "income_base_amount": r"(\d+(?:\.\d+)?)\s*(?:income base amounts|inkomstbasbelopp)",
            "price_base_amount": r"(\d+(?:\.\d+)?)\s*(?:price base amounts|prisbasbelopp)",
            "age": r"(?:age|ålder)\s*(\d+)",
            "year": r"(?:year|år)\s*(\d{4})",
            "contribution_rate": r"contribution(?:\s*rate)?\s*(?:of|is|på)?\s*(\d+(?:\.\d+)?)(?:\s*)?%"
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
    
    def extract_parameters(self, agreement_type: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Extract calculation parameters from documents for a specific agreement type.
        
        Args:
            agreement_type: Type of pension agreement (ITP1, ITP2, SAF-LO, PA16).
            force_refresh: If True, force re-extraction even if parameters exist.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        # Check if parameters already exist and force_refresh is False
        if agreement_type in self.parameters_db and not force_refresh:
            return self.parameters_db[agreement_type]
        
        # Load documents for the agreement type
        documents = self.doc_processor.load_documents(agreement_type)
        
        if not documents:
            logger.warning(f"No documents found for agreement type: {agreement_type}")
            return {}
        
        # Initialize parameters dictionary
        parameters = {}
        
        # Extract parameters from each document
        for doc in documents:
            # Extract text content
            text = doc.page_content
            
            # Extract parameters based on agreement type
            if agreement_type == "ITP1":
                extracted = self._extract_itp1_parameters(text)
            elif agreement_type == "ITP2":
                extracted = self._extract_itp2_parameters(text)
            elif agreement_type == "SAF-LO":
                extracted = self._extract_saflo_parameters(text)
            elif agreement_type == "PA16":
                extracted = self._extract_pa16_parameters(text)
            else:
                logger.warning(f"Unsupported agreement type: {agreement_type}")
                extracted = {}
            
            # Update parameters with extracted values
            parameters.update(extracted)
        
        # Store extracted parameters
        self.parameters_db[agreement_type] = parameters
        self._save_db(self.parameters_db, self.parameters_db_path)
        
        return parameters
    
    def _extract_pattern(self, text: str, pattern_key: str) -> List[str]:
        """
        Extract values matching a specific pattern from text.
        
        Args:
            text: Text to extract from.
            pattern_key: Key of the pattern to use.
            
        Returns:
            List[str]: List of extracted values.
        """
        pattern = self.patterns.get(pattern_key)
        if not pattern:
            return []
        
        matches = re.findall(pattern, text, re.IGNORECASE)
        return matches
    
    def _extract_itp1_parameters(self, text: str) -> Dict[str, Any]:
        """
        Extract ITP1 specific parameters from text.
        
        Args:
            text: Text to extract from.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        parameters = {}
        
        # Extract contribution rates
        contribution_rates = self._extract_pattern(text, "contribution_rate")
        if contribution_rates:
            # Look for specific contribution rate patterns
            below_cap_pattern = r"below.*?(\d+(?:\.\d+)?)(?:\s*)?%"
            above_cap_pattern = r"above.*?(\d+(?:\.\d+)?)(?:\s*)?%"
            
            below_matches = re.findall(below_cap_pattern, text, re.IGNORECASE)
            above_matches = re.findall(above_cap_pattern, text, re.IGNORECASE)
            
            if below_matches:
                parameters["contribution_rate_below_cap"] = float(below_matches[0]) / 100
            
            if above_matches:
                parameters["contribution_rate_above_cap"] = float(above_matches[0]) / 100
        
        # Extract income base amount
        income_base_amounts = self._extract_pattern(text, "income_base_amount")
        if income_base_amounts:
            parameters["income_cap_base_amount"] = float(income_base_amounts[0])
        
        # Extract money amounts
        money_amounts = self._extract_pattern(text, "money_amount")
        if money_amounts:
            # Try to identify which amount is the income base amount
            income_base_context = r"income\s*base\s*amount.*?(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:kr|kronor|SEK)"
            income_base_matches = re.findall(income_base_context, text, re.IGNORECASE)
            
            if income_base_matches:
                # Remove commas and convert to float
                amount = income_base_matches[0].replace(',', '')
                parameters["income_base_amount"] = float(amount)
        
        # Extract admin fees
        admin_fee_pattern = r"(?:admin|administration)(?:\s*fee)?\s*(?:of|is|på)?\s*(\d+(?:\.\d+)?)(?:\s*)?%"
        admin_fee_matches = re.findall(admin_fee_pattern, text, re.IGNORECASE)
        
        if admin_fee_matches:
            parameters["admin_fee_percentage"] = float(admin_fee_matches[0]) / 100
        
        return parameters
    
    def _extract_itp2_parameters(self, text: str) -> Dict[str, Any]:
        """
        Extract ITP2 specific parameters from text.
        
        Args:
            text: Text to extract from.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        parameters = {}
        
        # Extract ITPK contribution rate
        itpk_pattern = r"ITPK(?:\s*contribution)?\s*(?:rate|is)?\s*(\d+(?:\.\d+)?)(?:\s*)?%"
        itpk_matches = re.findall(itpk_pattern, text, re.IGNORECASE)
        
        if itpk_matches:
            parameters["itpk_contribution_rate"] = float(itpk_matches[0]) / 100
        
        # Extract income base amount
        income_base_amounts = self._extract_pattern(text, "income_base_amount")
        if income_base_amounts:
            parameters["income_cap_base_amount"] = float(income_base_amounts[0])
        
        # Extract price base amount
        price_base_amounts = self._extract_pattern(text, "price_base_amount")
        if price_base_amounts:
            parameters["price_base_amount_multiplier"] = float(price_base_amounts[0])
        
        # Extract accrual rates
        accrual_pattern_30 = r"(?:accrual|earning)(?:\s*rate)?\s*(?:for|up to)?\s*30\s*years.*?(\d+(?:\.\d+)?)(?:\s*)?%"
        accrual_pattern_over_30 = r"(?:accrual|earning)(?:\s*rate)?\s*(?:for|over)?\s*30\s*years.*?(\d+(?:\.\d+)?)(?:\s*)?%"
        
        accrual_30_matches = re.findall(accrual_pattern_30, text, re.IGNORECASE)
        accrual_over_30_matches = re.findall(accrual_pattern_over_30, text, re.IGNORECASE)
        
        if accrual_30_matches:
            parameters["accrual_rate_30_years"] = float(accrual_30_matches[0]) / 100
        
        if accrual_over_30_matches:
            parameters["accrual_rate_over_30_years"] = float(accrual_over_30_matches[0]) / 100
        
        # Extract money amounts
        money_amounts = self._extract_pattern(text, "money_amount")
        if money_amounts:
            # Try to identify which amount is the income base amount
            income_base_context = r"income\s*base\s*amount.*?(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:kr|kronor|SEK)"
            income_base_matches = re.findall(income_base_context, text, re.IGNORECASE)
            
            if income_base_matches:
                # Remove commas and convert to float
                amount = income_base_matches[0].replace(',', '')
                parameters["income_base_amount"] = float(amount)
            
            # Try to identify which amount is the price base amount
            price_base_context = r"price\s*base\s*amount.*?(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:kr|kronor|SEK)"
            price_base_matches = re.findall(price_base_context, text, re.IGNORECASE)
            
            if price_base_matches:
                # Remove commas and convert to float
                amount = price_base_matches[0].replace(',', '')
                parameters["price_base_amount"] = float(amount)
        
        return parameters
    
    def _extract_saflo_parameters(self, text: str) -> Dict[str, Any]:
        """
        Extract SAF-LO specific parameters from text.
        
        Args:
            text: Text to extract from.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        parameters = {}
        
        # Extract contribution rate
        contribution_rates = self._extract_pattern(text, "contribution_rate")
        if contribution_rates:
            parameters["contribution_rate"] = float(contribution_rates[0]) / 100
        
        # Extract money amounts
        money_amounts = self._extract_pattern(text, "money_amount")
        if money_amounts:
            # Try to identify which amount is the income base amount
            income_base_context = r"income\s*base\s*amount.*?(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:kr|kronor|SEK)"
            income_base_matches = re.findall(income_base_context, text, re.IGNORECASE)
            
            if income_base_matches:
                # Remove commas and convert to float
                amount = income_base_matches[0].replace(',', '')
                parameters["income_base_amount"] = float(amount)
        
        # Extract admin fees
        admin_fee_pattern = r"(?:admin|administration)(?:\s*fee)?\s*(?:of|is|på)?\s*(\d+(?:\.\d+)?)(?:\s*)?%"
        admin_fee_matches = re.findall(admin_fee_pattern, text, re.IGNORECASE)
        
        if admin_fee_matches:
            parameters["admin_fee_percentage"] = float(admin_fee_matches[0]) / 100
        
        return parameters
    
    def _extract_pa16_parameters(self, text: str) -> Dict[str, Any]:
        """
        Extract PA16 specific parameters from text.
        
        Args:
            text: Text to extract from.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        parameters = {}
        
        # Extract contribution rates
        contribution_rates = self._extract_pattern(text, "contribution_rate")
        if contribution_rates:
            # Look for specific contribution rate patterns
            below_cap_pattern = r"below.*?(\d+(?:\.\d+)?)(?:\s*)?%"
            above_cap_pattern = r"above.*?(\d+(?:\.\d+)?)(?:\s*)?%"
            
            below_matches = re.findall(below_cap_pattern, text, re.IGNORECASE)
            above_matches = re.findall(above_cap_pattern, text, re.IGNORECASE)
            
            if below_matches:
                parameters["contribution_rate_below_cap"] = float(below_matches[0]) / 100
            
            if above_matches:
                parameters["contribution_rate_above_cap"] = float(above_matches[0]) / 100
        
        # Extract income base amount
        income_base_amounts = self._extract_pattern(text, "income_base_amount")
        if income_base_amounts:
            parameters["income_cap_base_amount"] = float(income_base_amounts[0])
        
        # Extract money amounts
        money_amounts = self._extract_pattern(text, "money_amount")
        if money_amounts:
            # Try to identify which amount is the income base amount
            income_base_context = r"income\s*base\s*amount.*?(\d+(?:\,\d+)?(?:\.\d+)?)\s*(?:kr|kronor|SEK)"
            income_base_matches = re.findall(income_base_context, text, re.IGNORECASE)
            
            if income_base_matches:
                # Remove commas and convert to float
                amount = income_base_matches[0].replace(',', '')
                parameters["income_base_amount"] = float(amount)
        
        # Extract admin fees
        admin_fee_pattern = r"(?:admin|administration)(?:\s*fee)?\s*(?:of|is|på)?\s*(\d+(?:\.\d+)?)(?:\s*)?%"
        admin_fee_matches = re.findall(admin_fee_pattern, text, re.IGNORECASE)
        
        if admin_fee_matches:
            parameters["admin_fee_percentage"] = float(admin_fee_matches[0]) / 100
        
        return parameters
    
    def detect_parameter_changes(self, agreement_type: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect changes in parameters by comparing stored parameters with freshly extracted ones.
        
        Args:
            agreement_type: Type of pension agreement.
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (has_changes, changed_parameters)
        """
        # Get stored parameters
        stored_parameters = self.parameters_db.get(agreement_type, {})
        
        # Extract fresh parameters
        fresh_parameters = self.extract_parameters(agreement_type, force_refresh=True)
        
        # Compare parameters
        changed_parameters = {}
        for key, fresh_value in fresh_parameters.items():
            if key in stored_parameters:
                stored_value = stored_parameters[key]
                if stored_value != fresh_value:
                    changed_parameters[key] = {
                        "old_value": stored_value,
                        "new_value": fresh_value
                    }
            else:
                changed_parameters[key] = {
                    "old_value": None,
                    "new_value": fresh_value
                }
        
        has_changes = len(changed_parameters) > 0
        
        return has_changes, changed_parameters
    
    def get_all_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all extracted parameters for all agreement types.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of parameters by agreement type.
        """
        return self.parameters_db
    
    def get_parameters(self, agreement_type: str) -> Dict[str, Any]:
        """
        Get extracted parameters for a specific agreement type.
        
        Args:
            agreement_type: Type of pension agreement.
            
        Returns:
            Dict[str, Any]: Extracted parameters.
        """
        return self.parameters_db.get(agreement_type, {})
