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
            return state

        except Exception as e:
            logger.error(f"❌ LLM failed to generate answer: {e}")
            state["draft_answer"] = "Tyvärr, ett fel uppstod när jag försökte besvara frågan."
            return state


#--------------------------------------------

logger = logging.getLogger(__name__)
class RefinerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.7)
        self.retriever = RetrieverTool()
        self.attempts = {}

    def refine(self, state):
        state["status"] = "✏️ Reformulerar frågan..."
        conversation_id = state.get("conversation_id")
        attempts_so_far = self.attempts.get(conversation_id, 0)
        self.attempts[conversation_id] = attempts_so_far + 1
        logger.info(f"[refine_answer] attempt #{attempts_so_far + 1}")

        # 1. Reformulate query
        question =  state.get("question", "")
        messages = [
            SystemMessage(content=(""" 
Du är både pensionsrådgivare och vektorsökningsexpert. Du har två uppgifter:

1.**Som pensionsrådgivare**: 
- Tolka användarens fråga.
- Förbättra och förtydliga den utifrån din kunskap om pensionssystemet, lagar, kollektivavtal och vedertagna begrepp.
- Om användaren använder vardagligt språk, översätt det till termer som används i pensionsavtal (t.ex. "efterlevnadsskydd" → "efterlevandepension", "dödsfall", "familjeskydd", "återbetalningsskydd").
- Om ett visst avtal nämns (t.ex. "PA16", "Pensionsavtal 2016"), tolka det korrekt och använd exakt det namn som finns i systemet (t.ex. "PA16").

2 **Som FAISS-sökexpert**:
- Formulera en sökfråga som maximerar vektorträffar mot chunks.
- Använd metadata om möjligt, t.ex. `agreement_name="PA16"` för att filtrera endast på relevanta avtal.
- Om frågan gäller ett särskilt kapitel eller paragraf som nämns i användarens fråga eller i ett dokumentutdrag, inkludera det i sökfrågan.
- Formulera flera semantiskt olika men relevanta varianter av frågan för att förbättra träffsäkerheten.

🧩 Syfte: Hjälp RetrievalAgent att få fram de mest relevanta chunksen från vektordatabasen. Formulera frågan för `similarity_search()` så optimerat som möjligt.

Svar ska endast innehålla förbättrade sökfrågor som ska användas vid vektorsökning.

"""
            )),
            HumanMessage(content=f"Originalfråga: {question}")
        ]

        reformulated = self.llm.invoke(messages).content.strip()
        logger.info(f"[refine_answer] Reformulated question: {reformulated}")
        

        

        # 2. Retrieve again
        new_docs = self.retriever.retrieve_relevant_docs(reformulated, top_k=3)
        context = "\n\n".join([doc.page_content for doc in new_docs])
        
        # 3. Regenerate answer
        answer_prompt = [
            SystemMessage(content=(
                "Du är en svensk pensionsrådgivare. Besvara användarens fråga så tydligt som möjligt "
                "baserat på dokumenten nedan. Var konkret, korrekt och pedagogisk.\n\n"
                "• Svara på samma språk som frågan.\n"
                "• Om du hittar något relevant men inte hela svaret, skriv vad du hittade - men var ärlig med vad som saknas.\n"
                "• Gissa inte, men försök alltid hjälpa användaren vidare.\n"
                "• Om frågan gäller ett särskilt pensionsavtal, och det framgår i kontexten, nämn det i svaret.\n"
                "• Strukturera gärna svaret i punktform eller underrubriker om det förbättrar läsbarheten.\n"
            )),
            HumanMessage(content=f"Fråga: {reformulated}\n\nDokumentutdrag:\n{context}")
        ]
        logger.warning(f"[refine_answer] Sending to LLM:\n{answer_prompt}")

        new_answer = self.llm.invoke(answer_prompt).content.strip()
        logger.warning(f"[refine_answer] LLM refined answer:\n{new_answer}")
        # 4. Decide route
        route = "retry" if attempts_so_far + 1 <= 3 else "give_up"
        state["draft_answer"] = new_answer
        state["retrieved_docs"] = new_docs
        state["refiner_route"] = route

        return state


    def route_refinement(self, state):
        return state.get("refiner_route", "give_up")



#------------------------------
# src/agents/verifier_agent.py


class VerifierAgent:
    def __init__(self):
        self.verifier = ResponseVerifier()

    def verify(self, state):
        """
        Check if 'draft_answer' in state is good enough.
        If generate_answer gives anything other than 'nej', accept it.
        """
        state["status"] = "📋 Utvärderar om svaret är tillräckligt..."
        question = state.get("question", "")
        draft_answer = state.get("draft_answer", "").strip()
        retrieved_docs = [doc.page_content for doc in state.get("retrieved_docs", [])]

        logger.info("[verify_answer] Verifying draft_answer quality...")

        # ✅ Shortcut: if answer is NOT 'nej', treat it as good
        if draft_answer.lower() != "nej":
            logger.info("[verify_answer] Bypassing verifier — draft answer is not 'nej'")
            state["route"] = "good"
            return state

        # Otherwise, do proper check
        is_sufficient = self._custom_check(question, draft_answer, retrieved_docs)
        route = "good" if is_sufficient else "bad"
        state["verifier_route"] = route


        logger.warning(f"[verify_answer] LLM judged sufficiency: {route}")
        return state




    def route_verification(self, state):
        return state.get("verifier_route", "bad")



    def _custom_check(self, question, answer, retrieved_docs):
        return self.verifier.is_response_sufficient(question, answer, retrieved_docs)

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
                if lang == "sv":
                    followup = (
                        "\n\nFör att kunna ge mer personliga råd framöver, "
                        f"skulle det hjälpa om jag kan be få lite information om {', '.join(readable_fields)}."
                    )
                else:
                    followup = (
                        "\n\nTo offer more personalized guidance, "
                        f"it would help to know your {', '.join(readable_fields)}."
                    )

        full_response = final_answer + followup
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


