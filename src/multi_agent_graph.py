"""
Multi-agent pension advisor system with specialized agents for different tasks.
"""
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum
import json
import uuid
import logging
from dataclasses import dataclass, field
import datetime
import re

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from .agent import PensionAdvisor
from .document_processor import DocumentProcessor
from .cost_tracker import cost_tracker, TokenUsage, AgentCostLog
from .error_analyzer import error_analyzer, ErrorType
from .presentation_db import presentation_db

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentState(Enum):
    """States in our multi-agent system"""
    STARTING = "starting"
    GATHERING_INFO = "gathering_info"
    NEEDS_MORE_INFO = "needs_more_info"
    ANALYZING_NEEDS = "analyzing_needs"
    RETRIEVING_CONTEXT = "retrieving_context"
    CALCULATING = "calculating"
    GENERATING_ADVICE = "generating_advice"
    ANALYZING_ERROR = "analyzing_error"
    RECOVERING = "recovering"
    AWAITING_FEEDBACK = "awaiting_feedback"
    FINISHED = "finished"
    ERROR = "error"

@dataclass
class UserProfile:
    """Store user information gathered during conversation"""
    age: Optional[int] = None
    current_salary: Optional[float] = None
    employment_type: Optional[str] = None
    years_of_service: Optional[int] = None
    retirement_goals: List[str] = field(default_factory=list)
    risk_tolerance: Optional[str] = None
    family_situation: Optional[str] = None
    current_pension_plans: List[str] = field(default_factory=list)

