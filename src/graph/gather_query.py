# src/graph/gather_query.py
import logging
from src.graph.state import GraphState, AgentState

logger = logging.getLogger(__name__)

def gather_query(state: GraphState) -> GraphState:
    print(f"👀 Type of state inside gather_query: {type(state)}")
    print(f"🔍 Keys in state inside gather_query: {list(state.keys())}")
    print(f"📎 state raw: {state}")

    
    question = state.get("question", "")
    logger.info(f"[gather_query] User asked: {question!r}")

    if not question.strip():
        logger.warning("[gather_query] ⚠️ Inget meddelande mottaget från användaren – kontrollera att frågan är korrekt satt i GraphState.")

    state["state"] = AgentState.RETRIEVING_CONTEXT.value
    return state


