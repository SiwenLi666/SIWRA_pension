from langchain_openai import ChatOpenAI
from .retriever_tool import RetrieverTool  # Uses RetrieverTool for document search
import logging
from langchain_core.messages import SystemMessage, HumanMessage


# ✅ Initialize logger
logger = logging.getLogger(__name__)

class DocumentAnalystAgent:
    """Analyzes pension agreements using vector search and LLM."""

    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.2, model="gpt-4")
        self.retriever = RetrieverTool()  # Uses RetrieverTool to query documents

    def analyze_agreement_info(self, agreement: str) -> dict:
        """Analyze an agreement with retrieved documents as context and return structured results."""
        documents = self.query_relevant_documents(agreement)

        # ✅ Debug: Log retrieved document metadata
        for doc in documents:
            logger.info(f"Retrieved doc metadata: Source={doc['source']}, Page={doc['page']}, Language={doc['language']}")
        
        if not documents or documents[0]["text"] == "No relevant document found.":
            logger.warning(f"No relevant documents available for {agreement}. Skipping analysis.")
            return {
                "agreement": agreement,
                "full_name": "No relevant document found.",
                "user_group": "No relevant document found.",
                "sources": []
            }

        document_sources = [
            {"source": doc["source"], "page": doc["page"], "text": doc["text"][:200] + "..."}
            for doc in documents
        ]

        system_prompt = f"""Du är en expert på svenska pensionsavtal. Använd följande dokument som referens:
        
        {document_sources}

        - **Svara endast baserat på de hämtade dokumenten.**
        - **Om dokumenten inte innehåller svaret, ge en kvalificerad gissning baserat på din expertis.**
        - **Citerar alltid dokumentets källa och sidnummer i ditt svar om det används.**
        """

        questions = [
            f"Vad är det fullständiga namnet på avtalet {agreement}?",
            f"Vilken målgrupp gäller avtalet {agreement} för?"
        ]

        responses = {}
        for question in questions:
            response = self.llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=question)])
            logger.info(f"LLM response for '{question}': {response.content}")  # ✅ Log the response
            responses[question] = response.content

        return {
            "agreement": agreement,
            "full_name": responses.get(f"Vad är det fullständiga namnet på avtalet {agreement}?", "Unknown Agreement"),
            "user_group": responses.get(f"Vilken målgrupp gäller avtalet {agreement} för?", "Unknown Group"),
            "sources": document_sources
        }






    def query_relevant_documents(self, agreement: str, top_k=3):
        """Retrieve documents related to the agreement name with metadata."""
        results = self.retriever.query(agreement, top_k=top_k)

        if not results:
            logger.warning(f"No relevant documents found for agreement: {agreement}")
            return [{"text": "No relevant document found.", "source": "N/A", "page": "N/A", "language": "Unknown"}]

        formatted_results = []
        for result in results:
            if isinstance(result, str):
                logger.warning(f"FAISS returned a raw string instead of a document object: {result[:100]}...")
                formatted_results.append({
                    "text": result,
                    "source": "Unknown PDF",
                    "page": "Unknown Page",
                    "language": "Unknown"
                })
            else:
                formatted_results.append({
                    "text": result.page_content,
                    "source": result.metadata.get("source", "Unknown PDF"),
                    "page": result.metadata.get("page_number", "Unknown Page"),
                    "language": result.metadata.get("language", "Unknown")
                })

        return formatted_results





