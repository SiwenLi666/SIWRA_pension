# src/graph/gather_query.py
import logging
from src.graph.state import GraphState, AgentState

logger = logging.getLogger(__name__)

def gather_query(state: GraphState) -> GraphState:
    """
    This function doesn't do much except confirm we have state["question"] from the user.
    If the user typed something, we proceed to generate_answer next.
    """
    logger.debug(f"[gather_query] State keys: {list(state.keys())}")

    question = state.get("question", "")
    logger.info(f"[gather_query] User asked: {question!r}")

    # Just return the same state, possibly setting the state=some_value
    return GraphState(
        **state,
        state=AgentState.RETRIEVING_CONTEXT.value  # example
    )
