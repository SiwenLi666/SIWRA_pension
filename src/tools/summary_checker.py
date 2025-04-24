import logging
import json
import os
from typing import Dict, Any, Optional
from src.tools.base_tool import BaseTool


logger = logging.getLogger(__name__)

class SummaryCheckerTool(BaseTool):
    """Tool for checking pre-generated summaries"""
    
    def __init__(self):
        super().__init__(
            name="summary_checker",
            description="Checks for pre-generated summaries that match the question"
        )
        self.summaries_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                          "data", "summaries")
        # Create summaries directory if it doesn't exist
        if not os.path.exists(self.summaries_dir):
            try:
                os.makedirs(self.summaries_dir, exist_ok=True)
                logger.info(f"Created summaries directory: {self.summaries_dir}")
                # Create a sample summary file
                self._create_sample_summary()
            except Exception as e:
                logger.error(f"Failed to create summaries directory: {str(e)}")
    
    def can_handle(self, question: str, state: Dict[str, Any]) -> bool:
        """
        Determine if this tool can handle the given question by checking if a matching
        summary exists
        """
        summary = self._find_matching_summary(question)
        return summary is not None
    
    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        CONTRACT: Every return path MUST set state['response'] to a user-facing string.
        Return the pre-generated summary that matches the question.
        """
        logger.info("Running summary checker tool")
        summary = self._find_matching_summary(question)
        if summary:
            state["response"] = summary
            state["response_source"] = "summary_json"
            logger.info(f"Returning response: {state.get('response')}")
            return state
        else:
            # This shouldn't happen if can_handle returned True, but just in case
            state["response"] = "Tyvärr kunde jag inte hitta någon sammanfattning som matchar din fråga."
            logger.info(f"Returning response: {state.get('response')}")
            return state

    
    def _create_sample_summary(self):
        """Create a sample summary file to demonstrate the format"""
        try:
            sample_summary = {
                "title": "Tillgängliga pensionsavtal",
                "keywords": ["avtal", "pensionsavtal", "överenskommelse", "vilka avtal"],
                "content": "Jag har information om följande pensionsavtal: PA16 (för statligt anställda) och SKR2023 (för kommunalt anställda)."
            }
            
            sample_path = os.path.join(self.summaries_dir, "available_agreements.json")
            with open(sample_path, 'w', encoding='utf-8') as f:
                json.dump(sample_summary, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Created sample summary file: {sample_path}")
        except Exception as e:
            logger.error(f"Failed to create sample summary: {str(e)}")
    
    def _find_matching_summary(self, question: str) -> Optional[str]:
        """Find a summary that matches the question"""
        try:
            # Check if summaries directory exists
            if not os.path.exists(self.summaries_dir):
                logger.warning(f"Summaries directory not found: {self.summaries_dir}")
                try:
                    os.makedirs(self.summaries_dir, exist_ok=True)
                    logger.info(f"Created summaries directory: {self.summaries_dir}")
                except Exception as e:
                    logger.error(f"Failed to create summaries directory: {str(e)}")
                return None
            
            # Simple keyword matching for now - could be enhanced with embeddings
            question_lower = question.lower()
            
            # Look through all summary files
            for filename in os.listdir(self.summaries_dir):
                if not filename.endswith('.json'):
                    continue
                    
                file_path = os.path.join(self.summaries_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        
                    # Check if any keywords match
                    keywords = summary_data.get("keywords", [])
                    if any(keyword.lower() in question_lower for keyword in keywords):
                        logger.info(f"Found matching summary: {filename}")
                        return summary_data.get("content", "")
                        
                except Exception as e:
                    logger.error(f"Error reading summary file {filename}: {str(e)}")
            
            # No matching summary found
            logger.info("No matching summary found")
            return None
            
        except Exception as e:
            logger.error(f"Error in find_matching_summary: {str(e)}")
            return None
