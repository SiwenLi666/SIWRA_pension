# src/agents/conversational_agent.py

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState, AgentState, UserProfile
import logging
import re
import json

logger = logging.getLogger('conversational_agents')

class ConversationalAgent:
    def __init__(self):
        # Create a logger named "siwra" (or any name you like)
        self.llm = ChatOpenAI(temperature=0.7, model="gpt-4")
        self.logger = logging.getLogger("siwra")

    def generate_response(self, state: GraphState) -> GraphState:
        """Gather required user info or proceed to analysis if all fields are present."""

        # 1) Log entry to function
        self.logger.info("[gather_info] Entering ConversationalAgent.generate_response")

        # 2) Dynamically fetch your required fields from the UserProfile class
        required_fields = UserProfile.required_fields()
        user_profile = state.get("user_profile", {})

        missing_fields = []
        for field_name in required_fields:
            # If user_profile doesn't have that key OR it's None, call it missing
            if field_name not in user_profile or user_profile[field_name] is None:
                missing_fields.append(field_name)

        # 3) Log the missing fields for clarity
        if missing_fields:
            self.logger.debug(f"[gather_info] Missing fields: {missing_fields}")

        # 4) Construct the system message
        if missing_fields:
            system_message_content = (
                f"Du är en vänlig pensionsrådgivare. "
                f"Var artig och samla in följande uppgifter: {', '.join(missing_fields)}."
            )
        else:
            system_message_content = (
                "Tack för informationen! Jag har allt jag behöver för att analysera pensionen."
            )

        system_message = SystemMessage(content=system_message_content)

        # 5) Build messages
        conversation_history = state.get("conversation_history", [])
        question =  state.get("question", "")
        messages = [system_message] + conversation_history + [HumanMessage(content=question)]

        # 6) Invoke LLM
        try:
            response = self.llm.invoke(messages)
            # (Optional) track usage with _track_usage if you like

            # 7) Update the conversation history
            conversation_history.extend([
                HumanMessage(content=question),
                AIMessage(content=response.content)
            ])

            # 8) Decide next state
            if missing_fields:
                next_state = AgentState.GATHERING_INFO.value
                self.logger.info("[gather_info] Missing fields found → staying in GATHERING_INFO")
            else:
                next_state = AgentState.ANALYZING_NEEDS.value
                self.logger.info("[gather_info] No missing fields → moving to ANALYZING_NEEDS")

            # 9) Return updated state
            self.logger.info("[gather_info] Finished generating response")
            return GraphState(
                **state,
                conversation_history=conversation_history,
                user_profile=user_profile,
                response=response.content,
                state=next_state
            )

        except Exception as e:
            self.logger.error(f"[gather_info] LLM error: {str(e)}")
            return GraphState(
                **state,
                response="Ett fel uppstod, kan du upprepa din fråga?",
                state=AgentState.ERROR.value
            )

    def _extract_user_info(self, state: GraphState, message: str) -> None:
        """Optional method for auto-filling user_profile from numeric details in the message."""
        user_profile = state.get("user_profile", {})
        numbers = re.findall(r'\d+', message)

        for num in numbers:
            val = int(num)
            if 18 <= val <= 100 and "age" not in user_profile:
                user_profile["age"] = val
            if 10000 <= val <= 200000 and "current_salary" not in user_profile:
                user_profile["current_salary"] = val

        if "pension" in message.lower():
            age_match = re.findall(r'(\d+)\s*(?:års? ålder|år)', message.lower())
            if age_match:
                age_val = int(age_match[0])
                user_profile.setdefault("retirement_goals", []).append(f"Retire at age {age_val}")

        state["user_profile"] = user_profile

    def _track_usage(self, response, state):
        """Track token usage if desired."""
        usage = response.usage
        return {
            "agent_type": "conversational",
            "action": "generate_response",
            "conversation_id": state["conversation_id"],
            "token_usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost": self._calculate_cost(usage)
            }
        }

    def _calculate_cost(self, usage):
        """Simple GPT-4 cost calculation example."""
        return (usage.prompt_tokens / 1000) * 0.03 + (usage.completion_tokens / 1000) * 0.06



#-----------------------------------------


class FeedbackAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.1
        )

    def process_feedback(self, state: GraphState) -> GraphState:
        try:
            feedback =  state.get("question", "")
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
