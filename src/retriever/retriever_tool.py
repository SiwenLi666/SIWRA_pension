from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
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


class BM25Retriever:
    def __init__(self, chunk_data_path):
        with open(chunk_data_path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.documents = [entry["content"] for entry in self.data]
        self.tokenized_docs = [doc.lower().split() for doc in self.documents]
        self.bm25 = BM25Okapi(self.tokenized_docs)

    def retrieve(self, query, top_k=5):
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        ranked = sorted(zip(self.data, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
