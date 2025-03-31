from typing import Optional,Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import re
import logging
from typing import List

logger = logging.getLogger('reasoning_utils')

class AgreementDetector:
    """
    Detects which pension agreement the user is referring to based on input text.
    """

    def __init__(self):
        self.known_agreements = ["PA16", "SKR2023", "ITP1", "ITP2", "KAP-KL"]

    def detect(self, message: str) -> Optional[str]:
        """
        Scan user message and return the matched agreement if found.
        """
        message_lower = message.lower()
        for agreement in self.known_agreements:
            if agreement.lower() in message_lower:
                return agreement

        # Try fallback with fuzzy matching (e.g. 'pa 16' with space)
        if "pa 16" in message_lower:
            return "PA16"

        return None


# Example usage (can be removed in production):
if __name__ == "__main__":
    detector = AgreementDetector()
    test_input = "Vad gäller efterlevnadsskydd i PA16 avdelning 2?"
    print("🔍 Agreement detected:", detector.detect(test_input))

#------------------------------------------------

class IntentClassifier:
    """Classifies the user's intent based on their question."""

    def __init__(self):
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0)

    def classify_intent(self, question: str) -> Literal[
        "general_question", "personal_pension", "agreement_lookup", "ambiguous"]:
        """Categorize the type of user question."""

        system_prompt = """
        Du är en AI-assistent som hjälper till att klassificera frågor om pensioner.
        Klassificera frågan i en av följande kategorier:
        - general_question: En allmän fråga om pensioner eller pensionssystem.
        - personal_pension: Användaren frågar om sin egen pension eller ger personlig info.
        - agreement_lookup: Frågan gäller innehållet i ett specifikt avtal.
        - ambiguous: Det är oklart vad användaren menar eller den passar inte in i kategorierna.

        Svara enbart med kategorinamn (t.ex. personal_pension) utan förklaringar.
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question)
        ]

        response = self.llm.invoke(messages)
        return response.content.strip()

#------------------------------------------------


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
