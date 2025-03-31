# src/agents/verifier_agent.py
import logging
from src.reasoning.response_verifier import ResponseVerifier

logger = logging.getLogger(__name__)

class VerifierAgent:
    def __init__(self):
        self.verifier = ResponseVerifier()

    def verify(self, state):
        """
        Check if 'draft_answer' in state is good enough.
        If good, return route='good', else route='bad'.
        """
        question = state.get("question", "")
        draft_answer = state.get("draft_answer", "")
        retrieved_docs = [doc.page_content for doc in state.get("retrieved_docs", [])]

        logger.info("[verify_answer] Verifying draft_answer quality...")

        is_sufficient = self._custom_check(question, draft_answer, retrieved_docs)

        logger.info(f"[verify_answer] is_sufficient={is_sufficient}")
        route = "good" if is_sufficient else "bad"

        return {
            **state,
            "route": route
        }


    def route_verification(self, state):
        # This is the function used in add_conditional_edges() for deciding next node
        return state.get("route", "bad")


    def _custom_check(self, question, answer, retrieved_docs):
        return self.verifier.is_response_sufficient(question, answer, retrieved_docs)


