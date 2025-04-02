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
        self.attempts = {}

    def refine(self, state):
        state["status"] = "✏️ Reformulerar frågan..."
        conversation_id = state.get("conversation_id")
        attempts_so_far = self.attempts.get(conversation_id, 0)
        self.attempts[conversation_id] = attempts_so_far + 1
        logger.info(f"[refine_answer] attempt #{attempts_so_far + 1}")
        stage = attempts_so_far + 1
        stage_instruction = {
            #1: "🎯 Det här är första försöket. Fokusera på de mest direkta och precisa begreppen som kan matcha exakt med dokumenttexten.",
            2: "🧠 Försök nu omformulera frågan med lite bredare synonymer, relaterade begrepp eller alternativa tolkningar. Tänk om användaren menade något snarlikt.",
            3: "🚨 Detta är sista försöket. Om inget fungerar, bredda kraftigt. Prova bredare termer, relaterade teman, eller blanda olika angreppssätt.",
        }.get(stage, "")

        # 1. Reformulate query
        question =  state.get("question", "")
        messages = [
            SystemMessage(content=(f""" 
📌 Roll
Du är en kombination av en erfaren svensk pensionsrådgivare och en tekniskt kunnig sökspecialist. Din uppgift är att formulera professionella sökfrågor (queries) som kan användas i en vektordatabas för att hitta relevanta delar av pensionsavtal.
{stage_instruction}
💡 Du har totalt upp till tre försök att förbättra sökfrågan. Det här är första försöket. Var smart – satsa på de mest lovande formuleringarna, men spara extrema eller breda strategier till senare om detta misslyckas.
🧩 R3-U Modell för frågeförbättring
1️⃣ Roll (Användarens perspektiv)
Identifiera vad användaren försöker göra – t.ex. förstå regler, få rätt till ersättning, veta hur en viss situation behandlas. Exemplifiera gärna: "användaren vill veta när och till vem efterlevandepension betalas ut".

2️⃣ Regel (Fackspråk)
Hitta rätt terminologi och begrepp som används i avtalen för det användaren beskriver. Byt ut vardagsspråk till formella termer som t.ex. "efterlevandeskydd", "familjepension", "kompletterande efterlevandelivränta".

3️⃣ Resultat (Förväntat svar)
Förutse vilket typ av svar användaren vill ha: är det en regel? ett undantag? en tillämpning? ett exempel? Anpassa dina frågor därefter.

4️⃣ Uttrycksspecifikation (Sökbara frågor)
Formulera 3–5 konkreta, fokuserade queries som matchar språket i källdokumenten. obs! varje query skall ha minst 5 nyckelord (exclusive avtalsnamn)som kan beskriva en scenario som kan tänkas vara ur ursprungsfråga.
Lägg till därefter "agreement_name" =... som metadata om avtalet är angivet. Om möjligt, rikta sökningen mot t.ex. "kapitel='Efterlevandepension'" eller använd närliggande begrepp.

🛑 Viktiga regler
❌ Avsluta aldrig med att hänvisa användaren till annan rådgivare eller arbetsgivare. Du är senior rådgivaren, var professionellt!

✅ Om information saknas, säg det – men ge alltid vägledning om vad som vore nästa bästa steg.

✅ Anta aldrig att en fråga är enkel – kontrollera alltid om det kan finnas flera delar (t.ex. olika typer av efterlevandepension).

✅ Undvik att upprepa exakt samma query med små ordskillnader.


"""
            )),
            HumanMessage(content=f"Originalfråga: {question}")
        ]

        reformulated = self.llm.invoke(messages).content.strip()
        logger.warning(f"[refine_answer] Reformulated question: {reformulated}")
        

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
            HumanMessage(content=f"Originalfråga: {question}, reformerad fråga: {reformulated}\n\nDokumentutdrag:\n{context}")
        ]

        logger.info(f"[refine_answer] Sending to LLM:\n{answer_prompt}")

        new_answer = self.llm.invoke(answer_prompt).content.strip()
        logger.info(f"[refine_answer] LLM refined answer:\n{new_answer}")
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


