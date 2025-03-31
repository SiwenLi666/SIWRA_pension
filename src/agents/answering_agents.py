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


        all_summaries = []
        for entry in summary_data.get("agreements", []):
            for doc in entry.get("documents", []):
                text = doc.get("summary", "")
                if text:
                    all_summaries.append(text)

        if not all_summaries:
            logger.warning("⚠️ No summaries found in summary.json")
            state["draft_answer"] = "Tyvärr, inga summeringar fanns tillgängliga."
            return state


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
            SystemMessage(content="You are a helpful assistant. Reformulate the question to make it more specific or clearer."),
            HumanMessage(content=f"Original question: {question}")
        ]
        reformulated = self.llm.invoke(messages).content.strip()
        logger.info(f"[refine_answer] Reformulated question: {reformulated}")
        

        

        # 2. Retrieve again
        new_docs = self.retriever.retrieve_relevant_docs(reformulated, top_k=3)
        context = "\n\n".join([doc.page_content for doc in new_docs])
        
        # 3. Regenerate answer
        answer_prompt = [
            SystemMessage(content="Use the following context to answer the user's question as clearly and helpfully as possible."),
            HumanMessage(content=f"Question: {reformulated}\n\nContext:\n{context}")
        ]
        new_answer = self.llm.invoke(answer_prompt).content.strip()
        logger.warning(f"[refine_answer] LLM refined answer:\n{new_answer}")
        # 4. Decide route
        route = "retry" if attempts_so_far + 1 < 2 else "give_up"
        state["draft_answer"] = new_answer
        state["retrieved_docs"] = new_docs
        state["route"] = route
        return state


    def route_refinement(self, state):
        return state.get("route", "give_up")


#------------------------------
# src/agents/verifier_agent.py


class VerifierAgent:
    def __init__(self):
        self.verifier = ResponseVerifier()

    def verify(self, state):
        """
        Check if 'draft_answer' in state is good enough.
        If good, return route='good', else route='bad'.
        """
        state["status"] = "📋 Utvärderar om svaret är tillräckligt..."
        question =  state.get("question", "")
        draft_answer = state.get("draft_answer", "")
        retrieved_docs = [doc.page_content for doc in state.get("retrieved_docs", [])]

        logger.info("[verify_answer] Verifying draft_answer quality...")

        is_sufficient = self._custom_check(question, draft_answer, retrieved_docs)

        logger.info(f"[verify_answer] is_sufficient={is_sufficient}")
        route = "good" if is_sufficient else "bad"

        state["route"] = route
        logger.warning(f"[verify_answer] LLM judged sufficiency: {route}")
        return state



    def route_verification(self, state):
        # This is the function used in add_conditional_edges() for deciding next node
        return state.get("route", "bad")


    def _custom_check(self, question, answer, retrieved_docs):
        return self.verifier.is_response_sufficient(question, answer, retrieved_docs)

# ---------------------------------------------
# src/agents/missing_fields_agent.py


class MissingFieldsAgent:
    def ask(self, state):
        """
        1) We have a final 'draft_answer'
        2) Check which user profile fields are missing
        3) Append a polite question about them to the final answer
        4) Return final 'response' to user
        """
        state["status"] = "📨 Formulerar slutgiltigt svar till användaren..."
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

            field_translations = {
                "age": "din ålder",
                "current_salary": "din nuvarande lön",
                "employment_type": "vilken typ av anställning du har",
                "years_of_service": "hur länge du har arbetat",
                "risk_tolerance": "hur stor risk du är villig att ta",
                "family_situation": "din familjesituation"
            }

            # Hitta användarens språk
            user_lang = "sv" if "å" in state.get("question", "").lower() else "en"

            if missing:
                readable_fields = [field_translations.get(f, f) for f in missing]
                if user_lang == "sv":
                    followup = (
                        "\n\nFör att kunna ge mer personliga råd framöver, "
                        f"skulle det hjälpa om jag kan be få lite information om {', '.join(readable_fields)}."
                    )
                else:
                    followup = (
                        "\n\nTo offer more personalized guidance, "
                        f"it would help to know your {', '.join(readable_fields)}."
                    )
            else:
                followup = ""

        else:
            logger.info("[ask_for_missing_fields] No missing fields to ask about.")
            followup = ""

        full_response = final_answer + followup

        # Return the final conversation outcome
        state["response"] = full_response
        state["state"] = AgentState.FINISHED.value
        logger.warning(f"[ask_for_missing_fields] Follow-up response to user:\n{full_response}")
        return state


