# src/agents/answering_agent.py
import logging
import json
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.utils.config import SUMMARY_JSON_PATH, VERIFY_ANSWERS, STRUCTURED_ANSWER_TEMPLATES, ANSWER_POST_PROCESSING, ENHANCED_COMPARISON_HANDLING, CONFIDENCE_SCORING, USER_FEEDBACK_MECHANISM
from src.retriever.retriever_tool import RetrieverTool
from src.reasoning.reasoning_utils import ResponseVerifier, AnswerPostProcessor, ComparisonHandler, ConfidenceScorer
from src.graph.state import GraphState, AgentState, UserProfile
from src.feedback.feedback_ui import FeedbackUI

logger = logging.getLogger('answering_agents')


class AnswerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.3, model="gpt-4")
        self.response_verifier = ResponseVerifier() if VERIFY_ANSWERS else None

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
            
            # Verify the answer if enabled
            if VERIFY_ANSWERS and self.response_verifier and response.lower() == "nej":
                logger.info("🔍 Answer verification: Initial answer was 'nej', attempting to find better information")
                # If the answer is just 'nej', we need to try a different approach
                state["draft_answer"] = response
                state["response_source"] = "summary_json"
                state["needs_refinement"] = True
                return state
            
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
        self.response_verifier = ResponseVerifier() if VERIFY_ANSWERS else None
        self.question_classifier = QuestionClassifier() if STRUCTURED_ANSWER_TEMPLATES else None
        self.post_processor = AnswerPostProcessor() if ANSWER_POST_PROCESSING else None
        self.comparison_handler = ComparisonHandler() if ENHANCED_COMPARISON_HANDLING else None
        self.confidence_scorer = ConfidenceScorer() if CONFIDENCE_SCORING else None
        self.feedback_ui = FeedbackUI() if USER_FEEDBACK_MECHANISM else None

    def refine(self, state):
        state["status"] = "✏️ Förbättrar sökfrågan..."

        question = state.get("question", "")
        messages = [
            SystemMessage(content=(
                "Du är en expert på pensioner och teknisk sökoptimering. "
                "Formulera 3–5 precisa och professionella sökfrågor för en vektordatabas, baserat på användarens fråga. "
                "Använd korrekt terminologi från pensionsavtal (t.ex. 'familjepension', 'efterlevandeskydd') och inkludera agreement_name om relevant."
            )),
            HumanMessage(content=f"Originalfåga: {question}")
        ]

        reformulated = self.llm.invoke(messages).content.strip()
        state["reformulated_query"] = reformulated
        logger.warning(f"[refine_answer] Reformulated query:\n{reformulated}")

        # 🔍 Utför sökning igen
        docs = self.retriever.retrieve_relevant_docs(reformulated, top_k=3)
        
        # Extract and collect all acronyms and definitions from retrieved documents
        all_acronyms = set()
        all_definitions = {}
        all_target_groups = set()
        
        for doc in docs:
            # Extract acronyms and their definitions
            if "acronyms" in doc.metadata and doc.metadata["acronyms"]:
                for acronym in doc.metadata["acronyms"]:
                    all_acronyms.add(acronym)
            
            # Collect definitions
            if "definitions" in doc.metadata and doc.metadata["definitions"]:
                all_definitions.update(doc.metadata["definitions"])
            
            # Collect target groups
            if "target_groups" in doc.metadata and doc.metadata["target_groups"]:
                all_target_groups.update(doc.metadata["target_groups"])
        
        # Create enhanced context with definitions if relevant
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Check if the question is about an acronym or term that we have a definition for
        relevant_terms = []
        for term in all_acronyms:
            if term.lower() in question.lower():
                if term in all_definitions:
                    relevant_terms.append((term, all_definitions[term]))
        
        # Add definitions section if we found relevant terms
        definitions_section = ""
        if relevant_terms:
            definitions_section = "\n\nDefinitioner av termer i frågan:\n"
            for term, definition in relevant_terms:
                definitions_section += f"- {term}: {definition}\n"
        
        # Add target group information if relevant
        target_group_section = ""
        if all_target_groups:
            target_group_section = "\n\nMålgrupper som nämns i dokumenten:\n"
            for group in all_target_groups:
                target_group_section += f"- {group}\n"
        
        # Combine everything
        enhanced_context = context + definitions_section + target_group_section

        # Classify the question type if structured templates are enabled
        question_type = None
        template = None
        if STRUCTURED_ANSWER_TEMPLATES and self.question_classifier:
            question_type = self.question_classifier.classify_question(question)
            template = self.question_classifier.get_template_for_type(question_type)
            logger.info(f"[refine_answer] Question classified as: {question_type}")
        
        # 🤖 Försök besvara med ny kontext och eventuell strukturerad mall
        system_content = (
            "Besvara frågan baserat på dokumenten nedan. Var konkret, tydlig och använd korrekt pensionsspråk. "
            "Om svaret är oklart – ge det bästa du kan hitta och förklara eventuella brister. "
            "Om frågan innehåller pensionstermer eller förkortningar, förklara dessa i ditt svar. "
            "Om det finns målgruppsinformation, förklara vad som gäller för olika målgrupper."
        )
        
        # Add template instructions if available
        if template:
            system_content += f"\n\nAnvänd följande mall för att strukturera ditt svar:\n{template}"
        
        answer_prompt = [
            SystemMessage(content=system_content),
            HumanMessage(content=f"Fråga: {question}\n\nFörbättrad sökfråga: {reformulated}\n\nDokument och definitioner:\n{enhanced_context}")
        ]

        new_answer = self.llm.invoke(answer_prompt).content.strip()
        logger.info(f"[refine_answer] LLM refined answer:\n{new_answer}")
        
        # Verify the answer if enabled
        if VERIFY_ANSWERS and self.response_verifier:
            doc_contents = [doc.page_content for doc in docs]
            is_sufficient = self.response_verifier.is_response_sufficient(
                question, new_answer, doc_contents
            )
            
            if not is_sufficient:
                logger.warning("⚠️ Answer verification: Response deemed insufficient")
                # Try to improve the answer with more explicit instructions
                fallback_prompt = [
                    SystemMessage(content=(
                        "Du är en expert pensionsrådgivare. Besvara frågan baserat på dokumenten nedan. "
                        "Var konkret och tydlig. Om du inte kan hitta ett bra svar i dokumenten, "
                        "erkänn det ärligt och ge användaren bästa möjliga information baserat på "
                        "vad som faktiskt finns i dokumenten. Undvik att hänvisa till information som "
                        "inte finns i dokumenten. Förklara pensionstermer och förkortningar när det är relevant."
                    )),
                    HumanMessage(content=f"Fråga: {question}\n\nDokument och definitioner:\n{enhanced_context}")
                ]
                
                try:
                    improved_answer = self.llm.invoke(fallback_prompt).content.strip()
                    logger.info(f"[refine_answer] Improved answer after verification:\n{improved_answer}")
                    new_answer = improved_answer
                except Exception as e:
                    logger.error(f"❌ Failed to generate improved answer: {e}")
                    # Keep the original answer if fallback fails
        
        # Check if this is a comparison question and handle it specially
        is_comparison = False
        if ENHANCED_COMPARISON_HANDLING and self.comparison_handler:
            try:
                is_comparison = self.comparison_handler.is_comparison_question(question)
                if is_comparison:
                    logger.info("📋 Detected comparison question, using specialized handling")
                    doc_contents = [doc.page_content for doc in docs]
                    comparison_answer = self.comparison_handler.generate_structured_comparison(question, doc_contents)
                    new_answer = comparison_answer
                    logger.info("✅ Generated structured comparison response")
            except Exception as e:
                logger.error(f"❌ Error in comparison handling: {e}")
                # Continue with normal processing if comparison handling fails
                is_comparison = False
        
        # Apply post-processing if enabled and not a comparison question
        if ANSWER_POST_PROCESSING and self.post_processor and not is_comparison:
            doc_contents = [doc.page_content for doc in docs]
            logger.info("🔄 Applying answer post-processing")
            processed_answer = self.post_processor.process_answer(question, new_answer, doc_contents)
            
            # Only use the processed answer if it's different from the original
            if processed_answer != new_answer:
                logger.info("✅ Answer was enhanced during post-processing")
                new_answer = processed_answer
            else:
                logger.info("ℹ️ No changes needed during post-processing")
                
        # Add confidence scoring if enabled
        if CONFIDENCE_SCORING and self.confidence_scorer:
            doc_contents = [doc.page_content for doc in docs]
            logger.info("📊 Adding confidence score to answer")
            new_answer = self.confidence_scorer.add_confidence_score_to_answer(question, new_answer, doc_contents)
        
        # Add feedback UI if enabled
        if USER_FEEDBACK_MECHANISM and self.feedback_ui:
            logger.info("🗳️ Adding feedback UI to answer")
            feedback_ui = self.feedback_ui.prepare_feedback_ui(question, new_answer)
            new_answer = new_answer + feedback_ui
        
        # 🎯 Skicka vidare till slutlig användarsvar
        state["draft_answer"] = new_answer
        state["retrieved_docs"] = docs
        return state


