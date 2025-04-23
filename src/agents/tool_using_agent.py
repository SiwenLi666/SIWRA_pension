from typing import Dict, Any
from src.tools.calculator import CalculatorTool
from src.tools.vector_retriever import VectorRetrieverTool
from src.tools.summary_checker import SummaryCheckerTool
from src.tools.base_tool import BaseTool



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

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        question = state.get("question", "").lower().strip()

        # 🧠 Särskilt fallback-svar för följdfråga: "hur räknade du?"
        followups = ["hur räknade du", "hur kom du fram till det", "visa beräkning"]
        if any(p in question for p in followups):
            last = state.get("last_calculation")
            if last:
                i = last["input"]
                r = last["result"]
                state["response"] = (
                    f"Jag räknade ut pensionen baserat på en lön på {i['monthly_salary']} kr/mån, "
                    f"från {i['age']} års ålder till {i.get('retirement_age', 65)}. "
                    f"Det innebär {r['monthly_contribution']} kr/mån i avsättning under {r['years_to_pension']} år, "
                    f"som växte med 3% årligen till ett kapital på {r['total_pension']} kr. "
                    f"Det fördelas över 20 år → {r['monthly_pension']} kr/mån."
                )
                return state

            # 🔁 Fallback: använd kalkylloggen om ingen beräkning sparad
            approx = get_last_calculation_from_log()
            if approx:
                state["response"] = (
                    f"Jag har ingen aktiv beräkning sparad, "
                    f"men senast loggade beräkning gällde en lön på {approx['monthly_salary']} kr/mån "
                    f"och en ålder på {approx['age']} år, med pensionsålder {approx['retirement_age']}."
                )
                return state

            # ❌ Ingenting hittades
            state["response"] = "Jag har ingen tidigare beräkning att förklara just nu."
            return state

        # 🔁 Loopa igenom verktygen om inte följdfråga
        for tool in self.tools:
            if tool.can_handle(question, state):
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
        print(f"Kunde inte läsa kalkylloggen: {e}")
    return None
