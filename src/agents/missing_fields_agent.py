# src/agents/missing_fields_agent.py
import logging
from langchain_core.messages import SystemMessage
from src.graph.state import GraphState, AgentState, UserProfile

logger = logging.getLogger(__name__)

class MissingFieldsAgent:
    def ask(self, state):
        """
        1) We have a final 'draft_answer'
        2) Check which user profile fields are missing
        3) Append a polite question about them to the final answer
        4) Return final 'response' to user
        """
        user_profile = state.get("user_profile", {})
        required_fields = UserProfile.required_fields()
        missing = [
            f for f in required_fields 
            if f not in user_profile or user_profile[f] is None
        ]

        # Merge final answer + optional "missing fields" prompt
        final_answer = state.get("draft_answer", "Tyvärr har jag inget svar.")
        if missing:
            logger.info("[ask_for_missing_fields] Adding follow-up question for missing fields.")
            followup = f"\n\nBy the way, I'd like to know your {', '.join(missing)} " \
                       "to give more precise guidance next time."
        else:
            logger.info("[ask_for_missing_fields] No missing fields to ask about.")
            followup = ""

        full_response = final_answer + followup

        # Return the final conversation outcome
        return GraphState(
            **state,
            response=full_response,
            state=AgentState.FINISHED.value
        )
