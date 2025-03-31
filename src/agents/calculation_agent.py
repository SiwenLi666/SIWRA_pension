from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
import logging
from src.graph.state import GraphState, AgentState

logger = logging.getLogger(__name__)

class CalculationAgent:
    """Agent for performing pension calculations"""
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0
        )

    def calculate_pension(self, state: GraphState) -> GraphState:
        try:
            user_profile = state.get("user_profile", {})
            if not user_profile:
                return GraphState(
                    **state,
                    response="Jag har inte tillräckligt med information för att göra beräkningar. Kan du berätta mer om din situation?",
                    state=AgentState.GATHERING_INFO.value
                )

            system_prompt = (
                """Du är en expert på pensionsberäkningar i Sverige.
                Baserat på den information du har, gör en uppskattning av personens pension.
                Förklara dina beräkningar på ett pedagogiskt sätt.
                Om du saknar viktig information för att göra en bra beräkning, nämn det."""
            )

            profile_summary = [f"{key}: {value}" for key, value in user_profile.items()]

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Beräkna pension baserat på följande information:\n{', '.join(profile_summary)}")
            ]

            response = self.llm.invoke(messages)
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
                response=response.content,
                state=AgentState.CALCULATING.value
            )

        except Exception as e:
            logger.error(f"Error in calculation agent: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                response="Tyvärr kunde jag inte räkna just nu.",
                state=AgentState.ERROR.value
            )

    def _calculate_cost(self, usage) -> float:
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03
        completion_cost = (usage.completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost
