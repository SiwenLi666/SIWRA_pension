import logging
import os
from datetime import datetime
from src.tools.calculator import CalculatorTool

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Use a log file with today's date
log_filename = f"logs/agent_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("agent_logger")

from typing import Dict, Any
from src.tools.vector_retriever import VectorRetrieverTool
from src.tools.summary_checker import SummaryCheckerTool
from src.tools.base_tool import BaseTool
from src.llm_utils import ask_llm_gpt41nano



class ToolUsingPensionAgent:
    """
    A simple agent that routes pension-related questions to the appropriate tool.
    """

    def __init__(self):
        self.tools = [
            CalculatorTool(),
            SummaryCheckerTool(),
            VectorRetrieverTool()
        ]
        # Cache tool metadata for LLM prompts
        self.tool_metadata = {}
        for tool in self.tools:
            name = tool.__class__.__name__
            if hasattr(tool, "_check_required") and hasattr(tool, "_extract_parameters"):
                # Only CalculatorTool has these; you can expand for more tools in the future
                self.tool_metadata[name] = {
                    "required_fields": ["age", "monthly_salary", "agreement", "scenario", "retirement_age", "growth"],
                    "field_types": {"age": "int", "monthly_salary": "int", "agreement": "str", "scenario": "str", "retirement_age": "int", "growth": "float"},
                    "description": tool.description
                }
            else:
                self.tool_metadata[name] = {
                    "required_fields": [],
                    "field_types": {},
                    "description": getattr(tool, "description", "")
                }

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main agent logic. CONTRACT: Every return path MUST set state['response'] to a user-facing string.
        """
        logger.info("[AGENT] Start process. State: %s", state)
        question = state.get("question", "").lower().strip()
        logger.info(f"[AGENT] Received question: '{question}'")

        # --- Step 1: Handle and track follow-up count ---
        # If no active tool (new main question), reset followup_count
        if not state.get("active_tool"):
            state["followup_count"] = 0
        # If in a follow-up thread, increment count after each follow-up answer
        elif state.get("last_llm_question") and state.get("expected_fields") and not state.get("_followup_incremented"):
            state["followup_count"] = state.get("followup_count", 0) + 1
            state["_followup_incremented"] = True

        # --- Step 2: If max follow-ups reached, summarize and reset ---
        MAX_FOLLOWUPS = 2
        if state.get("followup_count", 0) >= MAX_FOLLOWUPS:
            user_profile = state.get("user_profile", {})
            missing = state.get("expected_fields", [])
            summary_prompt = (
                f"Sammanfatta följande användaruppgifter:\n{user_profile}\n"
                f"Följande parametrar saknas: {', '.join(missing) if missing else 'Inga'}\n"
                f"Skriv en tydlig svensk sammanfattning och be användaren börja om eller komplettera."
            )
            llm_summary = ask_llm_gpt41nano(summary_prompt)
            state["response"] = llm_summary
            for k in ["active_tool", "followup_count", "last_llm_question", "expected_fields", "_followup_incremented"]:
                state.pop(k, None)
            logger.info(f"[AGENT] Final state to return (followup max): {state}")
            return state

        # Särskilt fallback-svar för följdfråga: "hur räknade du?"
        followups = ["hur räknade du", "hur kom du fram till det", "visa beräkning"]
        if any(p in question for p in followups):
            last = state.get("last_calculation")
            if last:
                i = last["input"]
                r = last["result"]
                state["response"] = (
                    f"Jag räknade ut pensionen baserat på {agreement} ({scenario}) och en lön på {i['monthly_salary']} kr/mån, "
                    f"från {i['age']} års ålder till {i.get('retirement_age', 65)}. "
                    f"Det innebär {r['monthly_contribution']} kr/mån i avsättning under {r['years_to_pension']} år, "
                    f"som växte med 1,9% årligen (enligt MinPension.se april 2025) till ett kapital på {r['total_pension']} kr. "
                    f"Det fördelas över 20 år → {r['monthly_pension']} kr/mån."
                )
                logger.info(f"[AGENT] Final state to return (calculation fallback): {state}")
                return state

            # Fallback: använd kalkylloggen om ingen beräkning sparad
            # Use CalculatorTool.format_log_for_user for a user-friendly, step-by-step log
            calc_tool = next((t for t in self.tools if hasattr(t, "format_log_for_user")), None)
            if calc_tool:
                log_summary = calc_tool.format_log_for_user()
                state["response"] = f"Här är stegen från senaste beräkningen:\n\n{log_summary}"
                logger.info(f"[AGENT] Final state to return (calculation log fallback): {state}")
                return state
            # If for some reason no calculator tool is found, fallback to previous minimal summary
            approx = get_last_calculation_from_log()
            if approx:
                state["response"] = (
                    f"Jag har ingen aktiv beräkning sparad, "
                    f"men senast loggade beräkning gällde en lön på {approx['monthly_salary']} kr/mån "
                    f"och en ålder på {approx['age']} år, med pensionsålder {approx['retirement_age']}."
                )
                logger.info(f"[AGENT] Final state to return (calculation log fallback 2): {state}")
                return state

        # --- Step 4: Tool selection and activation (MVP logic) ---
        if not state.get("active_tool"):
            for tool in self.tools:
                logger.info(f"[AGENT] Trying tool: {tool.__class__.__name__}")
                try:
                    can_handle = tool.can_handle(question, state)
                    logger.info(f"[AGENT] Tool {tool.__class__.__name__}.can_handle returned: {can_handle}")
                except Exception as e:
                    logger.error(f"[AGENT] Exception in can_handle for {tool.__class__.__name__}: {e}")
                    continue
                if can_handle:
                    state["active_tool"] = tool.__class__.__name__
                    logger.info(f"[AGENT] Selected tool: {tool.__class__.__name__}")
                    # If tool supports parameter extraction/validation
                    if hasattr(tool, "_extract_parameters") and hasattr(tool, "_check_required"):
                        # Only use parameter extraction for CalculatorTool
                        if isinstance(tool, CalculatorTool):
                            try:
                                extracted = tool._extract_parameters(question)
                                logger.info("[AGENT] After parameter extraction. Extracted: %s, State: %s", extracted, state)
                                merged = {**state.get("user_profile", {}), **extracted}
                                logger.info("[AGENT] After merging/defaulting. Merged: %s, State: %s", merged, state)
                                if "agreement" not in merged:
                                    merged["agreement"] = "PA16"
                                if "scenario" not in merged:
                                    merged["scenario"] = "Avd1" if merged["agreement"].upper() == "PA16" else "Standard"
                                
                                calc = self.tools[0] if isinstance(self.tools[0], CalculatorTool) else CalculatorTool()
                                agreement = merged["agreement"].upper()
                                scenario = merged["scenario"]
                                agreement_data = calc.parameters.get(agreement, {}).get("scenarios", {}).get(scenario, {})
                                merged.setdefault("retirement_age", agreement_data.get("default_retirement_age", 65))
                                merged.setdefault("growth", agreement_data.get("default_return_rate", 0.03))
                                missing = tool._check_required(merged)
                                if missing:
                                    logger.info(f"[AGENT] Missing parameters after extraction: {missing}")
                                    # Use LLM with tool metadata for missing fields
                                    antaganden = (
                                        f"Avtal: {merged['agreement']} {merged['scenario']}\n"
                                        f"Uttagsålder: {merged['retirement_age']} år\n"
                                        f"Avkastning: {merged['growth']}\n"
                                    )
                                    llm_prompt = (
                                        f"För att räkna ut din pension använder jag följande standardvärden:\n"
                                        f"{antaganden}"
                                        f"Men jag behöver veta: {', '.join(missing)}.\n"
                                        f"Skriv gärna om du vill ändra något av ovanstående!\n"
                                        f"Användarens fråga: '{question}'\n"
                                        f"Nuvarande state: {merged}\n"
                                        f"Gissa aldrig. Om något är oklart eller saknas, returnera ENDAST en tydlig svensk följdfråga.\n"
                                        f"Om allt är tydligt, returnera ett JSON-objekt med alla parametrar."
                                    )
                                    # Spara senaste fråga och vilka fält som förväntas
                                    state["last_llm_question"] = f"Men jag behöver veta: {', '.join(missing)}."
                                    state["expected_fields"] = missing
                                    llm_response = ask_llm_gpt41nano(llm_prompt)
                                    # Enkel heuristik: om svaret börjar med '{', tolka som JSON-parametrar, annars följdfråga
                                    if llm_response.strip().startswith('{'):
                                        try:
                                            import json
                                            params = json.loads(llm_response)
                                            merged.update(params)
                                            # Kör kalkylatorn igen med ifyllda parametrar
                                            state["user_profile"] = merged
                                            state.pop("last_llm_question", None)
                                            state.pop("expected_fields", None)
                                            missing2 = tool._check_required(merged)
                                            if not missing2:
                                                logger.info("[AGENT] Before calling tool: %s. State: %s", tool.__class__.__name__, state)
                                                result = tool.run(question, state)
                                                logger.info("[AGENT] After tool run. State: %s", result)
                                                logger.info(f"[AGENT] Final state to return (calc tool run after LLM): {result}")
                                                return result
                                            else:
                                                logger.info(f"[AGENT] Still missing after LLM: {missing2}")
                                                state["response"] = f"Jag behöver fortfarande: {', '.join(missing2)}."
                                                logger.info(f"[AGENT] Final state to return (missing after LLM): {state}")
                                                return state
                                        except Exception as ex:
                                            logger.error(f"[AGENT] Error decoding JSON from LLM: {ex}")
                                            state["response"] = llm_response
                                            logger.info(f"[AGENT] Final state to return (LLM JSON error): {state}")
                                            return state
                                    else:
                                        # Direkt följdfråga från LLM
                                        state["response"] = llm_response
                                        logger.error(f"[AGENT] Fallback triggered. State: %s", state)
                                        if not state.get("response"):
                                            logger.error(f"[AGENT] Fallback triggered. State: %s", state)
                                            state["response"] = "Tyvärr kunde jag inte svara på din fråga (internt fel)."
                                        logger.info(f"[AGENT] Returning response: %s. State: %s", state.get('response'), state)
                                        # Add any additional formatting or post-processing here
                                        state["status"] = "✅ Klar"
                                        return state
                                # Om inga parametrar saknas, kör som vanligt
                                logger.info("[AGENT] Before calling tool: %s. State: %s", tool.__class__.__name__, state)
                                result = tool.run(question, state)
                                logger.info("[AGENT] After tool run. State: %s", result)
                                return result
                            except Exception as e:
                                logger.error(f"[AGENT] Exception during parameter extraction or tool run: {e}")
                                state["response"] = f"Ett fel uppstod: {e}"
                                return state
                    else:
                        # For non-calculator tools (e.g., retriever, summary), just call run directly
                        logger.info(f"[AGENT] Running tool {tool.__class__.__name__} with standard execution (no parameter extraction)")
                        logger.info(f"[AGENT] [NON-CALC] Try block START. state id: {id(state)}; state: {state}")
                        try:
                            logger.info(f"[AGENT] [NON-CALC] Before tool run. state id: {id(state)}; state: {state}")
                            result = tool.run(question, state)
                            logger.info(f"[AGENT] [NON-CALC] After tool run. result id: {id(result)}; result: {result}")
                            logger.info(f"[AGENT] [NON-CALC] Try block END. Returning result.")
                            return result
                        except Exception as e:
                            import traceback
                            logger.error(f"[AGENT] Exception during tool run: {e}\n{traceback.format_exc()}")
                            state["response"] = f"Ett fel uppstod: {e}"
                            logger.info(f"[AGENT] [NON-CALC] Try block END (exception). Returning state: {state}")
                            return state
                    logger.warning("[AGENT] FELL THROUGH TOOL LOOP! Returning fallback state: %s", state)            
                    return state
            # Om ingen tool matchade, låt LLM generera svensk följdfråga
        if not state.get("active_tool"):
            clarify_prompt = (
                f"Användarens fråga: '{question}'\n"
                f"Kunde inte identifiera rätt verktyg. Ställ en svensk följdfråga för att förtydliga användarens avsikt."
            )
            llm_clarify = ask_llm_gpt41nano(clarify_prompt)
            state["response"] = llm_clarify
            logger.info(f"Returning response: {state.get('response')}")
            return state
        else:
            # --- Om active_tool är satt, använd endast det verktyget för all vidare logik ---
            tool = next((t for t in self.tools if t.__class__.__name__ == state["active_tool"]), None)
            if tool:
                # --- Step 5: Follow-up/clarification logic (always LLM with tool metadata) ---
                if state.get("last_llm_question") and state.get("expected_fields"):
                    expected = state["expected_fields"]
                    tool_name = state.get("active_tool") or "CalculatorTool"
                    tool_meta = self.tool_metadata.get(tool_name, {})
                    # Always use LLM to clarify/reformulate
                    llm_prompt = (
                        f"Föregående fråga: '{state['last_llm_question']}'\n"
                        f"Användarens svar: '{question}'\n"
                        f"Det aktiva verktyget kräver följande parametrar: {tool_meta.get('required_fields', [])}\n"
                        f"Fält och typer: {tool_meta.get('field_types', {})}\n"
                        f"Reformulera svaret till en komplett svensk mening och returnera ett JSON-objekt med de fält som kan fyllas i.\n"
                        f"Om svaret är otydligt, be om förtydligande."
                    )
                    llm_response = ask_llm_gpt41nano(llm_prompt)
                    if llm_response.strip().startswith('{'):
                        import json
                        try:
                            params = json.loads(llm_response)
                            state["user_profile"] = state.get("user_profile", {})
                            state["user_profile"].update(params)
                            state.pop("last_llm_question", None)
                            state.pop("expected_fields", None)
                            # After filling, re-run tool selection/activation logic as if new query
                            return self.process(state)
                        except Exception:
                            state["response"] = llm_response
                            return state
                    else:
                        # If still missing, LLM asks again (up to max follow-ups)
                        state["response"] = llm_response
                        return state

                # --- Kör som vanligt, men om kritiska parametrar saknas, använd LLM för följdfråga + visa antaganden ---
                extracted = tool._extract_parameters(question)
                logger.info("[AGENT] After parameter extraction. Extracted: %s, State: %s", extracted, state)
                merged = {**state.get("user_profile", {}), **extracted}
                logger.info("[AGENT] After merging/defaulting. Merged: %s, State: %s", merged, state)
                if "agreement" not in merged:
                    merged["agreement"] = "PA16"
                if "scenario" not in merged:
                    merged["scenario"] = "Avd1" if merged["agreement"].upper() == "PA16" else "Standard"
                
                calc = self.tools[0] if isinstance(self.tools[0], CalculatorTool) else CalculatorTool()
                agreement = merged["agreement"].upper()
                scenario = merged["scenario"]
                agreement_data = calc.parameters.get(agreement, {}).get("scenarios", {}).get(scenario, {})
                merged.setdefault("retirement_age", agreement_data.get("default_retirement_age", 65))
                merged.setdefault("growth", agreement_data.get("default_return_rate", 0.03))
                missing = tool._check_required(merged)
                if missing:
                    antaganden = (
                        f"Avtal: {merged['agreement']} {merged['scenario']}\n"
                        f"Uttagsålder: {merged['retirement_age']} år\n"
                        f"Avkastning: {merged['growth']}\n"
                    )
                    llm_prompt = (
                        f"För att räkna ut din pension använder jag följande standardvärden:\n"
                        f"{antaganden}"
                        f"Men jag behöver veta: {', '.join(missing)}.\n"
                        f"Skriv gärna om du vill ändra något av ovanstående!\n"
                        f"Användarens fråga: '{question}'\n"
                        f"Nuvarande state: {merged}\n"
                        f"Gissa aldrig. Om något är oklart eller saknas, returnera ENDAST en tydlig svensk följdfråga.\n"
                        f"Om allt är tydligt, returnera ett JSON-objekt med alla parametrar."
                    )
                    state["last_llm_question"] = f"Men jag behöver veta: {', '.join(missing)}."
                    state["expected_fields"] = missing
                    llm_response = ask_llm_gpt41nano(llm_prompt)
                    if llm_response.strip().startswith('{'):
                        try:
                            import json
                            params = json.loads(llm_response)
                            merged.update(params)
                            state["user_profile"] = merged
                            state.pop("last_llm_question", None)
                            state.pop("expected_fields", None)
                            missing2 = tool._check_required(merged)
                            if not missing2:
                                result = tool.run(question, state)
                                return result
                            else:
                                state["response"] = f"Jag behöver fortfarande: {', '.join(missing2)}."
                                return state
                        except Exception:
                            state["response"] = llm_response
                            return state
                    else:
                        state["response"] = llm_response
                        return state
                return tool.run(question, state)

        state["response"] = "Jag är ledsen, men jag kunde inte förstå din fråga."
        return state

    import os

    def get_last_calculation_from_log():
        log_path = os.path.join(os.path.dirname(__file__), "../../logs/calculator.log")
        try:
            with open(log_path, encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                if "🧮 Beräkning startad" in line:
                    parts = line.split("age=")[1].split(",")
                    age = int(parts[0].strip())
                    salary = int(parts[1].split("=")[1].strip())
                    pension_age = int(parts[2].split("=")[1].strip())
                    return {
                        "age": age,
                        "monthly_salary": salary,
                        "retirement_age": pension_age
                    }
        except Exception as e:
            logger.warning(f"Kunde inte läsa kalkylloggen: {e}")
        return None



import os

def get_last_calculation_from_log():
    log_path = os.path.join(os.path.dirname(__file__), "../../logs/calculator.log")
    try:
        with open(log_path, encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            if "🧮 Avd2-beräkning startad" in line or "🧮 Beräkning startad" in line:
                # Try to extract all available parameters from the log line
                params = {}
                try:
                    # Example log: Beräkning startad: ålder=40, lön=50000, pensionsålder=65, år till pension=25, tillväxt=0.019, löneväxling=0, löneväxlingspremie=0
                    param_str = line.split(":", 1)[1]
                    for part in param_str.split(","):
                        if "ålder=" in part:
                            params["age"] = int(part.strip().split("=", 1)[1])
                        elif "lön=" in part:
                            params["monthly_salary"] = int(part.strip().split("=", 1)[1])
                        elif "pensionsålder=" in part:
                            params["retirement_age"] = int(part.strip().split("=", 1)[1])
                        elif "år till pension=" in part:
                            params["years_to_pension"] = int(part.strip().split("=", 1)[1])
                        elif "tillväxt=" in part:
                            params["growth"] = float(part.strip().split("=", 1)[1])
                        elif "löneväxling=" in part:
                            params["salary_exchange"] = int(part.strip().split("=", 1)[1])
                        elif "löneväxlingspremie=" in part:
                            params["salary_exchange_premium"] = float(part.strip().split("=", 1)[1])
                    # Try to extract agreement and scenario from previous log lines
                    # (since not always present in the 'Beräkning startad' line)
                    idx = lines.index(line)
                    for back_line in reversed(lines[:idx]):
                        if "Before calculation" in back_line:
                            # Example: [CALC] Before calculation. Agreement: PA16, Scenario: Avd1, Params: {...}
                            if "Agreement:" in back_line:
                                agr = back_line.split("Agreement:")[1].split(",")[0].strip()
                                params["agreement"] = agr
                            if "Scenario:" in back_line:
                                scn = back_line.split("Scenario:")[1].split(",")[0].strip()
                                params["scenario"] = scn
                            break
                    return params
                except Exception as e:
                    logger.warning(f"Kunde inte tolka kalkylloggen: {e}")
                    return params if params else None
    except Exception as e:
        print(f"Kunde inte läsa kalkylloggen: {e}")
    return None
