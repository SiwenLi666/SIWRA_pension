# src/graph/pension_graph.py

from langgraph.graph import StateGraph, END
from src.graph.state import GraphState
from src.graph.gather_query import gather_query
from src.agents.answer_agent import AnswerAgent
from src.agents.refiner_agent import RefinerAgent
from src.agents.verifier_agent import VerifierAgent
from src.agents.missing_fields_agent import MissingFieldsAgent

def create_pension_graph():
    builder = StateGraph(GraphState)

    # Agents (you can define them in separate files)
    answer_agent = AnswerAgent()
    refiner_agent = RefinerAgent()
    verifier_agent = VerifierAgent()
    missing_fields_agent = MissingFieldsAgent()

    builder.set_entry_point("gather_query")

    # 1) gather_query
    builder.add_node("gather_query", gather_query)
    # 2) generate_answer
    builder.add_node("generate_answer", answer_agent.generate)
    # 3) verify_answer
    builder.add_node("verify_answer", verifier_agent.verify)
    # 4) refine_answer
    builder.add_node("refine_answer", refiner_agent.refine)
    # 5) ask_for_missing_fields
    builder.add_node("ask_for_missing_fields", missing_fields_agent.ask)

    # Now define transitions
    builder.add_edge("gather_query", "generate_answer")
    builder.add_edge("generate_answer", "verify_answer")

    # verify_answer decides: "good" → ask_for_missing_fields, "bad" → refine_answer
    builder.add_conditional_edges("verify_answer", verifier_agent.route_verification, {
        "good": "ask_for_missing_fields",
        "bad": "refine_answer"
    })

    # refine_answer goes back to verify_answer or, if it fails multiple times, goes to ask_for_missing_fields
    builder.add_conditional_edges("refine_answer", refiner_agent.route_refinement, {
        "retry": "verify_answer",
        "give_up": "ask_for_missing_fields"
    })

    # ask_for_missing_fields final step
    builder.add_edge("ask_for_missing_fields", END)

    return builder.compile()
