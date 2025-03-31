from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
import logging
from src.graph.state import GraphState, AgentState

logger = logging.getLogger(__name__)

class FeedbackAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1
        )

    def process_feedback(self, state: GraphState) -> GraphState:
        try:
            feedback = state.get("question", "")
            previous_response = state.get("response", "")

            system_prompt = (
                """Du är en expert på pensionsrådgivning i Sverige.
                En användare har gett feedback på ett tidigare svar. Analysera feedbacken och ge ett förbättrat svar.
                Var lyhörd för användarens behov och anpassa ditt svar därefter.
                Om användaren verkar nöjd, fortsätt att bygga på det tidigare svaret med mer värdefull information."""
            )

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

            usage = response.usage
            state["token_usage"].append({
                "agent_type": "feedback",
                "action": "process_feedback",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })

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
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03
        completion_cost = (usage.completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost
