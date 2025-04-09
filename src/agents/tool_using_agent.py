import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BaseTool:
    """Base class for all tools used by the ToolUsingPensionAgent"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def can_handle(self, question: str, state: Dict[str, Any]) -> bool:
        """Determine if this tool can handle the given question"""
        raise NotImplementedError
    
    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run the tool on the given question and state"""
        raise NotImplementedError


class ToolUsingPensionAgent:
    """
    Agent that uses a set of tools to answer pension-related questions.
    This agent replaces the complex graph structure with a simpler, more autonomous approach.
    """
    
    def __init__(self):
        self.tools = []
        self._load_tools()
        self._initialize_llm()
        logger.info(f"Initialized ToolUsingPensionAgent with {len(self.tools)} tools")
    
    def _load_tools(self):
        """Load all available tools"""
        from src.tools.calculator import CalculatorTool
        from src.tools.summary_checker import SummaryCheckerTool
        from src.tools.vector_retriever import VectorRetrieverTool
        
        self.tools = [
            CalculatorTool(),
            SummaryCheckerTool(),
            VectorRetrieverTool()
        ]
        
    def _initialize_llm(self):
        """Initialize the LLM for question analysis"""
        try:
            from langchain_openai import ChatOpenAI
            from src.utils.config import OPENAI_API_KEY
            
            self.llm = ChatOpenAI(model="gpt-4", temperature=0.1, openai_api_key=OPENAI_API_KEY)
            logger.info("LLM initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            self.llm = None
    
    def _analyze_question(self, question: str, state: Dict[str, Any]) -> str:
        """
        Analyze the question to determine its type and which tool should handle it.
        Uses both rule-based patterns and LLM-based analysis.
        
        Returns:
            The type of question: 'calculation', 'summary', or 'information'
        """
        # First try rule-based analysis
        question_type = self._rule_based_analysis(question)
        
        # If we have an LLM and the rule-based analysis is uncertain, use LLM
        if question_type == 'information' and self.llm is not None:
            llm_question_type = self._llm_based_analysis(question, state)
            if llm_question_type:
                question_type = llm_question_type
                logger.info(f"LLM overrode question type to: {question_type}")
        
        return question_type
    
    def _rule_based_analysis(self, question: str) -> str:
        """Use rule-based patterns to analyze the question"""
        question_lower = question.lower()
        
        # Check if this is a calculation question
        calculation_indicators = [
            "beräkna", "räkna ut", "hur mycket", "pensionsbelopp",
            "hur stor blir min pension", "vad får jag i pension", 
            "min månadslön är", "jag tjänar", "min lön är"
        ]
        
        # Check for salary/age patterns that indicate calculation
        has_salary_pattern = bool(re.search(r'(\d[\d\s]*\s*kr|\d[\d\s]*\s*kronor|\d[\d\s]*\s*sek)', question_lower))
        has_age_pattern = bool(re.search(r'(\d+)\s*år', question_lower))
        
        if any(indicator in question_lower for indicator in calculation_indicators) or \
           (has_salary_pattern and has_age_pattern):
            logger.info("Rule-based analysis: calculation question")
            return 'calculation'
        
        # Check if this is a general information question
        information_indicators = [
            "vad är", "hur fungerar", "förklara", "beskriv", "när", "var", "vem",
            "vilka regler", "hur länge", "kan man", "möjligt att", "tillåtet att",
            "rättigheter", "skyldigheter", "överenskommelse", "avtal", "vilka", "bestämmelser"
        ]
        
        if any(indicator in question_lower for indicator in information_indicators):
            logger.info("Rule-based analysis: information question")
            return 'information'
        
        # Default to information if we can't determine
        logger.info("Rule-based analysis: unclear, defaulting to information")
        return 'information'
        
    def _llm_based_analysis(self, question: str, state: Dict[str, Any]) -> Optional[str]:
        """Use LLM to analyze the question"""
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Get conversation context if available
            context = ""
            if "calculation_parameters" in state and state["calculation_parameters"]:
                context = f"Tidigare har användaren frågat om pensionsberäkningar med dessa parametrar: {state['calculation_parameters']}.\n"
            
            system_prompt = (
                "Du är en expert på att analysera frågor om pensioner. "
                "Din uppgift är att avgöra om en fråga handlar om beräkningar eller om allmän information. "
                "Beräkningsfrågor handlar om att beräkna pensionsbelopp, pensionsnivåer, eller andra numeriska värden. "
                "Informationsfrågor handlar om regler, villkor, bestämmelser, eller annan faktabaserad information. "
                "Svara endast med 'calculation' eller 'information'."
            )
            
            # Add context and the question
            query = f"{context}Fråga: {question}"
            
            # Generate the analysis
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ]
            
            response = self.llm.invoke(messages).content.strip().lower()
            
            # Parse the response
            if "calculation" in response:
                logger.info("LLM analysis: calculation question")
                return "calculation"
            elif "information" in response:
                logger.info("LLM analysis: information question")
                return "information"
            else:
                logger.warning(f"Unexpected LLM response: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error in LLM analysis: {str(e)}")
            return None
    
    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a question using the appropriate tool(s)
        
        Args:
            state: The current state containing at least a "question" key
            
        Returns:
            Updated state with a "response" key containing the answer
        """
        question = state.get("question", "")
        if not question:
            state["response"] = "Ingen fråga tillhandahållen."
            return state
        
        logger.info(f"Processing question: {question}")
        state["status"] = "🤔 Analyserar frågan..."
        
        # First, analyze the question to determine its type using both rule-based and LLM analysis
        question_type = self._analyze_question(question, state)
        state["question_type"] = question_type
        logger.info(f"Question type determined as: {question_type}")
        
        # Select tools based on question type
        if question_type == 'calculation':
            # For calculation questions, try calculator first, then fall back to others
            prioritized_tools = [
                tool for tool in self.tools if tool.name == 'calculator'
            ] + [tool for tool in self.tools if tool.name != 'calculator']
        else:
            # For information questions, try summary checker first, then vector retriever
            prioritized_tools = [
                tool for tool in self.tools if tool.name == 'summary_checker'
            ] + [tool for tool in self.tools if tool.name == 'vector_retriever']
        
        # Try each tool in the prioritized order
        for tool in prioritized_tools:
            if tool.can_handle(question, state):
                logger.info(f"Using tool: {tool.name}")
                state["status"] = f"🔧 Använder {tool.name}..."
                state["selected_tool"] = tool.name
                
                try:
                    updated_state = tool.run(question, state)
                    
                    # Check if we got a good result
                    if self._is_good_response(updated_state.get("response", "")):
                        logger.info(f"Got good response from {tool.name}")
                        
                        # If we have an LLM, enhance the response with context awareness
                        if self.llm is not None and "response" in updated_state:
                            enhanced_response = self._enhance_response(question, updated_state)
                            if enhanced_response:
                                updated_state["response"] = enhanced_response
                                logger.info("Enhanced response with LLM")
                        
                        return updated_state
                    
                    # If not, continue with the next tool
                    logger.info(f"Response from {tool.name} not satisfactory, trying next tool")
                
                except Exception as e:
                    logger.error(f"Error using {tool.name}: {str(e)}")
        
        # If no tool provided a good response, use the LLM as a fallback if available
        if not state.get("response") and self.llm is not None:
            try:
                fallback_response = self._generate_fallback_response(question, state)
                if fallback_response:
                    state["response"] = fallback_response
                    state["response_source"] = "llm_fallback"
                    logger.info("Generated fallback response using LLM")
                    return state
            except Exception as e:
                logger.error(f"Error generating fallback response: {str(e)}")
        
        # Final fallback
        if not state.get("response"):
            state["response"] = "Tyvärr kan jag inte svara på den frågan just nu."
            
        return state
        
    def _enhance_response(self, question: str, state: Dict[str, Any]) -> Optional[str]:
        """Enhance the response with context awareness using LLM"""
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Get the original response
            original_response = state.get("response", "")
            if not original_response:
                return None
                
            # Get context from state
            context = ""
            if "calculation_parameters" in state and state["calculation_parameters"]:
                context += f"Användaren har följande beräkningsparametrar: {state['calculation_parameters']}.\n"
            
            if "selected_tool" in state:
                context += f"Svaret genererades av verktyget: {state['selected_tool']}.\n"
                
            if "question_type" in state:
                context += f"Frågetyp: {state['question_type']}.\n"
            
            # If we don't have meaningful context, return the original response
            if not context.strip():
                return original_response
            
            system_prompt = (
                "Du är en pensionsrådgivare som hjälper till att förbättra svar på frågor om pensioner. "
                "Din uppgift är att förbättra det befintliga svaret genom att göra det mer relevant för användarens fråga "
                "och ta hänsyn till kontexten. Svara på svenska och var hjälpsam, koncis och korrekt. "
                "Bevara all faktainformation i originalsvaret, men förbättra formuleringen och relevansen."
            )
            
            prompt = f"""Fråga: {question}

