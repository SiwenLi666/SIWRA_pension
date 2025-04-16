from typing import Optional, Literal, Dict, Any, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import re
import logging
from typing import List, Set
import json

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


class AnswerPostProcessor:
    """
    Post-processes generated answers to ensure they include all requested information
    and address the user's question properly.
    """
    
    def __init__(self, model_name="gpt-4", temperature=0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
    
    def extract_key_entities(self, question: str) -> List[str]:
        """
        Extract key entities from the user's question that should be addressed in the answer.
        """
        prompt = [
            SystemMessage(content=(
                "Identifiera de viktigaste nyckelorden och entiteterna i frågan som ett svar måste adressera. "
                "Returnera endast en kommaseparerad lista med 3-5 viktiga termer eller koncept, inga förklaringar."
            )),
            HumanMessage(content=question)
        ]
        
        try:
            result = self.llm.invoke(prompt)
            entities = [entity.strip() for entity in result.content.split(',')]
            logger.info(f"[AnswerPostProcessor] Extracted entities: {entities}")
            return entities
        except Exception as e:
            logger.error(f"❌ Error extracting entities: {e}")
            return []
    
    def identify_missing_information(self, question: str, answer: str, context: List[str]) -> Tuple[bool, List[str]]:
        """
        Identify what information is missing from the answer that should be included.
        Returns a tuple of (has_missing_info, list_of_missing_items)
        """
        context_text = "\n\n".join(context[:3]) if context else "Ingen kontext tillgänglig."
        
        prompt = [
            SystemMessage(content=(
                "Du är en expert på att analysera svar på pensionsfrågor. "
                "Granska svaret och identifiera viktiga delar från frågan som inte besvaras tillräckligt. "
                "Om all viktig information finns med, svara 'KOMPLETT'. "
                "Annars, lista de specifika informationspunkter som saknas eller är otillräckliga, "
                "en per rad med '-' i början. Var koncis."
            )),
            HumanMessage(content=f"Fråga: {question}\n\nSvar: {answer}\n\nTillgänglig kontext:\n{context_text}")
        ]
        
        try:
            result = self.llm.invoke(prompt)
            response = result.content.strip()
            
            if "KOMPLETT" in response.upper():
                return (False, [])
            
            # Extract missing items from the response
            missing_items = []
            for line in response.split('\n'):
                if line.strip().startswith('-'):
                    missing_items.append(line.strip()[1:].strip())
            
            return (True, missing_items)
        except Exception as e:
            logger.error(f"❌ Error identifying missing information: {e}")
            return (False, [])
    
    def enhance_answer(self, question: str, original_answer: str, context: List[str], missing_items: List[str]) -> str:
        """
        Enhance the answer by adding missing information identified in the analysis.
        """
        if not missing_items:
            return original_answer
            
        context_text = "\n\n".join(context[:3]) if context else "Ingen kontext tillgänglig."
        missing_info = "\n".join([f"- {item}" for item in missing_items])
        
        prompt = [
            SystemMessage(content=(
                "Du är en expert på pensioner. Förbättra det ursprungliga svaret genom att lägga till "
                "information om de saknade punkterna nedan. Integrera informationen naturligt i svaret "
                "så att det flyter bra. Använd endast information från den tillgängliga kontexten. "
                "Om information saknas i kontexten, erkänn det på ett professionellt sätt."
            )),
            HumanMessage(content=(
                f"Fråga: {question}\n\n"
                f"Ursprungligt svar: {original_answer}\n\n"
                f"Saknad information att inkludera:\n{missing_info}\n\n"
                f"Tillgänglig kontext:\n{context_text}"
            ))
        ]
        
        try:
            result = self.llm.invoke(prompt)
            enhanced_answer = result.content.strip()
            logger.info(f"[AnswerPostProcessor] Enhanced answer created")
            return enhanced_answer
        except Exception as e:
            logger.error(f"❌ Error enhancing answer: {e}")
            return original_answer  # Return original if enhancement fails
    
    def process_answer(self, question: str, answer: str, context: List[str]) -> str:
        """
        Main method to post-process an answer, ensuring it includes all requested information.
        """
        # Step 1: Check if answer is missing important information
        has_missing_info, missing_items = self.identify_missing_information(question, answer, context)
        
        # Step 2: If information is missing, enhance the answer
        if has_missing_info and missing_items:
            logger.info(f"[AnswerPostProcessor] Missing information detected: {missing_items}")
            enhanced_answer = self.enhance_answer(question, answer, context, missing_items)
            return enhanced_answer
        
        # If no enhancement needed, return the original answer
        return answer


class ComparisonHandler:
    """
    Specialized handler for comparison questions between pension agreements or provisions.
    Provides structured comparison templates and tabular formatting for clear side-by-side comparisons.
    """
    
    def __init__(self, model_name="gpt-4", temperature=0.3):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
    
    def is_comparison_question(self, question: str) -> bool:
        """
        Detect if a question is asking for a comparison between different items.
        """
        comparison_indicators = [
            "jämför", "skillnad", "likheter", "jämförelse", "versus", "vs", 
            "kontra", "eller", "jämfört med", "i förhållande till", "bättre", 
            "sämre", "fördelar", "nackdelar", "mellan"
        ]
        
        # Check for comparison indicators
        lower_q = question.lower()
        for indicator in comparison_indicators:
            if indicator in lower_q:
                # Verify with more context - ensure it's comparing pension-related items
                prompt = [
                    SystemMessage(content=(
                        "Avgör om följande fråga ber om en jämförelse mellan olika pensionsavtal, "
                        "förmåner, eller bestämmelser. Svara endast med 'JA' eller 'NEJ'."
                    )),
                    HumanMessage(content=question)
                ]
                
                try:
                    result = self.llm.invoke(prompt)
                    return "ja" in result.content.lower()
                except Exception as e:
                    logger.error(f"❌ Error detecting comparison question: {e}")
                    # If LLM call fails, use simple heuristic
                    return True
        
        return False
    
    def extract_comparison_entities(self, question: str) -> List[str]:
        """
        Extract the entities being compared in the question.
        """
        prompt = [
            SystemMessage(content=(
                "Identifiera de specifika pensionsavtal, förmåner, eller bestämmelser som jämförs i frågan. "
                "Returnera dem som en kommaseparerad lista. Om inga specifika enheter nämns, returnera 'OSPECIFICERAT'."
            )),
            HumanMessage(content=question)
        ]
        
        try:
            result = self.llm.invoke(prompt)
            entities = [entity.strip() for entity in result.content.split(',')]
            if "OSPECIFICERAT" in entities:
                return []
            logger.info(f"[ComparisonHandler] Extracted entities: {entities}")
            return entities
        except Exception as e:
            logger.error(f"❌ Error extracting comparison entities: {e}")
            return []
    
    def extract_comparison_aspects(self, question: str) -> List[str]:
        """
        Extract the specific aspects to compare (e.g., retirement age, benefits amount).
        """
        prompt = [
            SystemMessage(content=(
                "Identifiera de specifika aspekter eller egenskaper som ska jämföras i frågan. "
                "Till exempel: pensionsålder, förmånsbelopp, villkor, etc. "
                "Returnera dem som en kommaseparerad lista. Om inga specifika aspekter nämns, returnera 'ALLA'."
            )),
            HumanMessage(content=question)
        ]
        
        try:
            result = self.llm.invoke(prompt)
            aspects = [aspect.strip() for aspect in result.content.split(',')]
            if "ALLA" in aspects:
                # Default aspects if none specified
                return ["Grundläggande villkor", "Förmåner", "Pensionsålder", "Särskilda bestämmelser"]
            logger.info(f"[ComparisonHandler] Extracted aspects: {aspects}")
            return aspects
        except Exception as e:
            logger.error(f"❌ Error extracting comparison aspects: {e}")
            return ["Grundläggande villkor", "Förmåner", "Pensionsålder", "Särskilda bestämmelser"]
    
    def generate_comparison_table(self, entities: List[str], aspects: List[str], context: List[str]) -> str:
        """
        Generate a structured comparison table between the entities based on specified aspects.
        """
        context_text = "\n\n".join(context)
        
        # Handle case where entities couldn't be extracted
        if not entities or len(entities) < 2:
            # Try to extract entities from context if not found in question
            prompt = [
                SystemMessage(content=(
                    "Baserat på kontexten, identifiera de två eller fler pensionsavtal eller förmåner "
                    "som är mest relevanta att jämföra. Returnera dem som en kommaseparerad lista."
                )),
                HumanMessage(content=context_text)
            ]
            
            try:
                result = self.llm.invoke(prompt)
                entities = [entity.strip() for entity in result.content.split(',')]
                logger.info(f"[ComparisonHandler] Extracted entities from context: {entities}")
            except Exception as e:
                logger.error(f"❌ Error extracting entities from context: {e}")
                return "Jag kunde inte identifiera specifika pensionsavtal eller förmåner att jämföra. Kan du specificera vilka avtal eller förmåner du vill jämföra?"
        
        # Create table header
        table = "| Aspekt | " + " | ".join(entities) + " |\n"
        table += "| --- | " + " | ".join(["---" for _ in entities]) + " |\n"
        
        # Generate comparison data
        for aspect in aspects:
            prompt = [
                SystemMessage(content=(
                    f"Jämför följande pensionsavtal/förmåner med avseende på '{aspect}'. "
                    f"Ge en kort och koncis jämförelse för varje avtal/förmån. "
                    f"Använd endast information från den givna kontexten. "
                    f"Om information saknas för något avtal, ange 'Information saknas'. "
                    f"Formatera svaret som ett JSON-objekt där nycklarna är avtalsnamnen och värdena är beskrivningarna."
                )),
                HumanMessage(content=f"Avtal/förmåner att jämföra: {', '.join(entities)}\n\nKontext:\n{context_text}")
            ]
            
            try:
                result = self.llm.invoke(prompt)
                # Try to parse as JSON
                try:
                    comparison_data = json.loads(result.content)
                    row = f"| **{aspect}** | "
                    for entity in entities:
                        if entity in comparison_data:
                            row += f"{comparison_data[entity]} | "
                        else:
                            row += "Information saknas | "
                    table += row + "\n"
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    logger.warning(f"[ComparisonHandler] JSON parsing failed, using raw response")
                    table += f"| **{aspect}** | {' | '.join(['Information kunde inte struktureras' for _ in entities])} |\n"
            except Exception as e:
                logger.error(f"❌ Error generating comparison for aspect {aspect}: {e}")
                table += f"| **{aspect}** | {' | '.join(['Fel vid jämförelse' for _ in entities])} |\n"
        
        return table
    
    def generate_comparison_summary(self, entities: List[str], context: List[str]) -> str:
        """
        Generate a summary of key differences and similarities between the entities.
        """
        if not entities or len(entities) < 2:
            return ""
            
        context_text = "\n\n".join(context)
        
        prompt = [
            SystemMessage(content=(
                "Sammanfatta de viktigaste skillnaderna och likheterna mellan de angivna pensionsavtalen/förmånerna. "
                "Fokusera på de mest betydelsefulla aspekterna för en pensionstagare. "
                "Var kortfattad och tydlig."
            )),
            HumanMessage(content=f"Avtal/förmåner att jämföra: {', '.join(entities)}\n\nKontext:\n{context_text}")
        ]
        
        try:
            result = self.llm.invoke(prompt)
            return "\n\n### Sammanfattning av jämförelsen\n\n" + result.content
        except Exception as e:
            logger.error(f"❌ Error generating comparison summary: {e}")
            return ""
    
    def generate_structured_comparison(self, question: str, context: List[str]) -> str:
        """
        Main method to generate a structured comparison response based on the question and context.
        """
        # Extract entities and aspects to compare
        entities = self.extract_comparison_entities(question)
        aspects = self.extract_comparison_aspects(question)
        
        # Generate comparison table
        comparison_table = self.generate_comparison_table(entities, aspects, context)
        
        # Generate summary
        summary = self.generate_comparison_summary(entities, context)
        
        # Combine into structured response
        response = f"### Jämförelse mellan {', '.join(entities) if entities else 'pensionsavtal/förmåner'}\n\n"
        response += comparison_table + "\n"
        response += summary
        
        return response


class ConfidenceScorer:
    """
    Evaluates the confidence level of generated answers based on evidence strength,
    context relevance, and answer completeness.
    """
    
    def __init__(self, model_name="gpt-4", temperature=0.2):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
    
    def calculate_confidence_score(self, question: str, answer: str, context: List[str]) -> Tuple[float, Dict[str, float]]:
        """
        Calculate a confidence score (0-100%) for the generated answer based on multiple factors.
        Returns the overall score and a breakdown of component scores.
        """
        context_text = "\n\n".join(context[:3]) if context else "Ingen kontext tillgänglig."
        
        # Evaluate different aspects of confidence
        evidence_score = self._evaluate_evidence_strength(question, answer, context_text)
        relevance_score = self._evaluate_context_relevance(question, context_text)
        completeness_score = self._evaluate_answer_completeness(question, answer)
        consistency_score = self._evaluate_internal_consistency(answer)
        
        # Calculate weighted overall score
        weights = {
            "evidence": 0.4,      # Evidence strength is most important
            "relevance": 0.3,    # Context relevance is very important
            "completeness": 0.2,  # Answer completeness matters
            "consistency": 0.1    # Internal consistency is a bonus
        }
        
        component_scores = {
            "evidence": evidence_score,
            "relevance": relevance_score,
            "completeness": completeness_score,
            "consistency": consistency_score
        }
        
        overall_score = sum(score * weights[key] for key, score in component_scores.items())
        
        # Round to nearest integer percentage
        overall_score = round(overall_score)
        
        return overall_score, component_scores
    
    def _evaluate_evidence_strength(self, question: str, answer: str, context: str) -> float:
        """
        Evaluate how well the answer is supported by evidence in the context.
        Returns a score from 0-100.
        """
        prompt = [
            SystemMessage(content=(
                "Bedöm hur väl svaret stöds av bevis i den tillhandahållna kontexten. "
                "Ge en poäng från 0 till 100 där:\n"
                "0 = Inget stöd alls i kontexten\n"
                "50 = Delvis stöd i kontexten\n"
                "100 = Fullständigt stöd i kontexten med specifika citat eller hänvisningar\n"
                "Returnera ENDAST ett heltal mellan 0 och 100."
            )),
            HumanMessage(content=f"Fråga: {question}\n\nSvar: {answer}\n\nKontext: {context}")
        ]
        
        try:
            result = self.llm.invoke(prompt)
            # Extract the numeric score
            score_text = re.search(r'\d+', result.content)
            if score_text:
                score = int(score_text.group())
                return min(max(score, 0), 100)  # Ensure score is between 0-100
            return 50  # Default to medium confidence if parsing fails
        except Exception as e:
            logger.error(f"❌ Error evaluating evidence strength: {e}")
            return 50  # Default to medium confidence if evaluation fails
    
    def _evaluate_context_relevance(self, question: str, context: str) -> float:
        """
        Evaluate how relevant the retrieved context is to the question.
        Returns a score from 0-100.
        """
        prompt = [
            SystemMessage(content=(
                "Bedöm hur relevant den hämtade kontexten är för frågan. "
                "Ge en poäng från 0 till 100 där:\n"
                "0 = Kontexten är helt irrelevant för frågan\n"
                "50 = Kontexten är delvis relevant men saknar viktig information\n"
                "100 = Kontexten är perfekt relevant och innehåller all nödvändig information\n"
                "Returnera ENDAST ett heltal mellan 0 och 100."
            )),
            HumanMessage(content=f"Fråga: {question}\n\nKontext: {context}")
        ]
        
        try:
            result = self.llm.invoke(prompt)
            # Extract the numeric score
            score_text = re.search(r'\d+', result.content)
            if score_text:
                score = int(score_text.group())
                return min(max(score, 0), 100)  # Ensure score is between 0-100
            return 50  # Default to medium confidence if parsing fails
        except Exception as e:
            logger.error(f"❌ Error evaluating context relevance: {e}")
            return 50  # Default to medium confidence if evaluation fails
    
    def _evaluate_answer_completeness(self, question: str, answer: str) -> float:
        """
        Evaluate how completely the answer addresses all aspects of the question.
        Returns a score from 0-100.
        """
        prompt = [
            SystemMessage(content=(
                "Bedöm hur fullständigt svaret adresserar alla aspekter av frågan. "
                "Ge en poäng från 0 till 100 där:\n"
                "0 = Svaret adresserar inte frågan alls\n"
                "50 = Svaret adresserar frågan delvis men missar viktiga aspekter\n"
                "100 = Svaret adresserar alla aspekter av frågan fullständigt\n"
                "Returnera ENDAST ett heltal mellan 0 och 100."
            )),
            HumanMessage(content=f"Fråga: {question}\n\nSvar: {answer}")
        ]
        
        try:
            result = self.llm.invoke(prompt)
            # Extract the numeric score
            score_text = re.search(r'\d+', result.content)
            if score_text:
                score = int(score_text.group())
                return min(max(score, 0), 100)  # Ensure score is between 0-100
            return 50  # Default to medium confidence if parsing fails
        except Exception as e:
            logger.error(f"❌ Error evaluating answer completeness: {e}")
            return 50  # Default to medium confidence if evaluation fails
    
    def _evaluate_internal_consistency(self, answer: str) -> float:
        """
        Evaluate the internal consistency and coherence of the answer.
        Returns a score from 0-100.
        """
        prompt = [
            SystemMessage(content=(
                "Bedöm den interna konsistensen och sammanhänget i svaret. "
                "Ge en poäng från 0 till 100 där:\n"
                "0 = Svaret är mycket inkonsekvent med motsatta påståenden\n"
                "50 = Svaret har några mindre inkonsekvenser\n"
                "100 = Svaret är helt konsekvent och välstrukturerat\n"
                "Returnera ENDAST ett heltal mellan 0 och 100."
            )),
            HumanMessage(content=f"Svar: {answer}")
        ]
        
        try:
            result = self.llm.invoke(prompt)
            # Extract the numeric score
            score_text = re.search(r'\d+', result.content)
            if score_text:
                score = int(score_text.group())
                return min(max(score, 0), 100)  # Ensure score is between 0-100
            return 50  # Default to medium confidence if parsing fails
        except Exception as e:
            logger.error(f"❌ Error evaluating internal consistency: {e}")
            return 50  # Default to medium confidence if evaluation fails
    
    def get_confidence_label(self, score: float) -> str:
        """
        Convert a numeric confidence score to a human-readable label.
        """
        if score >= 90:
            return "Mycket hög"
        elif score >= 75:
            return "Hög"
        elif score >= 60:
            return "God"
        elif score >= 40:
            return "Måttlig"
        elif score >= 25:
            return "Låg"
        else:
            return "Mycket låg"
    
    def format_confidence_display(self, score: float, component_scores: Dict[str, float]) -> str:
        """
        Format the confidence score and breakdown for display to the user.
        """
        label = self.get_confidence_label(score)
        
        # Map component names to Swedish
        component_names = {
            "evidence": "Evidensstyrka",
            "relevance": "Kontextrelevans",
            "completeness": "Fullständighet",
            "consistency": "Intern konsistens"
        }
        
        # Format the confidence display
        display = f"\n\n---\n\n**Tillförlitlighet: {label} ({score}%)**\n\n"
        
        # Add component breakdown if score is below 75%
        if score < 75:
            display += "*Faktorer som påverkar tillförlitligheten:*\n\n"
            for component, component_score in component_scores.items():
                if component_score < 70:  # Only show problematic components
                    display += f"- {component_names[component]}: {component_score}%\n"
        
        return display
    
    def add_confidence_score_to_answer(self, question: str, answer: str, context: List[str]) -> str:
        """
        Calculate confidence score and add it to the answer.
        """
        try:
            score, component_scores = self.calculate_confidence_score(question, answer, context)
            confidence_display = self.format_confidence_display(score, component_scores)
            
            # Add confidence display to the answer
            enhanced_answer = answer + confidence_display
            
            logger.info(f"[ConfidenceScorer] Added confidence score: {score}%")
            return enhanced_answer
        except Exception as e:
            logger.error(f"❌ Error adding confidence score: {e}")
            return answer  # Return original answer if scoring fails
