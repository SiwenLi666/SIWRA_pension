# src/agents/answer_agent.py
import logging
import json
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.utils.config import SUMMARY_JSON_PATH

logger = logging.getLogger(__name__)

class AnswerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.3, model="gpt-4")

    def generate(self, state):
        question = state.get("question", "")
        logger.info("[generate_answer] Generating answer from summary.json via LLM...")

        try:
            with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load summary.json: {e}")
            return {**state, "draft_answer": "Tyvärr, jag kunde inte ladda summeringsfilen."}

        all_summaries = []
        for entry in summary_data.get("agreements", []):
            for doc in entry.get("documents", []):
                text = doc.get("summary", "")
                if text:
                    all_summaries.append(text)

        if not all_summaries:
            logger.warning("⚠️ No summaries found in summary.json")
            return {**state, "draft_answer": "Tyvärr, inga summeringar fanns tillgängliga."}

        prompt = [
            SystemMessage(content="Du är en pensionsrådgivare som ska hjälpa användaren."),
            HumanMessage(content=(
                f"Här är en fråga: '{question}'\n\n"
                f"Här är summeringar av olika dokument:\n\n{chr(10).join(all_summaries)}\n\n"
                "Om du kan besvara frågan baserat på summeringarna ovan, gör det."
                " Om det inte finns tillräcklig information för att ge ett meningsfullt svar, svara exakt: 'nej'."
            ))
        ]

        try:
            response = self.llm.invoke(prompt).content.strip()
            logger.info(f"[generate_answer] LLM response: {response[:100]}...")
            return {**state, "draft_answer": response}
        except Exception as e:
            logger.error(f"❌ LLM failed to generate answer: {e}")
            return {**state, "draft_answer": "Tyvärr, ett fel uppstod när jag försökte besvara frågan."}
