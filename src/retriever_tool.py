from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RetrieverTool:
    def __init__(self, persist_dir="vectorstore"):
        self.persist_dir = Path(persist_dir)
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

        try:
            self.vectorstore = FAISS.load_local(str(self.persist_dir), self.embeddings, allow_dangerous_deserialization=True)
            logger.info("Vectorstore loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load vectorstore: {str(e)}")
            self.vectorstore = None

    def query(self, question: str, top_k=3):
        if not self.vectorstore:
            logger.warning("Vectorstore is not loaded, returning empty results.")
            return []

        results = self.vectorstore.similarity_search(question, k=top_k)

        # ✅ Ensure metadata is extracted correctly
        formatted_results = []
        for result in results:
            formatted_results.append({
                "text": result.page_content,
                "source": result.metadata.get("source", "Unknown"),
                "page": result.metadata.get("page_number", "Unknown"),
                "language": result.metadata.get("language", "Unknown"),
            })

        return formatted_results


    def inspect_vectorstore(self):
        """Retrieve and log metadata from the FAISS vectorstore."""
        if not self.vectorstore:
            logger.warning("No vectorstore found.")
            return

        logger.info("🔍 Inspecting FAISS vectorstore...")

        # ✅ Retrieve all stored documents
        stored_docs = self.vectorstore.similarity_search(" ", k=10)  # Fetch first 10 docs

        if not stored_docs:
            logger.warning("No documents found in FAISS!")
            return

        for i, doc in enumerate(stored_docs):
            logger.info(f"🔹 Document {i+1}: Source={doc.metadata.get('source', 'Unknown')}, "
                        f"Page={doc.metadata.get('page_number', 'Unknown')}, "
                        f"Language={doc.metadata.get('language', 'Unknown')}, "
                        f"Text Preview={doc.page_content[:200]}...")