Kontext:
{context}

Befintligt svar:
{original_response}

Förbättrat svar:"""
            
            # Generate the enhanced response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            response = self.llm.invoke(messages).content
            return response
            
        except Exception as e:
            logger.error(f"Error enhancing response: {str(e)}")
            return original_response
    
    def _generate_fallback_response(self, question: str, state: Dict[str, Any]) -> Optional[str]:
        """Generate a fallback response using the LLM when no tool could handle the question"""
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            system_prompt = (
                "Du är en pensionsrådgivare som hjälper till att svara på frågor om pensioner och pensionsavtal. "
                "Du ska svara på svenska och vara hjälpsam, koncis och korrekt. "
                "Om du inte kan besvara frågan med säkerhet, var ärlig med det och förklara varför."
            )
            
            # Generate the fallback response
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question)
            ]
            
            response = self.llm.invoke(messages).content
            return response
            
        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return None
    
    def _is_good_response(self, response: str) -> bool:
        """Check if a response is good enough to return to the user"""
        if not response:
            return False
            
        # Check for common failure indicators
        bad_indicators = [
            "tyvärr",
            "kan inte svara",
            "vet inte",
            "har inte information",
            "förstår inte"
        ]
        
        # Convert to lowercase for case-insensitive matching
        response_lower = response.lower()
        
        # If any bad indicators are found, consider it a bad response
        for indicator in bad_indicators:
            if indicator in response_lower:
                return False
                
        # Check minimum length (arbitrary threshold)
        if len(response.strip()) < 20:
            return False
            
        return True
