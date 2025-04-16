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
            else:
                state["response"] = "Jag har ingen tidigare beräkning att förklara just nu."
                return state

        # 🔁 Om inte följdfråga – loopa igenom verktygen
        for tool in self.tools:
            if tool.can_handle(question, state):
                return tool.run(question, state)

        # ❌ Om inget verktyg kan hantera
        state["response"] = "Jag är ledsen, men jag kunde inte förstå din fråga."
        return state

