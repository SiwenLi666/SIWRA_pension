# inspect_vectorstore.py
import logging
from src.retriever_tool import RetrieverTool

# ✅ Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_faiss():
    """Retrieve and log metadata from the FAISS vectorstore."""
    retriever = RetrieverTool()

    if not retriever.vectorstore:
        logger.warning("No vectorstore found.")
        return

    logger.info("🔍 Inspecting FAISS vectorstore...")

    # ✅ Retrieve first 10 stored documents
    stored_docs = retriever.vectorstore.similarity_search(" ", k=10)

    if not stored_docs:
        logger.warning("No documents found in FAISS!")
        return

    for i, doc in enumerate(stored_docs):
        logger.info(f"🔹 Document {i+1}: Source={doc.metadata.get('source', 'Unknown')}, "
                    f"Page={doc.metadata.get('page_number', 'Unknown')}, "
                    f"Language={doc.metadata.get('language', 'Unknown')}, "
                    f"Text Preview={doc.page_content[:200]}...")

if __name__ == "__main__":
    inspect_faiss()
