# src/graph/pension_graph.py

from langgraph.graph import StateGraph, END
from src.graph.state import GraphState
from src.agents.answering_agents import AnswerAgent,RefinerAgent,MissingFieldsAgent


def create_pension_graph():
    builder = StateGraph(dict)  # ✅ matches input you're passing in


    # Agents (you can define them in separate files)
    answer_agent = AnswerAgent()
    refiner_agent = RefinerAgent()
    missing_fields_agent = MissingFieldsAgent()

    builder.set_entry_point("generate_answer")

    builder.add_node("generate_answer", answer_agent.generate)
    builder.add_node("refine_answer", refiner_agent.refine)
    builder.add_node("ask_for_missing_fields", missing_fields_agent.ask)

    # Route from generate_answer based on answer quality and verification
    def route_from_generate(state):
        # Check if answer needs refinement (either it's "nej" or verification failed)
        if state.get("needs_refinement", False) or state.get("draft_answer", "").strip().lower() == "nej":
            return "refine"
        else:
            return "final"

    builder.add_conditional_edges("generate_answer", route_from_generate, {
        "refine": "refine_answer",
        "final": "ask_for_missing_fields",
    })

    # refine_answer → ask directly (ingen retry-loop)
    builder.add_edge("refine_answer", "ask_for_missing_fields")

    # Sista nod
    builder.add_edge("ask_for_missing_fields", END)


    return builder.compile()
