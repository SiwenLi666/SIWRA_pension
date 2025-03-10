"""
Module for creating a visual representation of the pension advisor agent's workflow.
"""
import os
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum
import logging
import uuid

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import Graph, StateGraph
from langchain_core.agents import AgentAction, AgentFinish
from langchain_openai import ChatOpenAI

from .agent import PensionAdvisor
from .document_processor import DocumentProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentState(Enum):
    """States that our agent can be in"""
    STARTING = "starting"
    DETECTING_LANGUAGE = "detecting_language"
    RETRIEVING_CONTEXT = "retrieving_context"
    GENERATING_RESPONSE = "generating_response"
    FINISHED = "finished"
    ERROR = "error"

class GraphState(dict):
    """State object for our graph"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setdefault("conversation_id", str(uuid.uuid4()))
        self.setdefault("token_usage", [])
        self.setdefault("state", AgentState.STARTING.value)
        self.setdefault("language", "sv")
        self.setdefault("context", [])
        self.setdefault("response", "")
        self.setdefault("error", "")

class PensionAdvisorGraph:
    def __init__(self):
        """Initialize the pension advisor graph."""
        self.advisor = PensionAdvisor()
        
    def detect_language(self, state: GraphState) -> GraphState:
        """Detect the language of the input."""
        try:
            question = state["question"]
            lang = self.advisor.detect_language(question)
            return GraphState(
                **state,
                language=lang,
                state=AgentState.DETECTING_LANGUAGE.value
            )
        except Exception as e:
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )

    def retrieve_context(self, state: GraphState) -> GraphState:
        """Retrieve relevant context using RAG."""
        try:
            question = state["question"]
            context = self.advisor.retriever.get_relevant_documents(question)
            
            # Track token usage for RAG retrieval
            state["token_usage"].append({
                "agent_type": "retriever",
                "action": "retrieve_context",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": 0,  # No LLM tokens for retrieval
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0
                }
            })
            
            return GraphState(
                **state,
                context=[doc.page_content for doc in context],
                state=AgentState.RETRIEVING_CONTEXT.value
            )
        except Exception as e:
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )

    def generate_response(self, state: GraphState) -> GraphState:
        """Generate the final response."""
        try:
            lang = state.get("language", "sv")
            rag_chain = self.advisor.rag_chains[lang]
            response = rag_chain.invoke(state["question"])
            
            # Estimate token usage for RAG response generation
            # This is an approximation since we don't have direct access to token counts
            prompt_tokens = sum(len(ctx.split()) * 1.3 for ctx in state["context"]) + len(state["question"].split()) * 1.3
            completion_tokens = len(response.split()) * 1.3
            
            # Track token usage
            state["token_usage"].append({
                "agent_type": "rag_chain",
                "action": "generate_response",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(prompt_tokens + completion_tokens),
                    "cost": self._calculate_cost(int(prompt_tokens), int(completion_tokens))
                }
            })
            
            return GraphState(
                **state,
                response=response,
                state=AgentState.FINISHED.value
            )
        except Exception as e:
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )
    
    def _calculate_cost(self, prompt_tokens, completion_tokens) -> float:
        """Calculate cost based on GPT-4 pricing"""
        prompt_cost = (prompt_tokens / 1000) * 0.03  # $0.03 per 1K tokens
        completion_cost = (completion_tokens / 1000) * 0.06  # $0.06 per 1K tokens
        return prompt_cost + completion_cost

    def should_continue(self, state: GraphState) -> bool:
        """Determine if we should continue processing."""
        return state.get("state") != AgentState.ERROR.value

    def create_graph(self) -> Graph:
        """Create the workflow graph."""
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("detect_language", self.detect_language)
        workflow.add_node("retrieve_context", self.retrieve_context)
        workflow.add_node("generate_response", self.generate_response)

        # Add edges
        workflow.add_conditional_edges(
            "detect_language",
            self.should_continue,
            {
                True: "retrieve_context",
                False: "end"
            }
        )
        
        workflow.add_conditional_edges(
            "retrieve_context",
            self.should_continue,
            {
                True: "generate_response",
                False: "end"
            }
        )
        
        workflow.add_edge("generate_response", "end")
        
        # Set entry point
        workflow.set_entry_point("detect_language")

        # Compile the graph
        graph = workflow.compile()
        return graph

    def run_with_visualization(self, question: str) -> Tuple[str, List[Dict]]:
        """
        Run the agent and return both the response and graph data for visualization.
        
        Args:
            question: The question to process
            
        Returns:
            Tuple of (response, graph_data)
            where graph_data is a list of state transitions for visualization
        """
        graph = self.create_graph()
        
        # Initialize state
        state = GraphState(question=question)
        
        # Run the graph
        final_state = graph.invoke(state)
        
        # Extract response and graph data
        response = final_state.get("response", "Error: No response generated")
        
        # Also extract token usage for cost tracking
        token_usage = final_state.get("token_usage", [])
        total_cost = sum(usage["token_usage"]["cost"] for usage in token_usage)
        
        graph_data = [
            {
                "state": final_state.get("state", AgentState.ERROR.value),
                "language": final_state.get("language", "unknown"),
                "context_length": len(final_state.get("context", [])),
                "has_error": "error" in final_state and final_state["error"],
                "total_cost": total_cost
            }
        ]
        
        return response, graph_data

def main():
    """Example usage of the graph visualization."""
    advisor_graph = PensionAdvisorGraph()
    
    # Example questions in both languages
    questions = [
        "Vad är AKAP-KR?",
        "What is AKAP-KR?",
        "Hur beräknas pensionen enligt AKAP-KR?",
        "What happens to my pension if I change employers?"
    ]
    
    for question in questions:
        print(f"\nProcessing question: {question}")
        response, graph_data = advisor_graph.run_with_visualization(question)
        print("\nResponse:", response)
        print("\nGraph data:")
        print(graph_data)
        print("-" * 80)

if __name__ == "__main__":
    main()
