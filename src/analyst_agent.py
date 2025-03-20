from typing import TYPE_CHECKING, Dict, List, Tuple, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import logging

if TYPE_CHECKING:
    from .document_processor import DocumentProcessor  # Conditional import
    from .multi_agent_graph import GraphState  # Import only for type checking
    from .multi_agent_graph import AgentState  # Import to avoid missing reference

logger = logging.getLogger(__name__)


class PensionAnalystAgent:
    def __init__(self, doc_processor: "DocumentProcessor"):  # Use string annotation
        self.llm = ChatOpenAI(temperature=0.2, model="gpt-4")
        self.doc_processor = doc_processor

    def analyze_agreement_info(self, agreement: str) -> Dict[str, Any]:
        """Analyze and retrieve information about the agreement."""
        # Example questions to ask the LLM
        questions = [
            f"Do I know the agreement {agreement}?",
            f"What is the full name of the agreement {agreement}?",
            f"What user group is the agreement {agreement} for?"
        ]
        
        responses = {}
        
        for question in questions:
            response = self.llm.invoke([SystemMessage(content=question)])
            responses[question] = response.content
        
        return responses
    def analyze_needs(self, state: "GraphState") -> "GraphState":
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
            system_prompt = """Du är SIWRA, en varm, självsäker och engagerande pensionsrådgivare som specialiserar sig på pensionsavtal.
            Ditt mål är att hjälpa användaren att förstå olika pensionsavtal och ge råd baserat på deras specifika situation. 
            Använd information från alla tillgängliga avtal för att ge så precisa och användbara svar som möjligt."""
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

    def generate_advice(self, state: "GraphState") -> "GraphState":

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