from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import logging
from src.graph.state import GraphState, AgentState

logger = logging.getLogger(__name__)


class RecommendationAgent:
    """Agent for generating personalized pension recommendations"""
    def __init__(self):
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0.2)

    def generate_recommendations(self, state: GraphState) -> GraphState:
        try:
            user_profile = state.get("user_profile", {})
            analysis = state.get("analysis", "")
            calculations = state.get("calculations", "")

            if not user_profile or not analysis:
                return GraphState(
                    **state,
                    response="Jag behöver mer information för att kunna ge personliga rekommendationer.",
                    state=AgentState.GATHERING_INFO.value
                )

            system_prompt = (
                """Du är en expert på pensionsrådgivning i Sverige.
                Baserat på användarens profil, analys och beräkningar, ge personliga rekommendationer.
                Var konkret och ge praktiska råd som användaren kan följa.
                Förklara varför dina rekommendationer är lämpliga för just denna person.
                Avsluta med att fråga om användaren har några frågor om rekommendationerna."""
            )

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
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03
        completion_cost = (usage.completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost
