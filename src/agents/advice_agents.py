from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
import logging
from src.graph.state import GraphState, AgentState
from src.retriever.document_processor import DocumentProcessor
import json



logger = logging.getLogger('advice_agents')

class PensionAnalystAgent:
    def __init__(self, doc_processor: DocumentProcessor):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.3)
        self.doc_processor = doc_processor

    def analyze_needs(self, state: GraphState) -> GraphState:
        question = state.get("question", "")
        user_profile = state.get("user_profile", {})
        selected_agreement = state.get("selected_agreement")

        logger.info("📊 Analyzing user's pension needs...")

        # Try querying vector DB
        try:
            docs = self.doc_processor.query_documents(question, selected_agreement, top_k=3)
        except Exception as e:
            logger.warning(f"Document query failed: {str(e)}")
            docs = []

        if not docs:
            logger.warning("No documents found, falling back to summary.")
            from retriever.summary_handler import get_summary_chunks
            docs = get_summary_chunks(selected_agreement)

        context = "\n---\n".join([doc.page_content for doc in docs])
        prompt = f"""
        Du är en expert på svenska pensionsavtal. Analysera användarens situation och behov baserat på:

        FRÅGA:
        {question}

        PROFIL:
        {user_profile}

        DOKUMENTINNEHÅLL:
        {context}

        Sammanfatta användarens behov på ett konkret sätt. Om något är oklart, peka ut det.
        """

        messages = [SystemMessage(content=prompt)]

        response = self.llm.invoke(messages)

        logger.info("✅ Analysis completed")

        state["analysis"] = response.content
        state["response"] = response.content
        state["state"] = AgentState.ANALYZING_NEEDS.value
        return state

    def generate_advice(self, state: GraphState) -> GraphState:
        user_profile = state.get("user_profile", {})
        analysis = state.get("analysis", "")
        calculations = state.get("calculations", "")

        prompt = f"""
        Du är pensionsrådgivare. Sammanfatta lämplig rådgivning baserat på:

        PROFIL:
        {user_profile}

        ANALYS:
        {analysis}

        BERÄKNINGAR:
        {calculations}

        Ge tydlig, handlingsbar rådgivning med värme och professionalism.
        """

        messages = [SystemMessage(content=prompt)]
        response = self.llm.invoke(messages)

        logger.info("💡 Advice generated")

        state["recommendations"] = response.content
        state["response"] = response.content
        state["state"] = AgentState.GENERATING_ADVICE.value
        return state


#-----------------------------------



class RecommendationAgent:
    """Agent for generating personalized pension recommendations"""
    def __init__(self):
        self.llm = ChatOpenAI(model_name="gpt-4", temperature=0.2)

    def generate_recommendations(self, state: GraphState) -> GraphState:
        try:
            user_profile = state.get("user_profile", {})
            analysis = state.get("analysis", "")
            calculations = state.get("calculations", "")

            if not user_profile or not analysis:
                return GraphState(
                    **state,
                    response="Jag behöver mer information för att kunna ge personliga rekommendationer.",
                    state=AgentState.GATHERING_INFO.value
                )

            system_prompt = (
                """Du är en expert på pensionsrådgivning i Sverige.
                Baserat på användarens profil, analys och beräkningar, ge personliga rekommendationer.
                Var konkret och ge praktiska råd som användaren kan följa.
                Förklara varför dina rekommendationer är lämpliga för just denna person.
                Avsluta med att fråga om användaren har några frågor om rekommendationerna."""
            )

            context = f"""
            ANVÄNDARPROFIL:
            {json.dumps(user_profile, indent=2, ensure_ascii=False)}

            ANALYS:
            {analysis}

            BERÄKNINGAR:
            {calculations}
            """

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Ge personliga pensionsrekommendationer baserat på följande information:\n{context}")
            ]

            response = self.llm.invoke(messages)
            usage = response.usage
            state["token_usage"].append({
                "agent_type": "recommendation",
                "action": "generate_recommendations",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })

            return GraphState(
                **state,
                recommendations=response.content,
                response=response.content,
                state=AgentState.GENERATING_RECOMMENDATIONS.value
            )

        except Exception as e:
            logger.error(f"Error in recommendation agent: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                state=AgentState.ERROR.value
            )

    def _calculate_cost(self, usage) -> float:
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03
        completion_cost = (usage.completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost

#----------------------------------------


class CalculationAgent:
    """Agent for performing pension calculations"""
    def __init__(self):
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0
        )

    def calculate_pension(self, state: GraphState) -> GraphState:
        try:
            user_profile = state.get("user_profile", {})
            if not user_profile:
                return GraphState(
                    **state,
                    response="Jag har inte tillräckligt med information för att göra beräkningar. Kan du berätta mer om din situation?",
                    state=AgentState.GATHERING_INFO.value
                )

            system_prompt = (
                """Du är en expert på pensionsberäkningar i Sverige.
                Baserat på den information du har, gör en uppskattning av personens pension.
                Förklara dina beräkningar på ett pedagogiskt sätt.
                Om du saknar viktig information för att göra en bra beräkning, nämn det."""
            )

            profile_summary = [f"{key}: {value}" for key, value in user_profile.items()]

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Beräkna pension baserat på följande information:\n{', '.join(profile_summary)}")
            ]

            response = self.llm.invoke(messages)
            usage = response.usage

            state["token_usage"].append({
                "agent_type": "calculation",
                "action": "calculate_pension",
                "conversation_id": state["conversation_id"],
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "cost": self._calculate_cost(usage)
                }
            })

            return GraphState(
                **state,
                calculations=response.content,
                response=response.content,
                state=AgentState.CALCULATING.value
            )

        except Exception as e:
            logger.error(f"Error in calculation agent: {str(e)}")
            return GraphState(
                **state,
                error=str(e),
                response="Tyvärr kunde jag inte räkna just nu.",
                state=AgentState.ERROR.value
            )

    def _calculate_cost(self, usage) -> float:
        prompt_cost = (usage.prompt_tokens / 1000) * 0.03
        completion_cost = (usage.completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost
