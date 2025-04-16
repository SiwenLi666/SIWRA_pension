import json
import os
import re
from typing import Dict, Any, List
from src.tools.base_tool import BaseTool 
import logging


log_dir = os.path.join(os.path.dirname(__file__), "../../logs")
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "calculator.log")

logger = logging.getLogger("calculator_logger")
logger.setLevel(logging.DEBUG)

# Undvik duplicerade handlers
if not logger.handlers:
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


PARAMETER_PATH = os.path.join(os.path.dirname(__file__), "../calculation/calculation_parameters.json")

class CalculatorTool(BaseTool):
    """
    Tool for performing pension calculations based on structured parameters.
    """

    def __init__(self):
        super().__init__(
            name="calculator",
            description="Performs pension calculations using structured agreement parameters"
        )
        self.parameters = self._load_parameters()

    def _load_parameters(self) -> Dict[str, Any]:
        with open(PARAMETER_PATH, encoding="utf-8") as f:
            return json.load(f)

    def can_handle(self, question: str, state: Dict[str, Any]) -> bool:
        question_lower = question.lower()
        patterns = [
            r"hur\s+mycket",
            r"vad\s+f[\u00e5|a]r\s+jag",
            r"ber[a\u00e4]kna",
            r"r[a\u00e4]kna\s+ut",
            r"min\s+m[\u00e5|a]nadsl[\u00f6|o]n",
            r"jag\s+tj[\u00e4|a]nar"
        ]
        return any(re.search(p, question_lower) for p in patterns)

    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        user_profile = state.get("user_profile", {})
        extracted = self._extract_parameters(question)
        merged = {**user_profile, **extracted}
        if "scenario" in extracted:
            merged["scenario"] = extracted["scenario"]


        state["user_profile"] = merged

        missing = self._check_required(merged)
        if missing:
            state["response"] = f"Jag behöver följande information för att beräkna: {', '.join(missing)}."
            return state

        agreement = state.get("detected_agreement") or "PA16"
        scenario = merged.get("scenario", "Avd1")  # default to Avd1 for PA16

        try:
            if agreement == "PA16" and scenario == "Avd2":
                result = self._calculate_avd2(agreement, scenario, merged)
            else:
                result = self._calculate(agreement, scenario, merged)

            state["response"] = self._format_response(result, agreement, scenario, merged)

            # 🧠 Spara beräkningsinfo för uppföljning ("hur räknade du?")
            state["last_calculation"] = {
                "input": merged,
                "result": result,
                "agreement": agreement,
                "scenario": scenario
            }

        except Exception as e:
            state["response"] = f"Fel vid beräkning: {str(e)}"

        return state


    def _extract_parameters(self, question: str) -> Dict[str, Any]:
        data = {}
        question_lower = question.lower()

        # Ålder (t.ex. "45 år")
        age = re.search(r"(\d{2})\s*[aå]r", question_lower)
        if age:
            data["age"] = int(age.group(1))

        # Lön (t.ex. "35 000 kr", "35000 kronor")
        salary = re.search(r"(\d+[\s\d]*)\s*(kr|kronor|sek)", question_lower)
        if salary:
            data["monthly_salary"] = int(salary.group(1).replace(" ", ""))

        # Uttagsålder (t.ex. "vid 65 års pension")
        pension_age = re.search(r"vid\s+(\d{2})\s*[aå]rs?\s+pension", question_lower)
        if pension_age:
            data["retirement_age"] = int(pension_age.group(1))

        # Scenario: Avd1 eller Avd2
        scenario_match = re.search(r"avd(?:elning)?[\s\.]?(1|2)", question_lower)
        if scenario_match:
            data["scenario"] = f"Avd{scenario_match.group(1)}"

        return data



    def _check_required(self, data: Dict[str, Any]) -> List[str]:
        required = ["age", "monthly_salary"]
        return [f for f in required if f not in data]

    def _calculate(self, agreement: str, scenario: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        param = self.parameters[agreement]["scenarios"][scenario]

        age = user_input["age"]
        salary = user_input["monthly_salary"]
        pension_age = user_input.get("retirement_age", param.get("default_retirement_age", 65))
        years_to_pension = pension_age - age
        growth = param.get("default_return_rate", 0.03)

        logger.info(f"🧮 Beräkning startad: age={age}, salary={salary}, pension_age={pension_age}, years_to_pension={years_to_pension}, growth={growth}")

        # Step 1: determine cap
        cap = param["income_cap_base_amount"] * param["income_base_amount"]
        below = min(salary, cap)
        above = max(0, salary - cap)
        logger.info(f"🔢 Inkomsttak = {cap}, under tak = {below}, över tak = {above}")

        # Step 2: calculate contributions
        rate_below = param.get("contribution_rate_below_cap", 0)
        rate_above = param.get("contribution_rate_above_cap", 0)

        contrib_below = below * rate_below
        contrib_above = above * rate_above
        annual_contribution = (contrib_below + contrib_above) * 12
        monthly_contribution = annual_contribution / 12

        logger.info(f"💰 Avsättning: {rate_below*100:.1f}% av {below} = {contrib_below}, {rate_above*100:.1f}% av {above} = {contrib_above}")
        logger.info(f"📅 Årlig avsättning = {annual_contribution}, månatlig = {monthly_contribution:.2f}")

        # Step 3: estimate future value (compounding year by year)
        total_with_growth = 0
        for i in range(1, years_to_pension + 1):
            compounded = annual_contribution * (1 + growth)**(years_to_pension - i)
            total_with_growth += compounded
            logger.debug(f"📈 År {i}: insättning + tillväxt = {compounded:.2f}")

        monthly_pension = total_with_growth / (20 * 12)  # spread over 20 years

        logger.info(f"📦 Totalt kapital med tillväxt = {total_with_growth:.2f}, månatlig pension = {monthly_pension:.2f}")

        return {
            "monthly_pension": int(monthly_pension),
            "total_pension": int(total_with_growth),
            "monthly_contribution": int(monthly_contribution),
            "years_to_pension": years_to_pension
        }

    def _calculate_avd2(self, agreement: str, scenario: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        param = self.parameters[agreement]["scenarios"][scenario]

        age = user_input["age"]
        salary = user_input["monthly_salary"]
        pension_age = user_input.get("retirement_age", param.get("default_retirement_age", 65))
        years_to_pension = pension_age - age
        growth = param.get("default_return_rate", 0.03)

        logger.info(f"🧮 Avd2-beräkning startad: age={age}, salary={salary}, pension_age={pension_age}, tjänsteår={years_to_pension}")

        # Hämta nivåer: t.ex. {"<=30": 0.10, ">30": 0.65}
        levels = param.get("defined_benefit_levels", [])

        percent = 0
        for level in levels:
            if level["years"].startswith("<=") and years_to_pension <= int(level["years"][2:]):
                percent = level["percent"]
                break
            elif level["years"].startswith(">") and years_to_pension > int(level["years"][1:]):
                percent = level["percent"]
                break

        annual_salary = salary * 12
        annual_pension = annual_salary * percent
        monthly_pension = annual_pension / 12


        logger.info(f"📏 Tjänsteår = {years_to_pension}, nivå = {percent*100:.1f}%, pension = {monthly_pension:.2f}/mån")

        return {
            "monthly_pension": int(monthly_pension),
            "total_pension": int(monthly_pension * 12 * 20),  # schablon: 20 års uttag
            "monthly_contribution": 0,
            "years_to_pension": years_to_pension
        }

    def _format_response(self, result, agreement, scenario, inputs):
        if agreement == "PA16" and scenario == "Avd2":
            return (
                f"Baserat på dina uppgifter uppskattas din pension enligt {agreement} ({scenario}) till ca {result['monthly_pension']} kr/mån från {inputs.get('retirement_age', 65)} års ålder. "
                f"Detta baseras på en förmånsnivå av slutlönen efter {result['years_to_pension']} års tjänstetid."
            )
        else:
            return (
                f"Baserat på dina uppgifter uppskattas din pension enligt {agreement} ({scenario}) till ca {result['monthly_pension']} kr/mån från {inputs.get('retirement_age', 65)} års ålder. "
                f"Det motsvarar ett totalt kapital på ca {result['total_pension']} kr, baserat på en avsättning på {result['monthly_contribution']} kr/mån under {result['years_to_pension']} år."
            )
