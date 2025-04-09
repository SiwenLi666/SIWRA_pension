# src/graph/pension_graph.py

from langgraph.graph import StateGraph, END
from src.graph.state import GraphState
from src.agents.answering_agents import AnswerAgent, RefinerAgent, MissingFieldsAgent
from src.calculation.calculation_agent import CalculationAgent
import json
import logging
from src.utils.config import SUMMARY_JSON_PATH

logger = logging.getLogger(__name__)


def create_pension_graph():
    builder = StateGraph(dict)  # ✅ matches input you're passing in

    # Agents (you can define them in separate files)
    answer_agent = AnswerAgent()
    refiner_agent = RefinerAgent()
    missing_fields_agent = MissingFieldsAgent()
    calculation_agent = CalculationAgent()

    # Set the entry point to check summary.json first
    builder.set_entry_point("check_summary_json")

    # Add all nodes
    builder.add_node("check_summary_json", check_summary_json)
    builder.add_node("check_calculation_intent", check_calculation_intent)
    builder.add_node("extract_parameters", extract_parameters)
    builder.add_node("ask_calculation_parameters", ask_calculation_parameters)
    builder.add_node("handle_calculation", handle_calculation_query)
    builder.add_node("generate_answer", answer_agent.generate)
    builder.add_node("refine_answer", refiner_agent.refine)
    builder.add_node("ask_for_missing_fields", missing_fields_agent.ask)

    # 1. First, route from summary.json check
    def route_from_summary_check(state):
        if state.get("summary_json_answer", False):
            # We found an answer in summary.json
            return "end"
        else:
            # No answer in summary.json, check if calculation is needed
            return "check_calculation"
            
    builder.add_conditional_edges("check_summary_json", route_from_summary_check, {
        "end": END,
        "check_calculation": "check_calculation_intent",
    })
    
    # 2. Route from calculation intent check
    def route_from_calculation_check(state):
        if state.get("is_calculation", False):
            # This is a calculation query, extract parameters
            return "extract_parameters"
        else:
            # Not a calculation query, proceed to vector search
            return "generate"
            
    builder.add_conditional_edges("check_calculation_intent", route_from_calculation_check, {
        "extract_parameters": "extract_parameters",
        "generate": "generate_answer",
    })
    
    # 3. Route from parameter extraction
    def route_from_parameter_extraction(state):
        if state.get("requires_more_info", False):
            # Missing parameters, ask for them
            return "ask_params"
        else:
            # Have all parameters, perform calculation
            return "calculate"
            
    builder.add_conditional_edges("extract_parameters", route_from_parameter_extraction, {
        "ask_params": "ask_calculation_parameters",
        "calculate": "handle_calculation",
    })
    
    # 4. Route from asking calculation parameters
    def route_from_ask_params(state):
        if state.get("user_abandoned", False):
            # User abandoned parameter collection, go to vector search
            return "generate"
        elif state.get("all_params_collected", False):
            # All parameters collected, perform calculation
            return "calculate"
        else:
            # For MVP, we'll end the conversation after asking once to prevent infinite loops
            # In a production system, we would track the number of attempts and limit them
            state["response"] = state.get("response", "") + "\n\nVänligen svara med all information på en gång."
            return "end"
            
    builder.add_conditional_edges("ask_calculation_parameters", route_from_ask_params, {
        "generate": "generate_answer",
        "calculate": "handle_calculation",
        "end": END,
    })
    
    # 5. Route from generate_answer based on answer quality
    def route_from_generate(state):
        # Check if answer needs refinement
        if state.get("needs_refinement", False) or state.get("draft_answer", "").strip().lower() == "nej":
            return "refine"
        else:
            return "final"

    builder.add_conditional_edges("generate_answer", route_from_generate, {
        "refine": "refine_answer",
        "final": "ask_for_missing_fields",
    })

    # 6. Connect remaining edges
    builder.add_edge("refine_answer", "ask_for_missing_fields")
    builder.add_edge("handle_calculation", END)
    builder.add_edge("ask_for_missing_fields", END)

    return builder.compile()