# ---------------------------------------------
# Question Classification for Structured Templates

class QuestionClassifier:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.0)  # Use a cheaper model for classification
    
    def classify_question(self, question: str) -> str:
        """
        Classify the question into one of several predefined types to determine
        which answer template to use.
        """
        if not STRUCTURED_ANSWER_TEMPLATES:
            return "general"
            
        prompt = [
            SystemMessage(content=(
                "Du är en expert på att klassificera frågor om pension. "
                "Analysera frågan och klassificera den i exakt EN av följande kategorier:\n"
                "- eligibility: Frågor om vem som kvalificerar sig för en viss pensionsförmån\n"
                "- calculation: Frågor om hur man beräknar pensionsbelopp\n"
                "- comparison: Frågor som jämför olika pensionsavtal eller förmåner\n"
                "- timeline: Frågor om tidpunkter, datum eller tidslinjer för pension\n"
                "- process: Frågor om processer eller steg för att ansöka om pension\n"
                "- definition: Frågor som ber om definition av pensionstermer\n"
                "- requirement: Frågor om krav för att få en viss pensionsförmån\n"
                "- general: Alla andra typer av frågor\n\n"
                "Svara ENDAST med kategorinamnet i lowercase, inget annat."
            )),
            HumanMessage(content=question)
        ]
        
        try:
            response = self.llm.invoke(prompt).content.strip().lower()
            # Validate the response is one of our categories
            valid_types = ["eligibility", "calculation", "comparison", "timeline", 
                          "process", "definition", "requirement", "general"]
            
            if response in valid_types:
                return response
            return "general"  # Default if classification fails
        except Exception as e:
            logger.error(f"❌ Question classification failed: {e}")
            return "general"  # Default to general template
    
    def get_template_for_type(self, question_type: str) -> str:
        """
        Return a structured template based on the question type.
        """
        templates = {
            "eligibility": (
                "## Behörighet\n"
                "**Målgrupp:** [Beskriv vilka personer/grupper som berörs]\n\n"
                "**Kvalifikationskrav:**\n- [Lista viktiga krav]\n\n"
                "**Undantag:**\n- [Lista eventuella undantag]\n\n"
                "**Ytterligare information:** [Lägg till relevant kontext]"
            ),
            "calculation": (
                "## Beräkning av pension\n"
                "**Formel:** [Beskriv beräkningsformeln om tillgänglig]\n\n"
                "**Faktorer som påverkar beräkningen:**\n- [Lista faktorer]\n\n"
                "**Exempel:** [Ge ett exempel om möjligt]\n\n"
                "**Begränsningar:** [Nämn eventuella tak eller golv]"
            ),
            "comparison": (
                "## Jämförelse\n"
                "**Alternativ 1: [Namn]**\n- Fördelar: [Lista fördelar]\n- Nackdelar: [Lista nackdelar]\n\n"
                "**Alternativ 2: [Namn]**\n- Fördelar: [Lista fördelar]\n- Nackdelar: [Lista nackdelar]\n\n"
                "**Viktigaste skillnaderna:**\n- [Lista huvudskillnader]\n\n"
                "**Rekommendation:** [Om lämpligt]"
            ),
            "timeline": (
                "## Tidslinje\n"
                "**Viktiga datum:**\n- [Lista datum och händelser]\n\n"
                "**Deadlines:**\n- [Lista viktiga deadlines]\n\n"
                "**Övergångsperioder:** [Beskriv eventuella övergångsregler]\n\n"
                "**Nästa steg:** [Vad som händer efter]"
            ),
            "process": (
                "## Process\n"
                "**Steg för steg:**\n1. [Steg 1]\n2. [Steg 2]\n3. [Fortsätt efter behov]\n\n"
                "**Nödvändiga dokument:**\n- [Lista dokument]\n\n"
                "**Kontaktinformation:** [Om tillgänglig]\n\n"
                "**Vanliga problem:** [Lista vanliga problem och lösningar]"
            ),
            "definition": (
                "## Definition\n"
                "**Term:** [Term som definieras]\n\n"
                "**Definition:** [Tydlig definition]\n\n"
                "**Används i sammanhang:** [Förklara när/hur termen används]\n\n"
                "**Relaterade termer:** [Lista relaterade begrepp]"
            ),
            "requirement": (
                "## Krav\n"
                "**Huvudkrav:**\n- [Lista huvudkrav]\n\n"
                "**Dokumentation som behövs:**\n- [Lista nödvändiga dokument]\n\n"
                "**Tidsgränser:** [Ange eventuella tidsfrister]\n\n"
                "**Verifieringsprocess:** [Beskriv hur kraven verifieras]"
            ),
            "general": ""  # No specific template for general questions
        }
        
        return templates.get(question_type, "")

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


