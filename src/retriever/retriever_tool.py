from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from src.utils.config import VECTORSTORE_DIR
import os
import logging

# Constants
VECTOR_DIR = VECTORSTORE_DIR

# Logging setup
logger = logging.getLogger(__name__)

class RetrieverTool:
    def __init__(self):
        self.vectorstore = None
        self.embeddings = OpenAIEmbeddings()

    def load_vectorstore(self):
        """Load the existing vectorstore or raise error"""
        if not os.path.exists(VECTOR_DIR):
            raise FileNotFoundError("Vectorstore directory does not exist")

        try:
            self.vectorstore = FAISS.load_local(
                VECTOR_DIR,
                self.embeddings,
                allow_dangerous_deserialization=True  # ✅ opt-in for safe pickle use
            )
            logger.info("✅ Vectorstore loaded successfully")
            return self.vectorstore
        except Exception as e:
            logger.error(f"❌ Failed to load vectorstore: {str(e)}")
            raise

    def retrieve_relevant_docs(self, query: str, top_k: int = 5):
        """Query vectorstore for top-k relevant documents"""
        if self.vectorstore is None:
            self.load_vectorstore()

        try:
            docs = self.vectorstore.similarity_search(query, k=top_k)
            return docs
        except Exception as e:
            logger.error(f"❌ Retrieval error: {str(e)}")
            return []
