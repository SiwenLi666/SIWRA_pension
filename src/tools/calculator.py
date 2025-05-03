import json
import os
import re
import logging
from typing import Dict, Any, List
from src.tools.base_tool import BaseTool 
logger = logging.getLogger("calculator_logger")
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

    def clear_log(self):
        """Clears the calculator log file before each new calculation."""
        with open(log_file, "w", encoding="utf-8") as f:
            f.truncate(0)

    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        CONTRACT: Every return path MUST set state['response'] to a user-facing string.
        """
        #logger.info("[CALC] Start run. State: %s", state)
        user_profile = state.get("user_profile", {})
        extracted = self._extract_parameters(question)
        #logger.info("[CALC] After extraction. Extracted: %s, State: %s", extracted, state)
        merged = {**user_profile, **extracted}
        if "scenario" in extracted:
            merged["scenario"] = extracted["scenario"]
        #logger.info("[CALC] After merging. Merged: %s, State: %s", merged, state)

        # Set defaults for non-critical params
        if "agreement" not in merged or not merged["agreement"]:
            merged["agreement"] = "PA16"
        if "scenario" not in merged or not merged["scenario"]:
            merged["scenario"] = "Avd1"
        if "retirement_age" not in merged or not merged["retirement_age"]:
            merged["retirement_age"] = 65
        if "growth" not in merged or not merged["growth"]:
            merged["growth"] = 0.019
        #logger.info("[CALC] After setting defaults. Params: %s", merged)

        state["user_profile"] = merged

        # Clear log before every calculation for clarity (MVP requirement)
        self.clear_log()
        logger.info("🧹 Loggen har rensats för en ny beräkning.")

        # Jämförelse-funktion: om två avtal extraherats och "jämför" nämns
        if "compare_agreements" in extracted and len(extracted["compare_agreements"]) == 2:
            agreements = extracted["compare_agreements"]
            scenarios = extracted.get("compare_scenarios", ["Avd1", "Avd1"])
            logger.info("[CALC] Before compare_agreements. Agreements: %s, Scenarios: %s, Params: %s", agreements, scenarios, merged)
            # Kontrollera att nödvändiga parametrar finns
            missing = self._check_required(merged)
            logger.info("[CALC] Compare missing check. Missing: %s", missing)
            if missing:
                state["response"] = f"Jag behöver följande information för att jämföra: {', '.join(missing)}."
                logger.info("[CALC] Compare missing. Returning: %s, State: %s", state["response"], state)
                return state
            state["response"] = self.compare_agreements(
                agreements[0], scenarios[0], agreements[1], scenarios[1], merged
            )
            logger.info("[CALC] After compare_agreements. State: %s", state)
            return state

        #logger.info("[CALC] Before missing check. Params: %s", merged)
        missing = self._check_required(merged)
        #logger.info("[CALC] Missing check. Missing: %s", missing)
        if missing:
            state["response"] = f"Jag behöver följande information för att beräkna: {', '.join(missing)}."
            logger.info("[CALC] Missing. Returning: %s, State: %s", state["response"], state)
            return state

        agreement = state.get("detected_agreement") or "PA16"
        scenario = merged.get("scenario", "Avd1")  # default to Avd1 for PA16

        try:
            #logger.info("[CALC] Before calculation. Agreement: %s, Scenario: %s, Params: %s", agreement, scenario, merged)
            if agreement == "PA16" and scenario == "Avd2":
                result = self._calculate_avd2(agreement, scenario, merged)
            else:
                result = self._calculate(agreement, scenario, merged)
            #logger.info("[CALC] After calculation. Result: %s", result)

            state["response"] = self._format_response(result, agreement, scenario, merged)
            #logger.info("[CALC] Returning response: %s, State: %s", state["response"], state)

            # 🧠 Spara beräkningsinfo för uppföljning ("hur räknade du?")
            state["last_calculation"] = {
                "input": merged,
                "result": result,
                "agreement": agreement,
                "scenario": scenario
            }
            #logger.info("[CALC] Saved last_calculation. State: %s", state)

        except Exception as e:
            state["response"] = f"Fel vid beräkning: {str(e)}"
            logger.error("[CALC] Exception: %s, State: %s", str(e), state)

        return state

    def format_log_for_user(self) -> str:
        """Reads the calculator log and formats it for user-friendly display."""
        if not os.path.exists(log_file):
            return "Ingen beräkningslogg hittades."
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return "Loggen är tom."
        # Filter and format log lines for user display
        user_lines = []
        for line in lines:
            if "Beräkning startad" in line or "Avd2-beräkning startad" in line:
                user_lines.append("🧮 " + line.split("|", 2)[-1].strip())
            elif "Inkomsttak" in line:
                user_lines.append("🔢 " + line.split("|", 2)[-1].strip())
            elif "Avsättning" in line:
                user_lines.append("💰 " + line.split("|", 2)[-1].strip())
            elif "Årlig avsättning" in line:
                user_lines.append("📅 " + line.split("|", 2)[-1].strip())
            elif "År " in line and "insättning + tillväxt" in line:
                user_lines.append("📈 " + line.split("|", 2)[-1].strip())
            elif "Totalt kapital med tillväxt" in line:
                user_lines.append("📦 " + line.split("|", 2)[-1].strip())
            elif "Tjänsteår" in line and "nivå" in line:
                user_lines.append("📏 " + line.split("|", 2)[-1].strip())
        return "\n".join(user_lines) if user_lines else "Ingen användbar beräkningslogg hittades."



    def _extract_parameters(self, question: str) -> Dict[str, Any]:
        data = {}
        question_lower = question.lower()

        # Ålder (t.ex. "45 år", "45-åring", "45-års")
        age = re.search(r"(\d{2})\s*[-–]?\s*[aå]r(?:ing|s)?", question_lower)
        if age:
            data["age"] = int(age.group(1))

        # Lön (t.ex. "35 000 kr", "35000 kronor", "35 000 kr/mån")
        salary = re.search(r"(\d+[ \d]*)\s*(kr|kronor|sek)(?:/m[aå]n(ad)?)?", question_lower)
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

        # Löneväxling (salary exchange, e.g. "löneväxla 1000 kr", "löneväxling 2000 kr")
        lvx = re.search(r"löneväx(?:ling)?\s*(\d+[ \d]*)\s*(kr|kronor|sek)?", question_lower)
        if lvx:
            data["salary_exchange"] = int(lvx.group(1).replace(" ", ""))
        # Löneväxlingspremie (e.g. "premie 5%", "löneväxlingspremie 6 %")
        premie = re.search(r"premie\s*(\d+(?:[\.,]\d+)?)\s*%", question_lower)
        if premie:
            data["salary_exchange_premium"] = float(premie.group(1).replace(",", ".")) / 100

        # Extrahera två avtal och scenarier om "jämför" nämns
        agreements = re.findall(r"pa16|skr2023|itp1|itp2|kap-kl", question_lower)
        if "jämför" in question_lower and len(agreements) >= 2:
            data["compare_agreements"] = agreements[:2]
            # Försök hitta tillhörande scenarier (Avd1/Avd2/Standard)
            scenarios = re.findall(r"avd[\s\.]?(1|2)|standard", question_lower)
            if len(scenarios) >= 2:
                data["compare_scenarios"] = [
                    f"Avd{scenarios[0]}" if scenarios[0] in ["1", "2"] else "Standard",
                    f"Avd{scenarios[1]}" if scenarios[1] in ["1", "2"] else "Standard"
                ]
            else:
                # Defaulta till Avd1/Standard om ej specificerat
                data["compare_scenarios"] = ["Avd1" if agreements[0] == "pa16" else "Standard",
                                            "Avd1" if agreements[1] == "pa16" else "Standard"]
        return data

    def compare_agreements(self, agreement1: str, scenario1: str, agreement2: str, scenario2: str, user_input: Dict[str, Any]) -> str:
        """
        Jämför två pensionsavtal och returnera en svensk tabell/översikt.
        """
        try:
            if agreement1 == "pa16" and scenario1.lower() == "avd2":
                result1 = self._calculate_avd2(agreement1.upper(), scenario1, user_input)
            else:
                result1 = self._calculate(agreement1.upper(), scenario1, user_input)
            if agreement2 == "pa16" and scenario2.lower() == "avd2":
                result2 = self._calculate_avd2(agreement2.upper(), scenario2, user_input)
            else:
                result2 = self._calculate(agreement2.upper(), scenario2, user_input)
        except Exception as e:
            return f"Fel vid jämförelse: {str(e)}"

        rows = [
            ["Avtal (scenario)", f"{agreement1.upper()} ({scenario1})", f"{agreement2.upper()} ({scenario2})"],
            ["Månatlig pension (kr)", f"{result1['monthly_pension']}", f"{result2['monthly_pension']}",],
            ["Totalt pensionskapital (kr)", f"{result1['total_pension']}", f"{result2['total_pension']}",],
            ["Avsättning/mån (kr)", f"{result1['monthly_contribution']}", f"{result2['monthly_contribution']}",],
            ["År till pension", f"{result1['years_to_pension']}", f"{result2['years_to_pension']}",],
        ]
        # Bygg Markdown-tabell på svenska
        md = "| " + " | ".join(rows[0]) + " |\n"
        md += "|---|---|---|\n"
        for row in rows[1:]:
            md += "| " + " | ".join(row) + " |\n"
        return (
            "**Jämförelse mellan två pensionsavtal:**\n\n" +
            md +
            "\nAlla beräkningar är ungefärliga och bygger på dina angivna uppgifter."
        )



    def _check_required(self, params: Dict[str, Any]) -> List[str]:
        required = ["age", "monthly_salary"]
        missing = [field for field in required if field not in params or params[field] in [None, ""]]
        return missing

    def _calculate(self, agreement: str, scenario: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        param = self.parameters[agreement]["scenarios"][scenario]

        age = user_input["age"]
        salary = user_input["monthly_salary"]
        pension_age = user_input.get("retirement_age", param.get("default_retirement_age", 65))
        years_to_pension = pension_age - age
        growth = param.get("default_return_rate", 0.019)

        salary_exchange = user_input.get("salary_exchange", 0)
        salary_exchange_premium = user_input.get("salary_exchange_premium", 0)

        logger.info(f"🧮 Beräkning startad: ålder={age}, lön={salary}, pensionsålder={pension_age}, år till pension={years_to_pension}, tillväxt={growth}, löneväxling={salary_exchange}, löneväxlingspremie={salary_exchange_premium}")

        # ✅ Step 1: Correct annual income and cap logic (NO *12 on cap!)
        annual_salary = salary * 12
        annual_cap = param["income_cap_base_amount"] * param["income_base_amount"]

        below = min(annual_salary, annual_cap)
        above = max(0, annual_salary - annual_cap)

        # ✅ Step 2: Fetch rates
        rate_below = param.get("contribution_rate_below_cap", 0)
        rate_above = param.get("contribution_rate_above_cap", 0)

        contrib_below = below * rate_below
        contrib_above = above * rate_above
        annual_contribution = contrib_below + contrib_above

        # ✅ Löneväxling
        salary_exchange_contribution = salary_exchange * salary_exchange_premium
        annual_contribution += salary_exchange_contribution * 12
        monthly_contribution = annual_contribution / 12

        # ✅ Log breakdown
        logger.info(f"🔢 Inkomsttak (årsvis) = {annual_cap}, under tak = {below}, över tak = {above}")
        logger.info(f"💰 Avsättning: {rate_below*100:.1f}% av {below} = {contrib_below:.2f}, {rate_above*100:.1f}% av {above} = {contrib_above:.2f}")
        logger.info(f"💰 Löneväxlingspremie: {salary_exchange} * {salary_exchange_premium*100:.1f}% = {salary_exchange_contribution}")
        logger.info(f"📅 Årlig avsättning = {annual_contribution:.2f}, månatlig = {monthly_contribution:.2f}")

        # ✅ Step 3: Growth accumulation
        total_with_growth = 0
        for i in range(1, years_to_pension + 1):
            compounded = annual_contribution * (1 + growth) ** (years_to_pension - i)
            total_with_growth += compounded
            logger.info(f"📈 År {i}: insättning + tillväxt = {compounded:.2f}")

        monthly_pension = total_with_growth / (20 * 12)  # 20-year payout

        logger.info(f"📦 Totalt kapital med tillväxt = {total_with_growth:.2f}, månatlig pension = {monthly_pension:.2f}")

        # ✅ Return full breakdown
        return {
            "monthly_pension": int(monthly_pension),
            "total_pension": int(total_with_growth),
            "monthly_contribution": int(monthly_contribution),
            "years_to_pension": years_to_pension,
            "breakdown": {
                "below_cap_amount": int(below),
                "above_cap_amount": int(above),
                "contrib_below": int(contrib_below),
                "contrib_above": int(contrib_above),
                "rate_below": rate_below,
                "rate_above": rate_above
            }
        }


    def _calculate_avd2(self, agreement: str, scenario: str, user_input: Dict[str, Any]) -> Dict[str, Any]:
        param = self.parameters[agreement]["scenarios"][scenario]

        age = user_input["age"]
        salary = user_input["monthly_salary"]
        pension_age = user_input.get("retirement_age", param.get("default_retirement_age", 65))
        years_to_pension = pension_age - age
        growth = param.get("default_return_rate", 0.019)  # Standard enligt MinPension.se april 2025: 1.9% real värdeutveckling

        logger.info(f"Avd2-beräkning startad: ålder={age}, lön={salary}, pensionsålder={pension_age}, tjänsteår={years_to_pension}")

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

        logger.info(f"Tjänsteår = {years_to_pension}, nivå = {percent*100:.1f}%, pension = {monthly_pension:.2f}/mån")

        return {
            "monthly_pension": int(monthly_pension),
            "total_pension": int(monthly_pension * 12 * 20),  # schablon: 20 års uttag
            "monthly_contribution": 0,
            "years_to_pension": years_to_pension
        }

    def _format_response(self, result, agreement, scenario, inputs):
        # Special handling for PA16 Avd2
        if agreement == "PA16" and scenario == "Avd2":
            return (
                f"Baserat på dina uppgifter uppskattas din pension enligt {agreement} ({scenario}) till ca {result['monthly_pension']} kr/mån från {inputs.get('retirement_age', 65)} års ålder. "
                f"Det motsvarar ett totalt kapital på ca {result['total_pension']} kr, baserat på en avsättning på {result['monthly_contribution']} kr/mån under {result['years_to_pension']} år."
            )
        elif agreement == "PA16" and scenario == "Avd1":
            return (
                f"Baserat på dina uppgifter uppskattas din pension enligt {agreement} ({scenario}) till ca {result['monthly_pension']} kr/mån från {inputs.get('retirement_age', 65)} års ålder. "
                f"Det motsvarar ett totalt kapital på ca {result['total_pension']} kr, baserat på en avsättning på {result['monthly_contribution']} kr/mån under {result['years_to_pension']} år."
            )
        # Default for all other cases
        return (
            f"Baserat på dina uppgifter med antagande att månatlig avsättning: {result.get('monthly_contribution', 0)} kr/mån under {result.get('years_to_pension', 0)} år"
            f"Uppskattas din pension enligt {agreement} till: "
            f"Totalt kapital: ca {result['total_pension']} kr. "
            f"Vilket är ca {result['monthly_pension']} kr/mån från {inputs.get('retirement_age', 65)} års ålder. "
        )
