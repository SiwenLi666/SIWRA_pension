"""
Pension advisor agent using RAG for answering pension-related queries.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import langdetect

from langchain_core.callbacks import StreamingStdOutCallbackHandler
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.callbacks.manager import CallbackManager

from .document_processor import DocumentProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class PensionAdvisor:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating new PensionAdvisor instance")
            cls._instance = super(PensionAdvisor, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the pension advisor with a language model and document processor."""
        # Skip initialization if already done
        if PensionAdvisor._initialized:
            return
            
        logger.info("Initializing PensionAdvisor components")
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
            
        self.llm = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            temperature=0,
            streaming=True
        )
        
        # Initialize document processor and load vector store
        logger.info("Loading vector store...")
        self.doc_processor = DocumentProcessor()
        self.vectorstore = self.doc_processor.load_vectorstore()
        if not self.vectorstore:
            raise ValueError("Failed to load or create vector store")
            
        # Create the RAG prompts for different languages
        self.prompt_templates = {
            'sv': """Du är en hjälpsam och professionell pensionsrådgivare. Använd följande kontext för att besvara frågan. Om du inte vet svaret, säg bara att du inte vet. Försök inte hitta på ett svar.

Kontext:
{context}

Fråga: {question}

Hjälpsamt svar:""",
            
            'en': """You are a helpful and professional pension advisor. Use the following pieces of context to answer the question. If you don't know the answer, just say that you don't know. Don't try to make up an answer.

Context:
{context}

Question: {question}

Helpful Answer:"""
        }
        
        # Create the retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4}
        )
        
        # Initialize RAG chains for both languages
        self.rag_chains = {}
        for lang, template in self.prompt_templates.items():
            prompt = PromptTemplate.from_template(template)
            self.rag_chains[lang] = (
                {"context": self.retriever, "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
        
        logger.info("PensionAdvisor initialization complete")
        PensionAdvisor._initialized = True
        
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.
        Returns 'sv' for Swedish, 'en' for English, defaults to 'sv'
        """
        try:
            lang = langdetect.detect(text)
            return 'sv' if lang == 'sv' else 'en'
        except:
            return 'sv'  # Default to Swedish if detection fails
        
    async def ask(self, question: str) -> str:
        """
        Ask a question about pensions and get a response based on the knowledge base.
        
        Args:
            question: The question to ask about pensions
            
        Returns:
            str: The response from the model
        """
        try:
            logger.info(f"Processing question: {question}")
            
            # Detect language and use appropriate chain
            lang = self.detect_language(question)
            logger.info(f"Detected language: {lang}")
            
            # Use the appropriate chain based on language
            rag_chain = self.rag_chains.get(lang, self.rag_chains['sv'])
            
            response = await rag_chain.ainvoke(question)
            logger.info(f"Generated response: {response[:100]}...")  # Log first 100 chars
            return response
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}")
            error_messages = {
                'sv': f"Ett fel uppstod vid behandling av din fråga: {str(e)}",
                'en': f"Error processing your question: {str(e)}"
            }
            return error_messages.get(self.detect_language(question), error_messages['sv'])

def main():
    """Example usage of the pension advisor."""
    import asyncio
    
    async def run_examples():
        advisor = PensionAdvisor()
        
        # Example questions in both languages
        questions = [
            "Vad är AKAP-KR?",
            "What is AKAP-KR?",
            "Hur beräknas pensionen enligt AKAP-KR?",
            "What happens to my pension if I change employers?"
        ]
        
        for question in questions:
            print(f"\nQ: {question}")
            print(f"A: {await advisor.ask(question)}\n")
    
    asyncio.run(run_examples())

if __name__ == "__main__":
    main()