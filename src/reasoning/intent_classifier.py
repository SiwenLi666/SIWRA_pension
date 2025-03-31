from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

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
