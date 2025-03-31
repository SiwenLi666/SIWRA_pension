from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
import logging
from src.graph.state import GraphState, AgentState
from src.retriever.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

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
