from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.graph.state import GraphState, AgentState
from src.database.presentation_db import PensionAnalysisManager
import logging

logger = logging.getLogger('core_router_agent')

class CoreRouterAgent:
    """
    Agent that detects:
    1. Which agreement the user refers to (e.g., PA16, KAP-KL)
    2. What the user's intent is (e.g., ask for retirement age, survivor benefits)
    3. Reformulates the query for vector search
    """

    def __init__(self):
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0.2)
        self.presentation_manager = PensionAnalysisManager()

    def refine_or_continue(self, state: GraphState) -> dict:
        print("🧪 [Router] refine_or_continue called")
        return {"next": "recommendation"}



    def analyze_query(self, state: GraphState) -> GraphState:
        try:
            user_question = state.get("question", "")
            all_agreements = self.presentation_manager.get_factors().agreements

            prompt = f"""
            Du är en smart AI som analyserar användarens fråga. Du har tillgång till följande pensionsavtal:
            {all_agreements}

            Uppgift:
            1. Identifiera vilket pensionsavtal som frågan handlar om.
            2. Förklara vad användaren försöker ta reda på.
            3. Reformulera frågan så den passar för dokument- eller vektorsökning.

            Använd JSON-format:
            {{
              "agreement": "...",
              "intent": "...",
              "reformulated_query": "..."
            }}

            Användarens fråga:
            {user_question}
            """

            messages = [SystemMessage(content="Analysera användarens fråga och returnera JSON."), HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)

            import json
            data = json.loads(response.content)

            # Save to state
            state["detected_agreement"] = data.get("agreement")
            state["intent"] = data.get("intent")
            state["reformulated_query"] = data.get("reformulated_query")
            state["state"] = AgentState.RETRIEVING_CONTEXT.value

            return state

        except Exception as e:
            logger.error(f"Error in CoreRouterAgent.analyze_query: {e}")
            state["error"] = str(e)
            state["state"] = AgentState.ERROR.value
            return state
