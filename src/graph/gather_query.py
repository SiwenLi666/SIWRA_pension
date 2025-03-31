# src/graph/gather_query.py
import logging
from src.graph.state import GraphState, AgentState

logger = logging.getLogger(__name__)

def gather_query(state: GraphState) -> GraphState:
    
    question = state.get("question", "")
    logger.info(f"[gather_query] User asked: {question!r}")

    if not question.strip():
        logger.warning("[gather_query] ⚠️ Inget meddelande mottaget från användaren – kontrollera att frågan är korrekt satt i GraphState.")

    return GraphState(
        **state,
        state=AgentState.RETRIEVING_CONTEXT.value
    )

