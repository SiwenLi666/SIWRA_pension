"""
Module for processing pension agreement PDFs and creating a vector store.
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, agreements_dir: str = "docs/agreements", persist_dir: str = "vectorstore"):
        """
        Initialize the document processor.
        
        Args:
            agreements_dir: Directory containing the pension agreement PDFs
            persist_dir: Directory to save the vector store
        """
        self.agreements_dir = Path(agreements_dir)
        self.persist_dir = Path(persist_dir)
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Text splitter configuration
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
    
    def load_pdf(self, pdf_path: Path) -> List[str]:
        """
        Load and process a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of processed document chunks
        """
        logger.info(f"Loading PDF: {pdf_path}")
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        
        # Extract metadata and content
        metadata = {
            "source": pdf_path.name,
            "title": pdf_path.stem,
            "file_path": str(pdf_path)
        }
        
        # Split the documents
        splits = self.text_splitter.split_documents(pages)
        for split in splits:
            split.metadata.update(metadata)
            
        logger.info(f"Created {len(splits)} chunks from {pdf_path}")
        return splits
    
    def process_documents(self) -> Optional[FAISS]:
        """
        Process all PDF documents in the agreements directory and create a vector store.
        
        Returns:
            FAISS vector store instance or None if processing fails
        """
        if not self.agreements_dir.exists():
            logger.error(f"Agreements directory not found: {self.agreements_dir}")
            return None
            
        pdf_files = list(self.agreements_dir.glob("*.pdf"))
        if not pdf_files:
            logger.error("No PDF files found in agreements directory")
            return None
            
        all_splits = []
        for pdf_path in pdf_files:
            splits = self.load_pdf(pdf_path)
            all_splits.extend(splits)
            
        logger.info(f"Total chunks created: {len(all_splits)}")
        
        # Create and save the vector store
        vectorstore = FAISS.from_documents(all_splits, self.embeddings)
        vectorstore.save_local(str(self.persist_dir))
        logger.info(f"Vector store saved to {self.persist_dir}")
        
        return vectorstore
    
    def load_vectorstore(self) -> Optional[FAISS]:
        """
        Load an existing vector store or create a new one if it doesn't exist.
        
        Returns:
            FAISS vector store instance or None if processing fails
        """
        if self.persist_dir.exists():
            logger.info("Loading existing vector store")
            try:
                return FAISS.load_local(str(self.persist_dir), self.embeddings, allow_dangerous_deserialization=True)
            except Exception as e:
                logger.error(f"Error loading vector store: {e}")
                return self.process_documents()
        else:
            logger.info("Creating new vector store")
            return self.process_documents()
    
    def query_documents(self, query: str, top_k: int = 3) -> List[Any]:
        """
        Query the vector store for documents relevant to the query.
        
        Args:
            query: The query string
            top_k: Number of documents to return
            
        Returns:
            List of document objects with content and metadata
        """
        try:
            vectorstore = self.load_vectorstore()
            if not vectorstore:
                logger.error("Failed to load vector store for query")
                return []
                
            # Query the vector store
            docs = vectorstore.similarity_search(query, k=top_k)
            return docs
        except Exception as e:
            logger.error(f"Error querying documents: {e}", exc_info=True)
            return []
    
if __name__ == "__main__":
    # Example usage
    processor = DocumentProcessor()
    vectorstore = processor.load_vectorstore()
    if vectorstore:
        print(f"Successfully processed documents and created vector store") 