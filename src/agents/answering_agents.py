# src/agents/answering_agent.py
import logging
import json
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.utils.config import SUMMARY_JSON_PATH
from src.retriever.retriever_tool import RetrieverTool
from src.reasoning.reasoning_utils import ResponseVerifier
from src.graph.state import GraphState, AgentState, UserProfile

logger = logging.getLogger('answering_agents')


class AnswerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.3, model="gpt-4")

    def generate(self, state):
        state["status"] = "🔎 Läser summeringar från dokument..."
        logger.info(state["status"])

        question =  state.get("question", "")
        logger.info("[generate_answer] Generating answer from summary.json via LLM...")

        try:
            with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load summary.json: {e}")
            state["draft_answer"] = "Tyvärr, jag kunde inte ladda summeringsfilen."
            return state


        structured_summary = []
        for entry in summary_data.get("agreements", []):
            agreement_name = entry.get("name", "Okänt avtal")
            docs = entry.get("documents", [])
            doc_summaries = [doc.get("summary", "") for doc in docs if doc.get("summary")]
            structured_summary.append(f"Avtal: {agreement_name}\n" + "\n".join(f"- {s}" for s in doc_summaries))


        if not structured_summary:
            logger.warning("⚠️ No summaries found in summary.json")
            state["draft_answer"] = "Tyvärr, inga summeringar fanns tillgängliga."
            return state


        prompt = [
            SystemMessage(content=(
                "Du är en expert pensionsrådgivare. "
                "Du får endast svara baserat på innehållet i summeringarna nedan. "
                "summeringarna är extraherad från en vectordatabasen på olika pensions avtal"
                "Om du inte hittar ett tydligt svar i summeringarna, svara exakt: 'nej'. "
                "Gissa inte. Hitta ett tydligt matchande svar eller säg 'nej'."
            )),
            HumanMessage(content=(
                f"Fråga: '{question}'\n\n"
                "Här är informationen du kan använda, grupperad per avtal:\n\n" +
                "\n\n".join(structured_summary) +
                "\n\nOm användaren frågar om vilka avtal du har, nämn endast avtalsnamnen (t.ex. PA16, SKR2023), inte alla dokument."
                "Om du inte hittar ett tydligt svar i summeringarna, svara exakt: 'nej'. inget annat!"
            ))
        ]

        try:
            response = self.llm.invoke(prompt).content.strip()
            response = response.replace(". ", ".\n")  # crude line-breaks
            logger.debug("[generate_answer] Generating answer...")
            logger.warning(f"[generate_answer] LLM draft answer:\n{response}")


            state["draft_answer"] = response
            state["response_source"] = "summary_json"
            return state

        except Exception as e:
            logger.error(f"❌ LLM failed to generate answer: {e}")
            state["draft_answer"] = "Tyvärr, ett fel uppstod när jag försökte besvara frågan."
            state["response_source"] = "summary_json"
            return state


#--------------------------------------------

logger = logging.getLogger(__name__)
class RefinerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.7)
        self.retriever = RetrieverTool()

    def refine(self, state):
        state["status"] = "✏️ Förbättrar sökfrågan..."

        question = state.get("question", "")
        messages = [
            SystemMessage(content=(
                "Du är en expert på pensioner och teknisk sökoptimering. "
                "Formulera 3–5 precisa och professionella sökfrågor för en vektordatabas, baserat på användarens fråga. "
                "Använd korrekt terminologi från pensionsavtal (t.ex. 'familjepension', 'efterlevandeskydd') och inkludera agreement_name om relevant."
            )),
            HumanMessage(content=f"Originalfråga: {question}")
        ]

        reformulated = self.llm.invoke(messages).content.strip()
        state["reformulated_query"] = reformulated
        logger.warning(f"[refine_answer] Reformulated query:\n{reformulated}")

        # 🔍 Utför sökning igen
        docs = self.retriever.retrieve_relevant_docs(reformulated, top_k=3)
        context = "\n\n".join([doc.page_content for doc in docs])

        # 🧠 Försök besvara med ny kontext
        answer_prompt = [
            SystemMessage(content=(
                "Besvara frågan baserat på dokumenten nedan. Var konkret, tydlig och använd korrekt pensionsspråk. "
                "Om svaret är oklart – ge det bästa du kan hitta och förklara eventuella brister."
            )),
            HumanMessage(content=f"Fråga: {question}\n\nFörbättrad sökfråga: {reformulated}\n\nDokument:\n{context}")
        ]

        new_answer = self.llm.invoke(answer_prompt).content.strip()
        logger.info(f"[refine_answer] LLM refined answer:\n{new_answer}")

        # 🎯 Skicka vidare till slutlig användarsvar
        state["draft_answer"] = new_answer
        state["retrieved_docs"] = docs
        return state


# ---------------------------------------------
# src/agents/missing_fields_agent.py


class MissingFieldsAgent:
    def ask(self, state):
        state["status"] = "📨 Formulerar slutgiltigt svar till användaren..."

        final_answer = state.get("draft_answer", "Tyvärr har jag inget svar.")
        followup = ""

        if state.get("response_source") != "summary_json":
            user_profile = state.get("user_profile", {})
            required_fields = UserProfile.required_fields()
            missing = [f for f in required_fields if f not in user_profile or user_profile[f] is None]

            if missing:
                logger.info("[ask_for_missing_fields] Adding follow-up question for missing fields.")

                field_translations = {
                    "age": "din ålder",
                    "current_salary": "din nuvarande lön",
                    "employment_type": "vilken typ av anställning du har",
                    "years_of_service": "hur länge du har arbetat",
                    "risk_tolerance": "hur stor risk du är villig att ta",
                    "family_situation": "din familjesituation"
                }

                lang = state.get("user_language", "sv")  # use reliably detected lang
                readable_fields = [field_translations.get(f, f) for f in missing]
                # if lang == "sv":
                #     followup = (
                #         "\n\nFör att kunna ge mer personliga råd framöver, "
                #         f"skulle det hjälpa om jag kan be få lite information om {', '.join(readable_fields)}."
                #     )
                # else:
                #     followup = (
                #         "\n\nTo offer more personalized guidance, "
                #         f"it would help to know your {', '.join(readable_fields)}."
                #     )

        full_response = final_answer #+ followup
        state["response"] = full_response
        state["state"] = AgentState.FINISHED.value

        # logger.warning(f"[ask_for_missing_fields] Follow-up response to user:\n{full_response}")
        return {
            "response": state["response"],
            "status": state.get("status"),
            "user_profile": state.get("user_profile", {}),
            "conversation_id": state.get("conversation_id"),
            "token_usage": state.get("token_usage", []),
            "conversation_history": state.get("conversation_history", []),
            "state": state.get("state", AgentState.FINISHED.value),
        }


