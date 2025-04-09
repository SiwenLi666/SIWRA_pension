# src/graph/pension_graph.py

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from src.agents.tool_using_agent import ToolUsingPensionAgent

logger = logging.getLogger(__name__)

def create_pension_graph() -> StateGraph:
    """
    Create a simplified pension advisor graph using the ToolUsingPensionAgent.
    
    This graph has only two nodes:
    1. tool_router - Uses the ToolUsingPensionAgent to select and run the appropriate tool
    2. finalize_output - Ensures the response is properly formatted
    
    Returns:
        StateGraph: The compiled graph with minimal nodes.
    """
    builder = StateGraph(dict)
    
    # Create the tool-using agent
    agent = ToolUsingPensionAgent()
    
    def tool_router(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route the question to the appropriate tool using the ToolUsingPensionAgent.
        
        Args:
            state: The current state with at least a 'question' key.
            
        Returns:
            Dict[str, Any]: The updated state with a 'response' key.
        """
        logger.info(f"Processing question: {state.get('question', '')}")
        return agent.process(state)
    
    def finalize_output(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Finalize the output by ensuring a response is present.
        
        Args:
            state: The current state.
            
        Returns:
            Dict[str, Any]: The finalized state.
        """
        if not state.get("response"):
            state["response"] = "Tyvärr kunde jag inte svara på din fråga."
            
        # Add any additional formatting or post-processing here
        state["status"] = "✅ Klar"
        return state
    
    # Add the minimal set of nodes
    builder.add_node("tool_router", tool_router)
    builder.add_node("finalize_output", finalize_output)
    
    # Add simple edges
    builder.add_edge("tool_router", "finalize_output")
    builder.add_edge("finalize_output", END)
    
    # Set the entry point
    builder.set_entry_point("tool_router")
    
    return builder.compile()
