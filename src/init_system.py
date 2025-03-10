"""
Initialize the pension advisor system by processing existing agreements and setting up the vector store.
"""
import asyncio
import logging
from pathlib import Path
from .document_processor import DocumentProcessor
from .presentation_db import presentation_db
from .cost_tracker import cost_tracker

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def init_system():
    """Initialize the system by processing documents and creating the vector store."""
    try:
        # Create necessary directories
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / "data"
        docs_dir = base_dir / "docs"
        agreements_dir = docs_dir / "agreements"
        
        # Create directories if they don't exist
        for directory in [data_dir, docs_dir, agreements_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize presentation database
        logger.info("Initializing presentation database...")
        if not (data_dir / "presentation.db").exists():
            logger.info("Creating new presentation database...")
            presentation_db._init_db()
        
        # Initialize cost tracker
        logger.info("Initializing cost tracker...")
        if not (data_dir / "costs.db").exists():
            logger.info("Creating new cost tracking database...")
            cost_tracker._init_db()
        
        # Check if agreements exist
        if not agreements_dir.exists() or not list(agreements_dir.glob("*.pdf")):
            logger.warning("No pension agreement PDFs found in docs/agreements directory!")
            # Continue anyway as we can still function without agreements
        
        # Initialize document processor
        logger.info("Initializing document processor...")
        processor = DocumentProcessor()
        
        # Process documents and create vector store if documents exist
        if list(agreements_dir.glob("*.pdf")):
            logger.info("Processing documents and creating vector store...")
            vectorstore = processor.process_documents()
            if not vectorstore:
                logger.error("Failed to create vector store!")
                return False
        
        logger.info("System initialization completed successfully!")
        return True
            
    except Exception as e:
        logger.error(f"Error during system initialization: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(init_system())