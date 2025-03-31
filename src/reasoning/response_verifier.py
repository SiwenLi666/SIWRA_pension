import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class ResponseVerifier:
    """
    Uses GPT-4 to evaluate if the AI-generated answer addresses the user's question.
    """

    def __init__(self, model_name="gpt-4", temperature=0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)

    def is_response_sufficient(self, question: str, answer: str, retrieved_docs: List[str]) -> bool:
        """
        Uses an LLM to judge whether the generated answer is relevant and sufficient.
        """
        context = "\n\n".join(retrieved_docs[:3]) if retrieved_docs else "Inga dokument hittades."
        prompt = (
            "Bedöm om följande svar besvarar frågan på ett tydligt och relevant sätt, "
            "baserat på tillgänglig kontext. Svara endast med 'JA' eller 'NEJ'."
        )
        full_input = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Fråga: {question}\n\nSvar: {answer}\n\nKontext:\n{context}")
        ]

        try:
            result = self.llm.invoke(full_input)
            decision = result.content.strip().lower()
            logger.info(f"[ResponseVerifier] LLM decision: {decision}")
            return "ja" in decision
        except Exception as e:
            logger.error(f"❌ LLM verification failed: {str(e)}")
            return False
