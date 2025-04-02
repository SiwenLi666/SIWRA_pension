import os
import json
import time
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
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

    def detect_linked_chunks(self, text: str):
        text_lower = text.lower()

        # Detect links to other documents or sections
        linked_titles = []
        references = []
        is_amendment = False

        if "bilaga" in text_lower:
            linked_titles.append("bilaga")
        if "pa16" in text_lower:
            linked_titles.append("PA16")
        if "kompletterar" in text_lower or "ändrar" in text_lower or "ersätter" in text_lower:
            is_amendment = True
        if "kapitel" in text_lower:
            references.append("kapitel")
        if "punkt" in text_lower:
            references.append("punkt")

        return linked_titles, references, is_amendment


    def extract_chapter_title(self, text: str) -> Optional[str]:
        match = re.search(r"\b\d+\s*kap\.\s*(.*?)\n", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    def extract_paragraph_number(self, text: str) -> Optional[str]:
        match = re.search(r"\n\s*(\d+)\s*§", text)
        return match.group(1) if match else None

    def isolate_main_text_and_footnotes(self, text: str) -> Tuple[str, str]:

        """
        Split the main content from footnotes using a horizontal line or footnote number pattern.
        """
        lines = text.strip().splitlines()
        for i, line in enumerate(lines):
            if "____" in line or re.match(r"\d{1,2}\s", line.strip()):
                # Assume everything below is footnote
                main_text = "\n".join(lines[:i]).strip()
                footnotes = "\n".join(lines[i:]).strip()
                return main_text, footnotes
        return text, ""  # No footnotes found

    def detect_visual_chapter(self, text: str) -> Optional[str]:
        lines = text.strip().splitlines()
        for i, line in enumerate(lines):
            if line.strip() and 2 <= len(line.split()) <= 6:
                prev_empty = i == 0 or not lines[i - 1].strip()
                next_empty = i + 1 >= len(lines) or not lines[i + 1].strip()
                is_title_like = line.strip()[0].isupper()
                if prev_empty and next_empty and is_title_like:
                    return line.strip()
        return None


    def load_pdf(self, pdf_path: Path) -> List[Document]:
        logger.info(f"📄 Loading PDF: {pdf_path}")
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        all_splits = []

        agreement_name = pdf_path.parent.name
        title = pdf_path.stem

        current_chapter = None
        current_paragraph = None

        for i, page in enumerate(pages):
            if not page.page_content.strip():
                continue

            try:
                lang = detect(page.page_content.strip())
            except Exception:
                lang = "unknown"

            splits = self.text_splitter.split_documents([page])
            for split in splits:
                full_text = split.page_content
                main_text, footnotes = self.isolate_main_text_and_footnotes(full_text)
                text = main_text

                # Detect chapter using known format or fallback
            chapter_matches = re.findall(r"(\d+)\s*kap\.", text, flags=re.IGNORECASE)
            if not chapter_matches:
                # Fallback: detect bold-style standalone line numbers
                for line in text.splitlines():
                    if re.match(r"^\s*\d+\s+\w+(?:\s+\w+)*\s*$", line):
                        chapter_matches.append(line.strip().split()[0])  # Take just number part
                        break

            paragraph_matches = re.findall(r"\b(\d{1,3})\s*§\b", text)

            # Chapter detection logic
            if len(chapter_matches) > 1:
                chapter = ", ".join(f"{c} KAP" for c in chapter_matches)
                current_chapter = chapter_matches[-1]
            elif chapter_matches:
                current_chapter = chapter_matches[0]
                chapter = f"{current_chapter} KAP"
            else:
                # 🔁 fallback: detect visual chapter
                visual_chap = self.detect_visual_chapter(text)
                chapter = visual_chap if visual_chap else (f"{current_chapter} KAP" if current_chapter else None)


                # Paragraph logic
                if len(paragraph_matches) > 1:
                    paragraph = ", ".join(f"{p} §" for p in paragraph_matches)
                    current_paragraph = paragraph_matches[-1]
                elif paragraph_matches:
                    para_int = int(paragraph_matches[0])
                    if current_paragraph and para_int != int(current_paragraph) + 1:
                        if not chapter_matches:
                            logger.warning(
                                f"⚠️ Paragraph jump at page {i+1} in {pdf_path.name}: "
                                f"{current_paragraph} → {para_int} without new chapter"
                            )
                    current_paragraph = paragraph_matches[0]
                    paragraph = f"{current_paragraph} §"
                else:
                    paragraph = f"{current_paragraph} §" if current_paragraph else None

                # Detect references and amendments
                linked_titles, references, is_amendment = self.detect_linked_chunks(text)

                # 🔥 Wipe everything to avoid leaks
                split.metadata = {}

                # ✅ Set only what you want to keep
                split.metadata.update({
                    "agreement_name": agreement_name,
                    "title": title,
                    "chapter": chapter,
                    "paragraph": paragraph,
                    "linked_titles": linked_titles,
                    "references": references,
                    "is_amendment": is_amendment,
                    "footnotes": footnotes,
                    "source": str(pdf_path.relative_to(self.agreements_dir)),
                    "file_path": str(pdf_path),
                    "page_number": i + 1,
                    "language": lang,
                })


                for k in ["producer", "creator"]:
                    split.metadata.pop(k, None)

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

        index_file = self.persist_dir / "index.faiss"
        if index_file.exists():
            return FAISS.load_local(str(self.persist_dir), self.embeddings, allow_dangerous_deserialization=True)
        else:
            logger.warning(f"⚠️ Vectorstore missing at {index_file} — rebuilding.")
            self.rebuild_vectorstore(found_agreements)
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
