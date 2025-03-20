"""
Error analysis and handling agent for the pension advisor system.
"""
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import logging
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .presentation_db import PensionAnalysisManager  # Import the manager

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    MISSING_INFO = "missing_info"
    CALCULATION_ERROR = "calculation_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"

@dataclass
class ErrorAnalysis:
    error_type: ErrorType
    description: str
    missing_factors: List[str] = None  # Change to str if you just want names
    can_recover: bool = False
    next_action: str = None
    user_message: str = None

class ErrorAnalyzer:
    def __init__(self):
        """Initialize the error analyzer"""
        self.llm = ChatOpenAI(
            temperature=0.1,  # Low temperature for consistent analysis
            model="gpt-4"  # Using GPT-4 for better error understanding
        )
        self.presentation_manager = PensionAnalysisManager()  # Create an instance of the manager
        
    def _prepare_error_prompt(self, error: str, state: Dict) -> str:
        """Prepare a prompt for error analysis"""
        prompt = f"""You are an error analysis expert for a pension advisory system.
        Analyze this error and context to determine the type and required actions.
        
        Error: {error}
        
        Current State:
        - User Profile: {state.get('user_profile', {})}
        - Current Focus: {state.get('current_focus', 'unknown')}
        - Last Action: {state.get('last_action', 'unknown')}
        
        Classify this error as one of:
        1. MISSING_INFO: Missing or incomplete user information
        2. CALCULATION_ERROR: Error in pension calculations
        3. SYSTEM_ERROR: Technical system error
        4. UNKNOWN: Cannot determine error type
        
        Respond in JSON format with:
        {{
            "error_type": "type from above",
            "description": "detailed error description",
            "can_recover": true/false,
            "next_action": "recommended next action",
            "user_message": "friendly message to show user"
        }}
        """
        return prompt

    def analyze_error(self, error: str, state: Dict) -> ErrorAnalysis:
        """Analyze an error and determine the best course of action"""
        try:
            # First, check if it's clearly a missing info error
            if "required field" in error.lower() or "missing" in error.lower():
                missing_factors = self.presentation_manager.get_missing_factors(state.get('user_profile', {}))
                if missing_factors:
                    return ErrorAnalysis(
                        error_type=ErrorType.MISSING_INFO,
                        description="Missing required user information",
                        missing_factors=missing_factors,
                        can_recover=True,
                        next_action="gather_missing_info",
                        user_message="Jag behöver lite mer information för att kunna hjälpa dig bättre."
                    )
            
            # Check if this is the first interaction (no conversation history)
            if not state.get('conversation_history', []):
                # For the first interaction, provide a friendly welcome message instead of an error
                return ErrorAnalysis(
                    error_type=ErrorType.MISSING_INFO,
                    description="First interaction, no error to show user",
                    missing_factors=[],
                    can_recover=True,
                    next_action="gather_info",
                    user_message="Hej! Jag är din pensionsrådgivare. Hur kan jag hjälpa dig idag? Du kan fråga mig om din pension eller berätta lite om din situation så jag kan ge dig personliga råd."
                )
            
            # Use LLM for more complex error analysis
            messages = [
                SystemMessage(content="You are an error analysis expert."),
                HumanMessage(content=self._prepare_error_prompt(error, state))
            ]
            
            response = self.llm.invoke(messages)
            analysis = response.content
            
            # Parse the analysis
            if "MISSING_INFO" in analysis:
                missing_factors = self.presentation_manager.get_missing_factors(state.get('user_profile', {}))
                return ErrorAnalysis(
                    error_type=ErrorType.MISSING_INFO,
                    description=analysis.get('description', ''),
                    missing_factors=missing_factors,
                    can_recover=True,
                    next_action="gather_missing_info",
                    user_message=analysis.get('user_message', '')
                )
            elif "CALCULATION_ERROR" in analysis:
                return ErrorAnalysis(
                    error_type=ErrorType.CALCULATION_ERROR,
                    description=analysis.get('description', ''),
                    can_recover=True,
                    next_action="retry_calculation",
                    user_message="Det uppstod ett fel i beräkningen. Jag försöker räkna om."
                )
            elif "SYSTEM_ERROR" in analysis:
                logger.error(f"System error detected: {error}")
                return ErrorAnalysis(
                    error_type=ErrorType.SYSTEM_ERROR,
                    description=analysis.get('description', ''),
                    can_recover=False,
                    next_action="end",
                    user_message="Tyvärr uppstod ett tekniskt fel. Vårt team har notifierats."
                )
            else:
                logger.error(f"Unknown error: {error}")
                return ErrorAnalysis(
                    error_type=ErrorType.UNKNOWN,
                    description="Unable to classify error",
                    can_recover=False,
                    next_action="end",
                    user_message="Tyvärr uppstod ett oväntat fel. Försök gärna igen senare."
                )
                
        except Exception as e:
            logger.exception("Error in error analysis")
            return ErrorAnalysis(
                error_type=ErrorType.UNKNOWN,
                description=f"Error analysis failed: {str(e)}",
                can_recover=False,
                next_action="end",
                user_message="Tyvärr uppstod ett fel. Vårt team har notifierats."
            )
    
    def update_presentation_db(self, error_analysis: ErrorAnalysis, state: Dict):
        """Update the presentation database based on error analysis"""
        if error_analysis.error_type == ErrorType.MISSING_INFO:
            # Update frequency of missing factors
            for factor in error_analysis.missing_factors:
                self.presentation_manager.increment_factor_frequency(factor.name)
            
            # If we have a conversation history, try to extract new question templates
            if state.get('conversation_history'):
                self._extract_question_patterns(state['conversation_history'])
    
    def _extract_question_patterns(self, conversation_history: List[Dict]):
        """Extract useful question patterns from successful conversations"""
        try:
            # Prepare conversation for analysis
            conversation_text = "\n".join([f"{'Bot' if msg['role'] == 'assistant' else 'User'}: {msg['content']}" for msg in conversation_history])
            
            # Ask LLM to identify useful question patterns
            messages = [
                SystemMessage(content="Identify effective question patterns from this conversation."),
                HumanMessage(content=f"""
                Analyze this conversation and identify effective questions that successfully
                elicited important information. Format each as:
                factor: question template
                
                Conversation:
                {conversation_text}
                """)
            ]
            
            response = self.llm.invoke(messages)
            patterns = response.content.split('\n')
            
            # Add new patterns to database
            for pattern in patterns:
                if ':' in pattern:
                    factor, template = pattern.split(':', 1)
                    self.presentation_manager.add_question_template(factor.strip().lower(), template.strip())
                    
        except Exception as e:
            logger.error(f"Failed to extract question patterns: {e}")

# Global instance
error_analyzer = ErrorAnalyzer()