# Check if we can answer from summary.json
def check_summary_json(state):
    question = state.get("question", "")
    state["status"] = "🔎 Kontrollerar om jag kan svara direkt..."
    
    try:
        # Try to load summary.json
        with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
            summary_data = json.load(f)
            
        # Use the AnswerAgent's approach to check if we can answer from summary.json
        answer_agent = AnswerAgent()
        result_state = answer_agent.generate({"question": question})
        
        # If we got a valid answer (not "nej")
        if result_state.get("draft_answer") and result_state.get("draft_answer").strip().lower() != "nej":
            state["response"] = result_state["draft_answer"]
            state["response_source"] = "summary_json"
            state["summary_json_answer"] = True
            state["status"] = "✅ Svarar från sammanfattning"
            logger.info("Found answer in summary.json")
            return state
        
        # No valid answer in summary.json
        state["summary_json_answer"] = False
        logger.info("No answer found in summary.json, proceeding to calculation check")
        return state
        
    except Exception as e:
        # Error loading or processing summary.json
        logger.error(f"Error checking summary.json: {e}")
        state["summary_json_answer"] = False
        return state

# Check if this is a calculation query
def check_calculation_intent(state):
    question = state.get("question", "")
    state["status"] = "🧮 Kontrollerar om detta är en beräkningsfråga..."
    
    # Initialize calculation agent
    calc_agent = CalculationAgent()
    
    # Detect if this is a calculation query
    is_calculation, calculation_type, confidence = calc_agent.detect_calculation_intent(question)
    state["is_calculation"] = is_calculation
    
    if is_calculation:
        state["calculation_type"] = calculation_type
        state["calculation_confidence"] = confidence
        state["status"] = "🧮 Identifierade beräkningsfråga"
        logger.info(f"Detected calculation query of type {calculation_type} with confidence {confidence}")
    else:
        state["status"] = "🔎 Söker efter information..."
        logger.info("Not a calculation query, proceeding to vector search")
    
    return state

# Extract calculation parameters
def extract_parameters(state):
    question = state.get("question", "")
    user_profile = state.get("user_profile", {})
    
    # Get the selected agreement from state or user profile
    agreement = state.get("selected_agreement", user_profile.get("selected_agreement", ""))
    
    state["status"] = "🧮 Extraherar parametrar för beräkning..."
    
    # Initialize calculation agent
    calc_agent = CalculationAgent()
    
    # Extract parameters from the question
    parameters = calc_agent.extract_parameters(question, agreement)
    
    # Update user profile with any new parameters
    for param_name, value in parameters.items():
        user_profile[param_name] = value
    
    state["user_profile"] = user_profile
        
    # Check if we have all required parameters for this calculation type
    calculation_type = state.get("calculation_type", "")
    required_params = ["monthly_salary"]
    if calculation_type == "retirement_estimate":
        required_params.extend(["age"])
    
    # Check which parameters are missing
    missing_params = [param for param in required_params if param not in user_profile or user_profile[param] is None]
    
    if missing_params:
        state["requires_more_info"] = True
        state["missing_parameters"] = missing_params
        state["status"] = f"⚠️ Saknar parametrar: {', '.join(missing_params)}"
        logger.info(f"Missing parameters: {missing_params}")
    else:
        state["requires_more_info"] = False
        state["status"] = "✅ Har alla parametrar för beräkning"
        logger.info("All required parameters available")
    
    return state

# Ask for calculation parameters function
def ask_calculation_parameters(state):
    missing_params = state.get("missing_parameters", [])
    user_profile = state.get("user_profile", {})
    calculation_type = state.get("calculation_type", "")
    
    if not missing_params:
        # No missing parameters, proceed to calculation
        state["requires_more_info"] = False
        state["all_params_collected"] = True
        return state
    
    # Translate parameter names to user-friendly Swedish
    param_translations = {
        "age": "din ålder",
        "monthly_salary": "din månadslön",
        "years_of_service": "hur många år du har arbetat",
        "employment_type": "din anställningstyp",
        "return_rate": "förväntad avkastning"
    }
    
    # Create a user-friendly message asking for the missing parameters
    readable_params = [param_translations.get(param, param) for param in missing_params]
    
    # Format the response based on the calculation type
    calc_type_translations = {
        "retirement_estimate": "pensionsberäkning",
        "contribution_calculation": "beräkning av pensionsavsättningar",
        "early_retirement": "beräkning av förtidspension",
        "comparison": "jämförelse av pensionsalternativ"
    }
    
    calc_type_readable = calc_type_translations.get(calculation_type, "pensionsberäkning")
    
    # Create the response
    response = f"För att kunna göra en korrekt {calc_type_readable} behöver jag veta {', '.join(readable_params)}. "
    
    # Add what we already know
    if user_profile:
        known_params = []
        if "age" in user_profile:
            known_params.append(f"din ålder är {user_profile['age']} år")
        if "monthly_salary" in user_profile:
            known_params.append(f"din månadslön är {user_profile['monthly_salary']} kr")
        if "years_of_service" in user_profile:
            known_params.append(f"du har arbetat i {user_profile['years_of_service']} år")
        
        if known_params:
            response += f"\n\nJag vet redan att {', '.join(known_params)}."
    
    # Add a note about what information is still needed
    response += f"\n\nKan du vänligen berätta {', '.join(readable_params)}?"
    
    state["response"] = response
    state["state"] = "GATHERING_INFO"
    
    return state

