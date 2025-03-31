import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS
from langchain_core.messages import SystemMessage, HumanMessage
from langdetect import detect, DetectorFactory
from src.utils.config import BASE_DIR, VECTORSTORE_DIR, SUMMARY_JSON_PATH, OPENAI_API_KEY
from src.database.presentation_db import PensionAnalysisManager

DetectorFactory.seed = 0
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.WARNING,  # 🔇 suppress info/debug
    format="%(levelname)s:%(name)s:%(message)s"
)

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self):
        self.agreements_dir = Path(BASE_DIR) / "data"
        self.persist_dir = Path(VECTORSTORE_DIR)
        self.analysis_manager = PensionAnalysisManager()
        self.embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=50, length_function=len)

    def load_pdf(self, pdf_path: Path) -> List[Document]:
        logger.info(f"📄 Loading PDF: {pdf_path}")
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        all_splits = []

        for i, page in enumerate(pages):
            if not page.page_content.strip():
                continue

            try:
                lang = detect(page.page_content.strip())
            except Exception:
                lang = "unknown"

            splits = self.text_splitter.split_documents([page])
            for split in splits:
                split.metadata.update({
                    "source": str(pdf_path.relative_to(self.agreements_dir)),
                    "file_path": str(pdf_path),
                    "title": pdf_path.stem,
                    "page_number": i + 1,
                    "language": lang
                })

            all_splits.extend(splits)

        logger.info(f"🔹 Created {len(all_splits)} chunks from {pdf_path.name}")
        return all_splits

    def process_documents(self) -> Optional[FAISS]:
        if not self.agreements_dir.exists():
            logger.error(f"❌ Agreements folder missing: {self.agreements_dir}")
            return

        json_path = Path(SUMMARY_JSON_PATH)
        existing_agreements = set()
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing_agreements = {entry["name"] for entry in existing_data.get("agreements", [])}
            except Exception as e:
                logger.warning(f"⚠️ Could not parse summary.json: {e}")

        found_agreements = {f.name for f in self.agreements_dir.iterdir() if f.is_dir()}
        if found_agreements != existing_agreements:
            logger.info("🛠 Detected changes in agreement folders — rebuilding vectorstore.")
            self.rebuild_vectorstore(found_agreements)
        else:
            logger.info("✅ All agreements matched. Vectorstore already built.")

        return FAISS.load_local(str(self.persist_dir), self.embeddings, allow_dangerous_deserialization=True)

    def rebuild_vectorstore(self, all_agreements: set):
        logger.info("🔄 Rebuilding FAISS vectorstore from PDFs...")
        all_splits = []
        all_summaries = {}

        for folder in self.agreements_dir.iterdir():
            if not folder.is_dir():
                continue
            agreement_name = folder.name
            folder_splits = []  # ✅ declare properly
            all_summaries[agreement_name] = []

            for pdf_path in folder.glob("*.pdf"):
                splits = self.load_pdf(pdf_path)
                folder_splits.extend(splits)  # ✅ collect here

                # Summarize
                context = "\n\n".join([s.page_content[:500] for s in splits[:3]])
                prompt = f"Sammanfatta innehållet i följande dokument ({pdf_path.name}) i 2–3 meningar på svenska."
                llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=OPENAI_API_KEY)
                summary = llm.invoke([
                    SystemMessage(content=prompt),
                    HumanMessage(content=context)
                ]).content.strip()

                all_summaries[agreement_name].append({
                    "file": pdf_path.name,
                    "summary": summary
                })

            all_splits.extend(folder_splits)  # ✅ now this is meaningful

        # Save chunks
        preview_path = self.persist_dir / "chunk_preview.json"
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump([{"text": c.page_content, "metadata": c.metadata} for c in all_splits], f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Saved {len(all_splits)} chunk previews → {preview_path}")

        # Embed in batches
        batch_size = 1000
        logger.info(f"🚀 Embedding {len(all_splits)} chunks...")
        for i in range(0, len(all_splits), batch_size):
            batch = all_splits[i:i+batch_size]
            faiss_index = FAISS.from_documents(batch, self.embeddings)
            faiss_index.save_local(str(self.persist_dir))
            logger.info(f"✅ Embedded batch {i//batch_size + 1}")

        self.save_summary_json(all_agreements, all_summaries)
        logger.info("🎉 Vectorstore build complete.")


    def save_summary_json(self, agreements: set, all_summaries: Dict[str, List[Dict[str, str]]]):
        Path(SUMMARY_JSON_PATH).parent.mkdir(parents=True, exist_ok=True)
        data = {"agreements": []}
        for agreement in sorted(agreements):
            data["agreements"].append({
                "name": agreement,
                "description": f"Auto-generated description for {agreement}",
                "documents": all_summaries.get(agreement, [])
            })

        with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"📄 Saved structured summary.json → {SUMMARY_JSON_PATH}")

    def load_vectorstore(self) -> Optional[FAISS]:
        return self.process_documents()


if __name__ == "__main__":
    print("🚀 Running upgraded DocumentProcessor...")
    processor = DocumentProcessor()
    processor.load_vectorstore()
    print("✅ DocumentProcessor completed.")
