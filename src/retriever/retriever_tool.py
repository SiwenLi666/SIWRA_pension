from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from src.utils.config import VECTORSTORE_DIR, USE_HYBRID_RETRIEVAL, BM25_WEIGHT, LOG_RETRIEVAL_METRICS
from rank_bm25 import BM25Okapi
import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from langchain.docstore.document import Document

# Constants
VECTOR_DIR = VECTORSTORE_DIR

# Logging setup
logger = logging.getLogger(__name__)

class RetrieverTool:
    def __init__(self):
        self.vectorstore = None
        self.embeddings = OpenAIEmbeddings()
        self.bm25_retriever = None
        self.retrieval_metrics = {"vector_time": 0, "bm25_time": 0, "hybrid_time": 0, "calls": 0}

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
        """Query for top-k relevant documents using vector search or hybrid approach"""
        if self.vectorstore is None:
            self.load_vectorstore()
            
        start_time = time.time()
        
        try:
            # Use hybrid retrieval if enabled
            if USE_HYBRID_RETRIEVAL and self._initialize_bm25_if_needed():
                docs = self._hybrid_search(query, top_k)
                if LOG_RETRIEVAL_METRICS:
                    self.retrieval_metrics["hybrid_time"] += time.time() - start_time
                    self.retrieval_metrics["calls"] += 1
                    if self.retrieval_metrics["calls"] % 10 == 0:  # Log every 10 calls
                        self._log_retrieval_metrics()
            else:
                # Fallback to vector search only
                docs = self.vectorstore.similarity_search(query, k=top_k)
                if LOG_RETRIEVAL_METRICS:
                    self.retrieval_metrics["vector_time"] += time.time() - start_time
                    self.retrieval_metrics["calls"] += 1
            
            return docs
        except Exception as e:
            logger.error(f"❌ Retrieval error: {str(e)}")
            return []
            
    def _initialize_bm25_if_needed(self) -> bool:
        """Initialize BM25 retriever if not already initialized"""
        if self.bm25_retriever is not None:
            return True
            
        try:
            # Create a serialized version of documents for BM25
            chunk_data_path = os.path.join(VECTORSTORE_DIR, "chunks.json")
            
            # If chunks.json doesn't exist, create it from the vector store
            if not os.path.exists(chunk_data_path):
                if not self._create_chunks_json(chunk_data_path):
                    return False
                    
            self.bm25_retriever = BM25Retriever(chunk_data_path)
            logger.info("✅ BM25 retriever initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize BM25 retriever: {str(e)}")
            return False
            
    def _create_chunks_json(self, output_path: str) -> bool:
        """Create a JSON file with document chunks for BM25"""
        try:
            if self.vectorstore is None:
                self.load_vectorstore()
                
            # Get all documents from the vectorstore
            # This is a bit of a hack, but FAISS doesn't have a clean way to get all docs
            all_docs = self.vectorstore.similarity_search("", k=10000)  # Get as many as possible
            
            # Convert to the format needed for BM25
            chunks_data = []
            for i, doc in enumerate(all_docs):
                chunks_data.append({
                    "id": i,
                    "content": doc.page_content,
                    "metadata": doc.metadata
                })
                
            # Save to JSON
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"✅ Created chunks.json with {len(chunks_data)} documents")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create chunks.json: {str(e)}")
            return False
            
    def _hybrid_search(self, query: str, top_k: int = 5) -> List[Document]:
        """Perform hybrid search using both BM25 and vector search"""
        # Get results from both retrievers
        vector_start = time.time()
        vector_docs = self.vectorstore.similarity_search(query, k=top_k*2)  # Get more for reranking
        vector_time = time.time() - vector_start
        
        bm25_start = time.time()
        bm25_results = self.bm25_retriever.retrieve(query, top_k=top_k*2)
        bm25_time = time.time() - bm25_start
        
        if LOG_RETRIEVAL_METRICS:
            self.retrieval_metrics["vector_time"] += vector_time
            self.retrieval_metrics["bm25_time"] += bm25_time
        
        # Convert BM25 results to Documents
        bm25_docs = []
        for result, score in bm25_results:
            doc = Document(
                page_content=result["content"],
                metadata=result["metadata"]
            )
            # Store the BM25 score in metadata for reranking
            doc.metadata["bm25_score"] = score
            bm25_docs.append(doc)
        
        # Add vector scores to vector docs
        for i, doc in enumerate(vector_docs):
            # Normalize position as a score (higher is better)
            doc.metadata["vector_score"] = 1.0 - (i / (len(vector_docs) or 1))
        
        # Combine results
        combined_docs = {}
        
        # Add BM25 results with their scores
        for doc in bm25_docs:
            doc_id = self._get_doc_id(doc)
            combined_docs[doc_id] = {
                "doc": doc,
                "bm25_score": doc.metadata.get("bm25_score", 0),
                "vector_score": 0  # Default if not in vector results
            }
        
        # Add or update with vector results
        for doc in vector_docs:
            doc_id = self._get_doc_id(doc)
            if doc_id in combined_docs:
                combined_docs[doc_id]["vector_score"] = doc.metadata.get("vector_score", 0)
            else:
                combined_docs[doc_id] = {
                    "doc": doc,
                    "bm25_score": 0,  # Default if not in BM25 results
                    "vector_score": doc.metadata.get("vector_score", 0)
                }
        
        # Calculate hybrid scores
        for doc_id, data in combined_docs.items():
            # Weighted combination of scores
            data["hybrid_score"] = (BM25_WEIGHT * data["bm25_score"]) + \
                                  ((1 - BM25_WEIGHT) * data["vector_score"])
        
        # Sort by hybrid score and take top_k
        ranked_results = sorted(
            combined_docs.values(),
            key=lambda x: x["hybrid_score"],
            reverse=True
        )[:top_k]
        
        # Return just the documents
        return [item["doc"] for item in ranked_results]
    
    def _get_doc_id(self, doc: Document) -> str:
        """Generate a unique ID for a document based on content and metadata"""
        # Use source and page number if available
        if "source" in doc.metadata and "page_number" in doc.metadata:
            return f"{doc.metadata['source']}_{doc.metadata['page_number']}"
        # Fallback to first 100 chars of content
        return doc.page_content[:100]
        
    def _log_retrieval_metrics(self):
        """Log retrieval performance metrics"""
        calls = self.retrieval_metrics["calls"]
        if calls == 0:
            return
            
        avg_vector = self.retrieval_metrics["vector_time"] / calls
        avg_bm25 = self.retrieval_metrics["bm25_time"] / calls
        avg_hybrid = self.retrieval_metrics["hybrid_time"] / calls
        
        logger.info(f"📊 Retrieval metrics after {calls} calls:")
        logger.info(f"  - Avg vector search time: {avg_vector:.4f}s")
        logger.info(f"  - Avg BM25 search time: {avg_bm25:.4f}s")
        logger.info(f"  - Avg hybrid search time: {avg_hybrid:.4f}s")


class BM25Retriever:
    def __init__(self, chunk_data_path):
        with open(chunk_data_path, encoding="utf-8") as f:
            self.data = json.load(f)
        self.documents = [entry["content"] for entry in self.data]
        self.tokenized_docs = [doc.lower().split() for doc in self.documents]
        self.bm25 = BM25Okapi(self.tokenized_docs)
        logger.info(f"📚 BM25 initialized with {len(self.documents)} documents")

    def retrieve(self, query, top_k=5):
        """Retrieve documents using BM25 ranking"""
        # Handle empty queries
        if not query.strip():
            return [(self.data[i], 0.0) for i in range(min(top_k, len(self.data)))]
            
        # Tokenize query and get scores
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        
        # Create (document, score) pairs and sort by score
        doc_score_pairs = list(zip(self.data, scores))
        ranked = sorted(doc_score_pairs, key=lambda x: x[1], reverse=True)
        
        return ranked[:top_k]