# Handle calculation query function
def handle_calculation_query(state):
    """Handle a calculation query."""
    question = state.get("question", "")
    user_profile = state.get("user_profile", {})
    calculation_type = state.get("calculation_type", "")
    
    # Get the selected agreement from state or user profile
    agreement = state.get("selected_agreement", user_profile.get("selected_agreement", ""))
    
    # Initialize calculation agent
    calc_agent = CalculationAgent()
    
    # Perform the calculation
    state["status"] = "🧮 Utför beräkning..."
    logger.info(f"Performing calculation of type {calculation_type} for agreement {agreement}")
    
    # Extract parameters from user profile
    parameters = {}
    for param in ["monthly_salary", "age", "years_of_service", "years_until_retirement", "return_rate"]:
        if param in user_profile and user_profile[param] is not None:
            parameters[param] = user_profile[param]
    
    # Call the calculation agent
    result = calc_agent.handle_calculation_query(question, agreement, parameters)
    
    # Update state with calculation result
    if result.get("is_calculation", False):
        if result.get("requires_more_info", False):
            # Need more information to complete calculation
            state["requires_more_info"] = True
            state["missing_parameters"] = result.get("missing_parameters", [])
            state["response"] = result.get("message", "Jag behöver mer information för att kunna göra beräkningen.")
            state["status"] = "⚠️ Behöver mer information"
            logger.info(f"Need more information for calculation: {state['missing_parameters']}")
        else:
            # Calculation completed successfully
            state["requires_more_info"] = False
            
            # Format the response based on calculation type
            if calculation_type == "retirement_estimate" and "estimated_pension" in result:
                estimated_pension = result["estimated_pension"]
                state["response"] = (
                    f"Baserat på din information har jag beräknat din uppskattade pension:\n\n"
                    f"📊 **Uppskattad månatlig pension:** {estimated_pension:,.2f} kr\n\n"
                    f"Denna beräkning är baserad på {agreement if agreement else 'generella pensionsregler'} "
                    f"och din angivna månadslön på {user_profile.get('monthly_salary', 0):,.2f} kr."
                )
            elif calculation_type == "contribution_calculation" and "monthly_contribution" in result:
                monthly_contribution = result["monthly_contribution"]
                annual_contribution = monthly_contribution * 12
                state["response"] = (
                    f"Baserat på din information har jag beräknat dina pensionsavsättningar:\n\n"
                    f"📊 **Månatlig avsättning:** {monthly_contribution:,.2f} kr\n"
                    f"📊 **Årlig avsättning:** {annual_contribution:,.2f} kr\n\n"
                    f"Denna beräkning är baserad på {agreement if agreement else 'generella pensionsregler'}."
                )
            else:
                state["response"] = result.get("message", "Här är resultatet av beräkningen.")
                
            state["status"] = "✅ Beräkning klar"
            logger.info("Calculation completed successfully")
    else:
        # Not a calculation query (should not happen at this point)
        state["is_calculation"] = False
        state["response"] = "Jag kunde inte utföra beräkningen. Låt mig istället söka efter information om din fråga."
        state["status"] = "❌ Kunde inte utföra beräkning"
        logger.error("Failed to perform calculation")
    
    state["state"] = "FINISHED"
    return state
