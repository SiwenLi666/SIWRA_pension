"""
Module for processing pension agreement PDFs and creating a vector store.
"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import json
import time
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from .presentation_db import PensionAnalysisFactors, PensionAnalysisManager
from .analyst_agent import PensionAnalystAgent
from .retriever_tool import RetrieverTool
from .document_analyst_agent import DocumentAnalystAgent
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0  # Ensure consistent results

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self, analyst_agent: PensionAnalystAgent, agreements_dir: str = "docs/agreements", persist_dir: str = "vectorstore"):
        self.agreements_dir = Path(os.path.join(os.path.dirname(__file__), '..', 'docs', 'agreements'))
        self.persist_dir = Path(persist_dir)
        self.analysis_manager = PensionAnalysisManager()  # Initialize the manager
        self.analyst_agent = analyst_agent  # Use the passed instance
        self.document_analyst = DocumentAnalystAgent()
        self.all_agreements = []
        
        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Text splitter configuration
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=50,
            length_function=len,
        )
    




    def load_pdf(self, pdf_path: Path) -> List[str]:
        """Load and process a PDF file, splitting into chunks while preserving metadata."""
        logger.info(f"Loading PDF: {pdf_path}")
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()  # ✅ Loads all pages

        all_splits = []
        
        for i, page in enumerate(pages):
            text_content = page.page_content.strip()  # ✅ Ensure no empty space
            if not text_content:
                logger.warning(f"Skipping empty page {i + 1} in {pdf_path.name}")
                continue  # ✅ Skip pages with no text

            try:
                detected_language = detect(text_content)  # ✅ Detect language from text
            except Exception as e:
                logger.warning(f"Could not detect language for {pdf_path.name}, page {i + 1}. Error: {e}")
                detected_language = "unknown"  # ✅ Set a default if detection fails

            metadata = {
                "source": pdf_path.name,
                "title": pdf_path.stem,
                "file_path": str(pdf_path),
                "page_number": i + 1,
                "language": detected_language
            }

            # ✅ Split text while preserving metadata
            splits = self.text_splitter.split_documents(pages)  # ✅ Use full pages, not just [page]
            for split in splits:
                if "metadata" not in split:  # ✅ Ensure metadata exists
                    split.metadata = {}

                split.metadata.update(metadata)  # ✅ Attach correct metadata

            all_splits.extend(splits)

        logger.info(f"Created {len(all_splits)} chunks from {pdf_path}")
        return all_splits



        


    def save_agreements_to_json(self, agreements: List[str]):
        """Save the list of agreements to a JSON file."""
        agreements_data = {
            "agreements": [{"name": agreement, "description": f"Description for {agreement}"} for agreement in agreements]
        }
        json_path = self.persist_dir / 'summary.json'  # Save in the same directory as the vector store
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(agreements_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Agreements saved to {json_path}")



    def process_documents(self) -> None:


        if not self.agreements_dir.exists():
            logger.error(f"Agreements directory not found: {self.agreements_dir}")
            return

        json_path = self.persist_dir / 'summary.json'
        existing_agreements = set()  # ✅ Ensure it's always defined

        if not json_path.exists():
            logger.warning(f"{json_path} not found. Proceeding to process documents.")
        else:
            with open(json_path, 'r') as f:
                existing_data = json.load(f)
                existing_agreements = {entry['name'] for entry in existing_data.get('agreements', [])}  # ✅ Safe retrieval

        all_agreements = {folder.name for folder in self.agreements_dir.iterdir() if folder.is_dir()}
  
        if all_agreements != existing_agreements:
            logger.info(f"Mismatch found! Agreements in folder: {all_agreements}, Agreements in summary.json: {existing_agreements}")
            self.rebuild_vectorstore(all_agreements)  # ✅ Extract vectorstore logic into a separate function
            all_splits = []  

            for agreement_folder in self.agreements_dir.iterdir():
                if agreement_folder.is_dir():
                    pdf_files = list(agreement_folder.glob("*.pdf"))
                    if not pdf_files:
                        logger.warning(f"No PDF files found in agreement folder: {agreement_folder.name}")
                        continue
                    
                    folder_splits = []
                    for pdf_path in pdf_files:
                        splits = self.load_pdf(pdf_path)
                        folder_splits.extend(splits)

                    logger.info(f"Total chunks created from {agreement_folder.name}: {len(folder_splits)}")
                    all_splits.extend(folder_splits)
                    self.analysis_manager.save_agreement(agreement_folder.name)


            # ✅ Ensure each document chunk has proper metadata before storing in FAISS
            for doc in all_splits:
                if "metadata" not in doc:
                    doc.metadata = {}

            doc.metadata["source"] = doc.metadata.get("source", pdf_path.name)  # ✅ Store PDF filename
            doc.metadata["page_number"] = doc.metadata.get("page_number", doc.metadata.get("page", "Unknown"))  # ✅ Use correct page reference
            doc.metadata["language"] = doc.metadata.get("language", detected_language)  # ✅ Store detected language
            
            batch_size = 5000  # ✅ Process in smaller batches
            for i in range(0, len(all_splits), batch_size):
                batch = all_splits[i : i + batch_size]
                vectorstore = FAISS.from_documents(batch, self.embeddings)
                vectorstore.save_local(str(self.persist_dir))
                total_batches = (total_chunks // batch_size) + (1 if total_chunks % batch_size else 0)
                start_time = time.time()  # Track total processing time
                
                logger.info(f"🚀 Starting FAISS processing: {total_chunks} total chunks across {total_batches} batches.")
                for batch_index, i in enumerate(range(0, total_chunks, batch_size)):
                    batch = all_splits[i : i + batch_size]

                    # ✅ Track time for this batch
                    batch_start = time.time()

                    # ✅ Process FAISS index for this batch
                    vectorstore = FAISS.from_documents(batch, self.embeddings)
                    vectorstore.save_local(str(self.persist_dir))

                    batch_time = time.time() - batch_start
                    elapsed_time = time.time() - start_time
                    estimated_remaining = (batch_time * (total_batches - (batch_index + 1)))

                    # ✅ Log detailed progress
                    logger.info(
                        f"✅ Processed batch {batch_index + 1}/{total_batches} "
                        f"({(i + batch_size)}/{total_chunks} chunks, {((i + batch_size) / total_chunks) * 100:.2f}% complete) "
                        f"in {batch_time:.2f} seconds. Estimated remaining time: {estimated_remaining:.2f} seconds."
                    )

                # ✅ Final log
                total_time = time.time() - start_time
                logger.info(f"🎉 FAISS processing complete! {total_chunks} chunks processed in {total_time:.2f} seconds.")


            # ✅ Ensure RetrieverTool can query the new FAISS index
            retriever = RetrieverTool(persist_dir=str(self.persist_dir))
            logger.info("RetrieverTool is now ready to query documents.")

            # ✅ Save agreements to JSON
            self.save_agreements_to_json(all_agreements)

        else:
            logger.info("All files are up to date, calling analyst agent...")
            self.query_document_analyst_and_update_json(all_agreements)


    def query_document_analyst_and_update_json(self, agreements: List[str]):
        """Uses DocumentAnalystAgent to analyze agreements and update JSON storage."""
        for agreement in agreements:
            responses = self.document_analyst.analyze_agreement_info(agreement)
            full_name = responses.get(f"What is the full name of the agreement {agreement}? answer only the name", "Unknown Agreement")
            user_group = responses.get(f"What user group is the agreement {agreement} for?", "Unknown Group")

            self.update_json_with_agreement_info(agreement, full_name, user_group)



    def update_json_with_agreement_info(self, agreement: str, full_name: str, user_group: str):
        json_path = self.persist_dir / 'summary.json'

        # Ensure the summary file exists
        if not json_path.exists():
            logger.warning(f"{json_path} not found. Creating a new summary.json file.")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({"agreements": []}, f, ensure_ascii=False, indent=4)

        # Load the existing JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Loaded summary.json with {len(data['agreements'])} agreements.")

        # ✅ Debug the actual values passed
        logger.info(f"Updating '{agreement}': full_name='{full_name}', user_group='{user_group}'")

        # Check if the agreement exists in JSON
        updated = False
        for entry in data['agreements']:
            if entry['name'] == agreement:
                logger.info(f"Found existing agreement '{agreement}', updating details.")
                entry['full_name'] = full_name
                entry['user_group'] = user_group
                updated = True
                break  # Stop once found

        # If agreement was not found, add it as new
        if not updated:
            logger.info(f"Adding new agreement '{agreement}' to summary.json.")
            data['agreements'].append({
                "name": agreement,
                "full_name": full_name,
                "user_group": user_group
            })

        # ✅ Debug final data before saving
        logger.info(f"Final JSON structure before saving: {json.dumps(data, indent=4, ensure_ascii=False)}")

        # Save the updated JSON
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"Successfully saved updated summary.json.")


    def load_vectorstore(self) -> Optional[FAISS]:
        """
        Load an existing vector store or create a new one if it doesn't exist.
        
        Returns:
            FAISS vector store instance or None if processing fails
        """
        logger.info("Creating or loading vector store")
        return self.process_documents()  # Always process documents when running the script
    
    def query_documents(self, question, selected_agreements, top_k=3):
        agreements_path = 'docs/agreements/'
        documents = []
    
        # Check if selected_agreements is a list
        if isinstance(selected_agreements, list):
            for selected_agreement in selected_agreements:
                agreement_folder = os.path.join(agreements_path, selected_agreement)
                if os.path.exists(agreement_folder):
                    for filename in os.listdir(agreement_folder):
                        if filename.endswith(".txt"):
                            filepath = os.path.join(agreement_folder, filename)
                            with open(filepath, 'r', encoding='utf-8') as file:
                                document = file.read()
                                documents.append(document)
        else:
            # Handle single agreement case
            agreement_folder = os.path.join(agreements_path, selected_agreements)
            if os.path.exists(agreement_folder):
                for filename in os.listdir(agreement_folder):
                    if filename.endswith(".txt"):
                        filepath = os.path.join(agreement_folder, filename)
                        with open(filepath, 'r', encoding='utf-8') as file:
                            document = file.read()
                            documents.append(document)
    
        retriever = RetrieverTool()
        relevant_documents = retriever.query(question, top_k=top_k)

        return relevant_documents

    def create_embeddings(self, documents: List[str]) -> List[Any]:
        """Create embeddings for the given documents."""
        logger.info(f"Creating embeddings for {len(documents)} documents.")
        embeddings = self.embeddings.embed_documents(documents)
        logger.info(f"Generated {len(embeddings)} embeddings.")
        return embeddings


    def load_agreements(self):
        with open('agreements.json', 'r') as file:
            data = json.load(file)
            return data['agreements']
    
    def rebuild_vectorstore(self, all_agreements):
        """Processes and embeds documents from scratch when agreements are updated."""
        logger.info("Rebuilding FAISS vectorstore from scratch...")
        all_splits = []

        for agreement_folder in self.agreements_dir.iterdir():
            if agreement_folder.is_dir():
                pdf_files = list(agreement_folder.glob("*.pdf"))
                if not pdf_files:
                    logger.warning(f"No PDF files found in agreement folder: {agreement_folder.name}")
                    continue

                folder_splits = []
                for pdf_path in pdf_files:
                    splits = self.load_pdf(pdf_path)
                    folder_splits.extend(splits)

                logger.info(f"Total chunks created from {agreement_folder.name}: {len(folder_splits)}")
                all_splits.extend(folder_splits)
                self.analysis_manager.save_agreement(agreement_folder.name)

        for doc in all_splits:
            if not hasattr(doc, "metadata") or doc.metadata is None:
                doc.metadata = {}  # ✅ Ensure metadata exists

            doc.metadata["source"] = doc.metadata.get("source", pdf_path.name)  # ✅ Store PDF filename
            doc.metadata["page_number"] = doc.metadata.get("page_number", doc.metadata.get("page", "Unknown"))  # ✅ Ensure page reference
            doc.metadata["language"] = doc.metadata.get("language", "Unknown")  # ✅ Default language

        # ✅ Now store documents properly in FAISS
        vectorstore = FAISS.from_documents(all_splits, self.embeddings)
        vectorstore.save_local(str(self.persist_dir))
        logger.info(f"Vector store saved to {self.persist_dir} with {len(all_splits)} document chunks.")

        # ✅ Ensure RetrieverTool can query the new FAISS index
        retriever = RetrieverTool(persist_dir=str(self.persist_dir))
        logger.info("RetrieverTool is now ready to query documents.")

        # ✅ Save agreements to JSON
        self.save_agreements_to_json(all_agreements)


if __name__ == "__main__":
    from .analyst_agent import PensionAnalystAgent
    from .document_processor import DocumentProcessor

    # ✅ First, create DocumentProcessor (since analyst_agent needs it)
    processor = DocumentProcessor(analyst_agent=None)  # Temporarily set analyst_agent to None

    # ✅ Now, create PensionAnalystAgent, passing DocumentProcessor
    analyst_agent = PensionAnalystAgent(doc_processor=processor)

    # ✅ Reassign analyst_agent inside processor
    processor.analyst_agent = analyst_agent

    # ✅ Log before loading vectorstore
    logger.info("Starting document processing via load_vectorstore...")
    
    # ✅ Ensure `load_vectorstore()` runs when the script is executed
    processor.load_vectorstore()

    print("Document-Processor and document-analysis-agent successfully initialized!")
