# src/graph/transitions.py

from src.graph.state import AgentState, GraphState, UserProfile
from src.reasoning.reasoning_utils import IntentClassifier
from src.reasoning.reasoning_utils import AgreementDetector
from src.reasoning.reasoning_utils import ResponseVerifier

def should_analyze_needs(state: GraphState) -> str:
    """
    Decide whether to analyze needs (if user has provided enough data),
    or continue gathering info.
    """
    question = state.get("question", "")
    user_profile = state.get("user_profile", {}) or {}

    # 1) Grab the required field names from UserProfile
    required_field_names = UserProfile.required_fields()

    # 2) Determine which required fields are missing or None
    missing_fields = [
        f for f in required_field_names 
        if f not in user_profile or user_profile[f] is None
    ]

    # 3) Classify the user's intent
    classifier = IntentClassifier()
    detected_intent = classifier.classify_intent(question)

    # 4) If user wants to calculate or typed "sluta/avsluta" and we have all fields, move on
    #    Otherwise, stay in "gather_info"
    if detected_intent == "calculate" and not missing_fields:
        return "analyze_needs"
    if "sluta" in question.lower() or "avsluta" in question.lower():
        # You might also check if missing_fields is empty here, depending on your logic
        return "analyze_needs"
    return "gather_info"


def should_generate_recommendations(state: GraphState) -> str:
    """Decide if we have what we need to make recommendations."""
    if state.get("calculations"):
        return "generate_recommendations"
    return "generate_advice"


def should_process_feedback(state: GraphState) -> str:
    """Decide if we should process feedback."""
    if state.get("state") == AgentState.AWAITING_FEEDBACK.value and state.get("question"):
        return "process_feedback"
    return "continue"


def should_refine_or_continue(state: GraphState) -> str:
    """
    Checks whether retrieved info (in 'retrieved_docs') is sufficient 
    for a good answer. If not, return 'refine'.
    """
    response = state.get("response", "")
    question = state.get("question", "")
    docs = state.get("retrieved_docs", [])
    if not ResponseVerifier.is_response_sufficient(question, docs):
        return "refine"
    return "continue"


def route_by_agreement(state: GraphState) -> str:
    detector = AgreementDetector()
    agreement = detector.detect(state.get("question", ""))

    if agreement:
        state["detected_agreement"] = agreement
        return "retrieve_documents"
    return "ask_for_agreement"