class GraphState(dict):
    """State object for our graph"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setdefault("conversation_id", str(uuid.uuid4()))
        self.setdefault("token_usage", [])
        self.setdefault("state", AgentState.STARTING.value)
        self.setdefault("user_profile", {})

class ConversationalAgent:
    """Friendly agent that gathers user information naturally"""
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-4"
        )
        
    def generate_response(self, state: GraphState) -> GraphState:
        try:
            # Get the required information from the presentation database
            required_fields = presentation_db.get_required_factors()
            
            # Extract user profile information from state
            user_profile = state.get("user_profile", {})
            
            # Check which required fields are missing
            missing_fields = [field.name for field in required_fields 
                             if field.name not in user_profile]
            
            # Prepare system message based on missing fields
            if missing_fields:
                system_message = f"""Du är en vänlig pensionsrådgivare som samlar information.
                Var artig och ge komplimanger när det passar. Försök att få information om följande:
                {', '.join(missing_fields)}.
                
                Samla denna information på ett naturligt sätt genom konversation.
                Om användaren inte vill dela mer information, respektera detta och gå vidare."""
            else:
                system_message = """Du är en vänlig pensionsrådgivare.
                Tack användaren för informationen och meddela att du kommer att analysera deras pensionssituation."""
            
            # Generate response using LLM
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=state["question"])
            ]
            
            # Add conversation history if available
            conversation_history = state.get("conversation_history", [])
            if conversation_history:
                messages = [SystemMessage(content=system_message)] + conversation_history + [HumanMessage(content=state["question"])]
            
            try:
                response = self.llm.invoke(messages)
                
                # Track token usage
                usage = response.usage
                state["token_usage"].append({
                    "agent_type": "conversational",
                    "action": "generate_response",
                    "conversation_id": state["conversation_id"],
                    "token_usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                        "cost": self._calculate_cost(usage)
                    }
                })
                
                # Update conversation history
                if "conversation_history" not in state:
                    state["conversation_history"] = []
                
                # Add this exchange to the conversation history
                state["conversation_history"].append(HumanMessage(content=state["question"]))
                state["conversation_history"].append(AIMessage(content=response.content))
                
                # Extract information from the conversation
                self._extract_user_info(state, state["question"])
                
                # Check if we have all required information or user wants to stop
                has_all_info = not missing_fields
                wants_to_stop = "sluta" in state["question"].lower() or "avsluta" in state["question"].lower()
                
                next_state = AgentState.ANALYZING_NEEDS.value if (has_all_info or wants_to_stop) else AgentState.GATHERING_INFO.value
                
                return GraphState(
                    **state,
                    response=response.content,
                    state=next_state
                )
            except Exception as e:
                # Handle specific API errors
                logger.error(f"LLM API error: {str(e)}")
                # Provide a fallback response for the first message
                if not conversation_history:
                    fallback_response = "Hej! Jag är din pensionsrådgivare. Hur kan jag hjälpa dig idag? Du kan fråga mig om din pension eller berätta lite om din situation så jag kan ge dig personliga råd."
                    
                    # Create a minimal state with the fallback response
                    return GraphState(
                        **state,
                        response=fallback_response,
                        state=AgentState.GATHERING_INFO.value
                    )
                else:
                    # Re-raise the exception if it's not the first message
                    raise e
                
        except Exception as e:
            logger.error(f"Error in conversational agent: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )

    def _extract_user_info(self, state: GraphState, message: str) -> None:
        """Extract user information from the message"""
        user_profile = state.get("user_profile", {})
        
        # Simple pattern matching for age
        if "år" in message.lower() or "ålder" in message.lower():
            # Extract numbers from the message
            import re
            numbers = re.findall(r'\d+', message)
            if numbers:
                # Assume the first number between 18 and 100 is the age
                for num in numbers:
                    if 18 <= int(num) <= 100:
                        user_profile["age"] = int(num)
                        break
        
        # Simple pattern matching for salary
        if "lön" in message.lower() or "tjänar" in message.lower() or "kronor" in message.lower() or "kr" in message.lower():
            # Extract numbers from the message
            import re
            numbers = re.findall(r'\d+\s*\d*', message)
            if numbers:
                # Remove spaces and convert to int
                for num_str in numbers:
                    num = int(num_str.replace(" ", ""))
                    # Assume the largest number is the salary
                    if num > 10000 and num < 200000:  # Reasonable monthly salary range in SEK
                        user_profile["current_salary"] = num
                        break
        
        # Simple pattern matching for employment type
        employment_keywords = {
            "offentlig": "public",
            "kommun": "public",
            "landsting": "public",
            "stat": "public",
            "privat": "private",
            "företag": "private",
            "egen": "self-employed",
            "egenföretagare": "self-employed",
            "frilans": "self-employed"
        }
        
        for keyword, emp_type in employment_keywords.items():
            if keyword in message.lower():
                user_profile["employment_type"] = emp_type
                break
        
        # Extract retirement goals
        retirement_keywords = ["pensionera", "pension", "sluta arbeta", "gå i pension"]
        if any(keyword in message.lower() for keyword in retirement_keywords):
            # Try to extract retirement age
            age_pattern = r'(\d+)\s*(?:års? ålder|år)'
            matches = re.findall(age_pattern, message.lower())
            if matches:
                retirement_age = int(matches[0])
                if 55 <= retirement_age <= 75:  # Reasonable retirement age range
                    if "retirement_goals" not in user_profile:
                        user_profile["retirement_goals"] = []
                    user_profile["retirement_goals"].append(f"Retire at age {retirement_age}")
        
        # Extract risk tolerance
        risk_keywords = {
            "låg risk": "low",
            "försiktig": "low",
            "säker": "low",
            "mellan risk": "medium",
            "balanserad": "medium",
            "hög risk": "high",
            "aggressiv": "high",
            "chansa": "high"
        }
        
        for keyword, risk_level in risk_keywords.items():
            if keyword in message.lower():
                user_profile["risk_tolerance"] = risk_level
                break
        
        # Extract family situation
        family_keywords = ["gift", "sambo", "partner", "barn", "familj", "ensam", "singel"]
        if any(keyword in message.lower() for keyword in family_keywords):
            # Simple extraction of family situation
            if "gift" in message.lower() or "sambo" in message.lower() or "partner" in message.lower():
                family_status = "married/partner"
            elif "singel" in message.lower() or "ensam" in message.lower():
                family_status = "single"
            else:
                family_status = "has family"
                
            user_profile["family_situation"] = family_status
            
            # Try to extract number of children
            children_pattern = r'(\d+)\s*(?:barn|kids|children)'
            matches = re.findall(children_pattern, message.lower())
            if matches:
                user_profile["children"] = int(matches[0])
        
        # Update the state with the extracted information
        state["user_profile"] = user_profile

    # Calculate cost based on GPT-4 pricing
    def _calculate_cost(self, usage):
        # GPT-4 pricing: $0.03/1K prompt tokens, $0.06/1K completion tokens
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03
        completion_cost = (usage.completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost

class PensionAnalystAgent:
    """Expert agent that analyzes gathered information and pension rules"""
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0.2,
            model="gpt-4"
        )
        self.advisor = PensionAdvisor()
        
    def analyze_needs(self, state: GraphState) -> GraphState:
        try:
            # Get user profile information
            user_profile = state.get("user_profile", {})
            
            # If user profile is empty, return a friendly message
            if not user_profile:
                return GraphState(
                    **state,
                    response="Jag har inte tillräckligt med information för att analysera dina pensionsbehov. Kan du berätta lite mer om din situation?",
                    state=AgentState.GATHERING_INFO.value
                )
            
            # Create a user-friendly summary of the collected information
            profile_summary = []
            if "age" in user_profile:
                profile_summary.append(f"Ålder: {user_profile['age']} år")
            if "current_salary" in user_profile:
                profile_summary.append(f"Lön: {user_profile['current_salary']} kr/månad")
            if "employment_type" in user_profile:
                emp_type = user_profile['employment_type']
                emp_type_swedish = {
                    "public": "offentlig sektor",
                    "private": "privat sektor",
                    "self-employed": "egenföretagare"
                }.get(emp_type, emp_type)
                profile_summary.append(f"Anställningstyp: {emp_type_swedish}")
            
            # Generate analysis using LLM
            system_prompt = """Du är en expert på pensionsanalys i Sverige.
            Baserat på den information du har, ge en kort och tydlig analys av personens pensionssituation.
            Var pedagogisk och förklara på ett sätt som är lätt att förstå.
            Om du saknar viktig information, nämn det och förklara varför den informationen är viktig."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Analysera följande information om en person:\n{', '.join(profile_summary)}")
            ]
            
            response = self.llm.invoke(messages)
            
            # Track token usage
            usage = response.usage
            state["token_usage"].append({
                "agent_type": "analyst",
                "action": "analyze_needs",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })
            
            # Create a response that acknowledges the user's information and provides analysis
            final_response = f"""Tack för informationen! Baserat på det du berättat kan jag ge dig följande analys:

{response.content}

Vill du ha mer specifika råd om din pensionssituation?"""
            
            return GraphState(
                **state,
                analysis=response.content,
                response=final_response,
                state=AgentState.ANALYZING_NEEDS.value
            )
            
        except Exception as e:
            logger.error(f"Error in analyst agent: {str(e)}", exc_info=True)
            return GraphState(
                **state,
                error=str(e),
                response="Tyvärr kunde jag inte analysera din pensionssituation just nu. Kan vi försöka igen?",
                state=AgentState.ERROR.value
            )

    def generate_advice(self, state: GraphState) -> GraphState:
        try:
            # Generate professional advice based on analysis
            messages = [
                SystemMessage(content="Du är en expert på att ge pensionsråd."),
                HumanMessage(content=f"Ge råd baserat på denna analys: {state['analysis']}")
            ]
            
            response = self.llm.invoke(messages)
            
            # Track token usage
            usage = response.usage
            state["token_usage"].append({
                "agent_type": "analyst",
                "action": "generate_advice",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })
            
            return GraphState(
                **state,
                response=response.content,
                state=AgentState.GENERATING_ADVICE.value
            )
            
        except Exception as e:
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )

    def _calculate_cost(self, usage) -> float:
        """Calculate cost based on GPT-4 pricing"""
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        completion_cost = (usage.completion_tokens / 1000) * 0.06  # $0.06 per 1K tokens
        return prompt_cost + completion_cost

class CalculationAgent:
    """Agent for performing pension calculations"""
    def __init__(self):
        """Initialize the calculation agent"""
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0
        )
        
    def calculate_pension(self, state: GraphState) -> GraphState:
        try:
            # Get user profile information
            user_profile = state.get("user_profile", {})
            
            # If user profile is empty, return a friendly message
            if not user_profile:
                return GraphState(
                    **state,
                    response="Jag har inte tillräckligt med information för att göra beräkningar. Kan du berätta mer om din situation?",
                    state=AgentState.GATHERING_INFO.value
                )
            
            # Generate calculations using LLM
            system_prompt = """Du är en expert på pensionsberäkningar i Sverige.
            Baserat på den information du har, gör en uppskattning av personens pension.
            Förklara dina beräkningar på ett pedagogiskt sätt.
            Om du saknar viktig information för att göra en bra beräkning, nämn det."""
            
            # Create a summary of user information
            profile_summary = []
            for key, value in user_profile.items():
                profile_summary.append(f"{key}: {value}")
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Beräkna pension baserat på följande information:\n{', '.join(profile_summary)}")
            ]
            
            response = self.llm.invoke(messages)
            
            # Track token usage
            usage = response.usage
            state["token_usage"].append({
                "agent_type": "calculation",
                "action": "calculate_pension",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })
            
            return GraphState(
                **state,
                calculations=response.content,
                state=AgentState.CALCULATING.value
            )
            
        except Exception as e:
            logger.error(f"Error in calculation agent: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )
    
    def _calculate_cost(self, usage) -> float:
        """Calculate cost based on GPT-4 pricing"""
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        completion_cost = (usage.completion_tokens / 1000) * 0.06  # $0.06 per 1K tokens
        return prompt_cost + completion_cost

class RecommendationAgent:
    """Agent for generating personalized pension recommendations"""
    def __init__(self):
        """Initialize the recommendation agent"""
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.2
        )
        
    def generate_recommendations(self, state: GraphState) -> GraphState:
        try:
            # Get user profile, analysis and calculations
            user_profile = state.get("user_profile", {})
            analysis = state.get("analysis", "")
            calculations = state.get("calculations", "")
            
            # If we don't have enough information, return a message
            if not user_profile or not analysis:
                return GraphState(
                    **state,
                    response="Jag behöver mer information för att kunna ge personliga rekommendationer.",
                    state=AgentState.GATHERING_INFO.value
                )
            
            # Generate recommendations using LLM
            system_prompt = """Du är en expert på pensionsrådgivning i Sverige.
            Baserat på användarens profil, analys och beräkningar, ge personliga rekommendationer.
            Var konkret och ge praktiska råd som användaren kan följa.
            Förklara varför dina rekommendationer är lämpliga för just denna person.
            Avsluta med att fråga om användaren har några frågor om rekommendationerna."""
            
            # Create a summary of all information
            context = f"""
            ANVÄNDARPROFIL:
            {json.dumps(user_profile, indent=2, ensure_ascii=False)}
            
            ANALYS:
            {analysis}
            
            BERÄKNINGAR:
            {calculations}
            """
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Ge personliga pensionsrekommendationer baserat på följande information:\n{context}")
            ]
            
            response = self.llm.invoke(messages)
            
            # Track token usage
            usage = response.usage
            state["token_usage"].append({
                "agent_type": "recommendation",
                "action": "generate_recommendations",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })
            
            return GraphState(
                **state,
                recommendations=response.content,
                response=response.content,
                state=AgentState.GENERATING_RECOMMENDATIONS.value
            )
            
        except Exception as e:
            logger.error(f"Error in recommendation agent: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )
    
    def _calculate_cost(self, usage) -> float:
        """Calculate cost based on GPT-4 pricing"""
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        completion_cost = (usage.completion_tokens / 1000) * 0.06  # $0.06 per 1K tokens
        return prompt_cost + completion_cost

class FeedbackHandler:
    """Handler for processing user feedback"""
    def __init__(self):
        """Initialize the feedback handler"""
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1
        )
        
    def process_feedback(self, state: GraphState) -> GraphState:
        try:
            # Get the feedback (latest question) and previous response
            feedback = state.get("question", "")
            previous_response = state.get("response", "")
            
            # Generate improved response using LLM
            system_prompt = """Du är en expert på pensionsrådgivning i Sverige.
            En användare har gett feedback på ett tidigare svar. Analysera feedbacken och ge ett förbättrat svar.
            Var lyhörd för användarens behov och anpassa ditt svar därefter.
            Om användaren verkar nöjd, fortsätt att bygga på det tidigare svaret med mer värdefull information."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"""
                TIDIGARE SVAR:
                {previous_response}
                
                ANVÄNDARENS FEEDBACK:
                {feedback}
                
                Ge ett förbättrat svar baserat på denna feedback:
                """)
            ]
            
            response = self.llm.invoke(messages)
            
            # Track token usage
            usage = response.usage
            state["token_usage"].append({
                "agent_type": "feedback_handler",
                "action": "process_feedback",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })
            
            # Update conversation history
            if "conversation_history" not in state:
                state["conversation_history"] = []
            
            state["conversation_history"].append(HumanMessage(content=feedback))
            state["conversation_history"].append(AIMessage(content=response.content))
            
            return GraphState(
                **state,
                response=response.content,
                state=AgentState.FINISHED.value
            )
            
        except Exception as e:
            logger.error(f"Error in feedback handler: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )
    
    def _calculate_cost(self, usage) -> float:
        """Calculate cost based on GPT-4 pricing"""
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        completion_cost = (usage.completion_tokens / 1000) * 0.06  # $0.06 per 1K tokens
        return prompt_cost + completion_cost

class PensionAdvisorGraph:
    def __init__(self):
        self.conversational_agent = ConversationalAgent()
        self.analyst_agent = PensionAnalystAgent()
        self.calculation_agent = CalculationAgent()
        self.recommendation_agent = RecommendationAgent()
        self.feedback_handler = FeedbackHandler()

    def should_analyze_needs(self, state: GraphState) -> str:
        """Determine if we should move to analyzing needs"""
        # If the state is set to ANALYZING_NEEDS, move to the next step
        if state.get("state") == AgentState.ANALYZING_NEEDS.value:
            return "analyze_needs"
        
        # Check if we have all required information
        required_fields = presentation_db.get_required_factors()
        user_profile = state.get("user_profile", {})
        missing_fields = [field.name for field in required_fields 
                         if field.name not in user_profile]
        
        # If we have all required information or user wants to stop, move to analyze_needs
        wants_to_stop = state.get("question", "").lower()
        wants_to_stop = "sluta" in wants_to_stop or "avsluta" in wants_to_stop
        
        if not missing_fields or wants_to_stop:
            return "analyze_needs"
            
        # Otherwise, continue gathering information
        return "gather_info"
    
    def should_generate_recommendations(self, state: GraphState) -> str:
        """Determine if we should move to generating recommendations"""
        # If we have calculations, move to recommendations
        if state.get("calculations"):
            return "generate_recommendations"
        # Otherwise, continue with advice
        return "generate_advice"
    
    def should_process_feedback(self, state: GraphState) -> str:
        """Determine if we should process feedback"""
        # If we're awaiting feedback and received a new message, process it
        if state.get("state") == AgentState.AWAITING_FEEDBACK.value and state.get("question"):
            return "process_feedback"
        # Otherwise, continue with the normal flow
        return "continue"

    def handle_error(self, state: GraphState) -> GraphState:
        """Handle errors using the error analyzer"""
        try:
            # Get the error from state
            error = state.get("error", "Unknown error")
            
            # Analyze the error
            analysis = error_analyzer.analyze_error(error, state)
            
            # Update presentation database
            error_analyzer.update_presentation_db(analysis, state)
            
            if analysis.can_recover:
                if analysis.error_type == ErrorType.MISSING_INFO:
                    # Update state with missing factors and return to conversation
                    return GraphState(
                        **state,
                        missing_factors=analysis.missing_factors,
                        response=analysis.user_message,
                        state=AgentState.GATHERING_INFO.value
                    )
                elif analysis.error_type == ErrorType.CALCULATION_ERROR:
                    # Return to calculation with adjusted parameters
                    return GraphState(
                        **state,
                        response=analysis.user_message,
                        state=AgentState.CALCULATING.value
                    )
            
            # If we can't recover, end with error message
            return GraphState(
                **state,
                response=analysis.user_message,
                state=AgentState.ERROR.value
            )
            
        except Exception as e:
            logger.error(f"Error in error handling: {str(e)}")
            return GraphState(
                **state,
                response="Tyvärr uppstod ett fel. Vårt team har notifierats.",
                state=AgentState.ERROR.value
            )

    def create_graph(self):
        """Create the multi-agent workflow graph"""
        # Define the nodes in our graph
        builder = StateGraph(GraphState)
        
        # Add nodes for each agent
        builder.add_node("gather_info", self.conversational_agent.generate_response)
        builder.add_node("analyze_needs", self.analyst_agent.analyze_needs)
        builder.add_node("calculate", self.calculation_agent.calculate_pension)
        builder.add_node("generate_advice", self.analyst_agent.generate_advice)
        builder.add_node("process_feedback", self.feedback_handler.process_feedback)
        builder.add_node("handle_error", self.handle_error)
        
        # Add conditional edges
        builder.add_conditional_edges(
            "gather_info",
            self.should_analyze_needs,
            {
                True: "analyze_needs",
                False: "gather_info"
            }
        )
        
        # Add normal flow edges
        builder.add_edge("analyze_needs", "calculate")
        builder.add_edge("calculate", "generate_advice")
        builder.add_edge("generate_advice", END)
        builder.add_edge("process_feedback", END)
        
        # Set the entry point
        builder.set_entry_point("gather_info")
        
        return builder.compile()

    def run_with_visualization(self, question: str) -> Tuple[str, List[Dict]]:
        """Run the graph with visualization data"""
        try:
            logger.info(f"Creating graph for question: {question}")
            graph = self.create_graph()
            
            # Check if this is a continuation of an existing conversation
            if hasattr(self, 'current_state') and self.current_state:
                logger.info("Continuing existing conversation")
                # Update the existing state with the new question
                state = self.current_state
                state["question"] = question
                logger.debug(f"Current state: {state.get('state', 'UNKNOWN')}")
                logger.debug(f"Conversation history length: {len(state.get('conversation_history', []))}")
                
                # Add the user's message to conversation history
                state["conversation_history"].append(HumanMessage(content=question))
                
                # For short responses like "yes", "no", "javisst", etc., use direct response
                if len(question.strip().split()) <= 2:
                    logger.info(f"Short response detected: '{question}'. Using direct response.")
                    response = self._generate_direct_response(question, state["conversation_history"])
                    
                    # Add the response to conversation history
                    state["conversation_history"].append(AIMessage(content=response))
                    state["response"] = response
                    
                    # Store the updated state for the next interaction
                    self.current_state = state
                    
                    return response, []
                
                # Use the conversational agent to generate a response
                try:
                    logger.info("Invoking graph with state")
                    result = graph.invoke(state)
                    logger.info(f"Graph execution completed with state: {result.get('state', 'UNKNOWN')}")
                    
                    # Store the current state for the next interaction
                    self.current_state = result
                    
                    # Get the final response
                    response = result.get("response", "")
                    
                    # If no response was generated but there's an error, use the error analyzer
                    if not response and result.get("error"):
                        logger.warning(f"No response generated but error found: {result.get('error')}")
                        error_analysis = error_analyzer.analyze_error(result.get("error"), result)
                        response = error_analysis.user_message
                    
                    # If still no response, provide a default one
                    if not response:
                        logger.warning("No response generated, using default")
                        response = "Jag förstår. Kan du berätta mer om din situation så jag kan hjälpa dig bättre?"
                    
                    # Return response and visualization data
                    logger.info(f"Returning response: {response[:100]}...")
                    return response, []
                    
                except Exception as e:
                    logger.error(f"Error in graph execution: {str(e)}", exc_info=True)
                    
                    # Use direct response as fallback
                    logger.info("Using direct response as fallback")
                    response = self._generate_direct_response(question, state["conversation_history"])
                    
                    # Add the response to conversation history
                    state["conversation_history"].append(AIMessage(content=response))
                    state["response"] = response
                    
                    # Store the updated state for the next interaction
                    self.current_state = state
                    
                    return response, []
            else:
                logger.info("Starting new conversation")
                # For the first interaction, use direct response
                conversation_history = [HumanMessage(content=question)]
                response = self._generate_direct_response(question, conversation_history)
                
                # Initialize state for next interaction
                state = GraphState(
                    question=question,
                    conversation_id=str(uuid.uuid4()),
                    state=AgentState.STARTING.value,
                    token_usage=[],
                    user_profile={},
                    response=response,
                    conversation_history=conversation_history + [AIMessage(content=response)]
                )
                
                # Store the state for the next interaction
                self.current_state = state
                
                return response, []
            
        except Exception as e:
            logger.error(f"Critical error in graph execution: {str(e)}", exc_info=True)
            return "Tyvärr uppstod ett fel. Vårt team har notifierats.", []
    
    def _generate_direct_response(self, question: str, conversation_history: List) -> str:
        """Generate a direct response to a question using embeddings first, then LLM"""
        try:
            logger.info(f"Generating direct response for: {question}")
            
            # First, query the vector store for relevant information
            relevant_info = ""
            try:
                # Use document processor to query vector store
                from .document_processor import DocumentProcessor
                doc_processor = DocumentProcessor()
                
                # Get relevant documents from vector store
                docs = doc_processor.query_documents(question, top_k=3)
                
                if docs:
                    # Extract the content from the documents
                    relevant_info = "\n\n".join([f"Document: {doc.metadata.get('source', 'Unknown')}\nContent: {doc.page_content}" for doc in docs])
                    logger.info(f"Found {len(docs)} relevant documents for query")
                else:
                    logger.info("No relevant documents found in vector store")
            except Exception as e:
                logger.error(f"Error querying vector store: {str(e)}", exc_info=True)
                relevant_info = ""
            
            # Use the analyst agent's LLM to generate a response
            llm = ChatOpenAI(
                model_name="gpt-4",
                temperature=0.5
            )
            
            system_prompt = """Du är SIWRA, en varm, självsäker och engagerande pensionsrådgivare som specialiserar sig på AKAP-KR avtalet.
            
            VIKTIGT: 
            1. Var ALLTID POSITIV och SJÄLVSÄKER i dina svar. Undvik fraser som "Som en AI kan jag inte..."
            2. Håll dina svar KORTA och KONCISA - max 2-3 meningar.
            3. Använd ett VARMT och PERSONLIGT språk, som om du pratar med en vän.
            4. Använd KOMPLIMANGER och visa UPPSKATTNING för användarens frågor.
            5. Om du inte har personlig information, säg något som: "Jag känner inte till dina personliga detaljer ännu, men jag skulle älska att lära mig mer så jag kan ge dig personlig rådgivning!"
            6. Nämn AKAP-KR eller andra specifika avtal när det är relevant.
            
            Om frågan är om personlig pension, visa ENTUSIASM för att hjälpa och be om mer information på ett VARMT sätt."""
            
            # Include relevant information in the prompt if available
            if relevant_info:
                system_prompt += f"\n\nRelevant information från dokument:\n{relevant_info}"
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question)
            ]
            
            # Add conversation history to the prompt
            if conversation_history:
                messages = [SystemMessage(content=system_prompt)] + conversation_history + [HumanMessage(content=question)]
            
            response = llm.invoke(messages)
            
            # Ensure response is concise (truncate if necessary)
            content = response.content
            if len(content) > 500:
                sentences = content.split('.')
                shortened = '.'.join(sentences[:3]) + '.'
                logger.info(f"Shortened response from {len(content)} to {len(shortened)} characters")
                content = shortened
            
            logger.info(f"Generated direct response: {content[:100]}...")
            
            return content
            
        except Exception as e:
            logger.error(f"Error generating direct response: {str(e)}", exc_info=True)
            return "Jag kan tyvärr inte svara på den frågan just nu. Kan du omformulera?"

def main():
    """Example usage"""
    advisor = PensionAdvisorGraph()
    
    # Example conversation
    questions = [
        "Jag funderar på min pension",  # Initial inquiry
        "Jag är 45 år och jobbar som lärare",  # Basic info
        "Jag tjänar 42000 kr i månaden",  # Salary info
        "Jag vill gärna pensionera mig vid 65",  # Retirement goal
    ]
    
    for question in questions:
        response, graph_data = advisor.run_with_visualization(question)
        print(f"\nUser: {question}")
        print(f"Advisor: {response}")
        print("Graph state:", graph_data)

if __name__ == "__main__":
    main()
