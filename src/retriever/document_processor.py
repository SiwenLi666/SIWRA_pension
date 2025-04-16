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
from src.utils.config import BASE_DIR, VECTORSTORE_DIR, SUMMARY_JSON_PATH, OPENAI_API_KEY, ENHANCED_METADATA_EXTRACTION, STRUCTURED_TRANSITIONAL_PROVISIONS

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
        self.embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        
        # Improved chunking strategy with higher overlap and semantic boundaries
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,  # Increased overlap to maintain context between chunks
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""]  # Prioritize breaking at paragraph/sentence boundaries
        )
        
        # Common pension acronyms and terms
        self.pension_terms = {
            "PA16": "Pensionsavtal för statligt anställda från 2016",
            "PA03": "Pensionsavtal för statligt anställda från 2003",
            "ITP": "Industrins och handelns tilläggspension",
            "ITP1": "ITP-avdelning 1, premiebestämd ålderspension för födda 1979 eller senare",
            "ITP2": "ITP-avdelning 2, förmånsbestämd ålderspension för födda 1978 eller tidigare",
            "ITPK": "ITP kompletterande ålderspension",
            "KAP-KL": "Kollektivavtalad Pension för kommun- och landstingsanställda",
            "AKAP-KL": "Avgiftsbestämd Kollektivavtalad Pension för kommun- och landstingsanställda",
            "AKAP-KR": "Avgiftsbestämd Kollektivavtalad Pension för kommun- och regionsanställda",
            "SAP-R": "Särskild Avtalspension för Räddningstjänstpersonal",
            "SKR": "Sveriges Kommuner och Regioner",
            "SKR2023": "Pensionsavtal för kommuner och regioner från 2023",
            "PFA": "Pensions- och försäkringsavtal",
            "ATP": "Allmän tilläggspension",
            "PPM": "Premiepensionsmyndigheten",
            "SPV": "Statens tjänstepensionsverk",
            "KPA": "Kommunernas Pensionsanstalt",
            "AIP": "Avtalspension SAF-LO",
            "FTP": "Försäkringstjänstepension"
        }

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
        
    def extract_acronyms_and_definitions(self, text: str) -> Tuple[List[str], Dict[str, str], List[str]]:
        """
        Extract pension-related acronyms and definitions from text.
        Returns a tuple of (found_acronyms, found_definitions)
        """
        if not ENHANCED_METADATA_EXTRACTION:
            return [], {}
            
        found_acronyms = []
        found_definitions = {}
        
        # Find known pension terms and acronyms
        for term, definition in self.pension_terms.items():
            if term.lower() in text.lower():
                found_acronyms.append(term)
                found_definitions[term] = definition
        
        # Look for pattern: "X (Y)" where Y is likely an acronym
        acronym_pattern = re.compile(r'([A-Za-zåäöÅÄÖ\s]+)\s+\(([A-Z0-9\-]{2,})\)')
        for match in acronym_pattern.finditer(text):
            term, acronym = match.groups()
            term = term.strip()
            if acronym not in found_acronyms:
                found_acronyms.append(acronym)
                found_definitions[acronym] = term
        
        # Look for pattern: "Y (X)" where Y is likely an acronym and X is its definition
        definition_pattern = re.compile(r'([A-Z0-9\-]{2,})\s+\(([A-Za-zåäöÅÄÖ\s]+)\)')
        for match in definition_pattern.finditer(text):
            acronym, definition = match.groups()
            definition = definition.strip()
            if acronym not in found_acronyms:
                found_acronyms.append(acronym)
                found_definitions[acronym] = definition
        
        # Look for explicit definitions with "betyder", "innebär", "definieras som", etc.
        definition_markers = ["betyder", "innebär", "definieras som", "avser", "syftar på"]
        for marker in definition_markers:
            pattern = re.compile(rf'([A-Z0-9\-]{{2,}})\s+{marker}\s+([^.]+)')
            for match in pattern.finditer(text):
                term, definition = match.groups()
                definition = definition.strip()
                if term not in found_acronyms:
                    found_acronyms.append(term)
                    found_definitions[term] = definition
                    
        # Detect target groups dynamically
        target_groups = []
        
        # Common patterns for target groups
        base_patterns = [
            r'(födda\s+(?:före|efter|mellan)\s+\d{4}(?:\s+och\s+\d{4})?)',
            r'(anställda\s+(?:före|efter|från|mellan)\s+\d{4}(?:\s+och\s+\d{4})?)',
            r'(personer\s+(?:som|med)\s+[\w\såäöÅÄÖ]+)',
            r'((?:statligt|kommunalt|regionalt)\s+anställda)'
        ]
        
        # Dynamic occupation detection
        occupation_pattern = r'(\b[\w]+are\b)'
        occupation_matches = re.findall(occupation_pattern, text.lower())
        
        # Filter out common words ending with 'are' that aren't occupations
        common_false_positives = ['senare', 'tidigare', 'vidare', 'närmare']
        occupation_matches = [match for match in occupation_matches 
                             if match not in common_false_positives 
                             and len(match) > 4]  # Avoid short words
        
        # Process base patterns
        for pattern in base_patterns:
            matches = re.findall(pattern, text.lower())
            target_groups.extend(matches)
            
        # Add occupation matches
        target_groups.extend(occupation_matches)
        
        # Look for specific phrases indicating target groups
        target_indicators = ['gäller för', 'tillämpas på', 'omfattar', 'avser']
        for indicator in target_indicators:
            pattern = rf'{indicator}\s+([\w\såäöÅÄÖ,]+?)(?:\.|\n)'
            matches = re.findall(pattern, text.lower())
            clean_matches = [match.strip() for match in matches if len(match.strip()) > 3]
            target_groups.extend(clean_matches)
            
        return found_acronyms, found_definitions, target_groups
        
    def extract_transitional_provisions(self, text: str) -> Dict[str, any]:
        """
        Extract structured metadata about transitional provisions/rules in the text.
        Returns a dictionary with information about the transitional provision.
        """
        if not STRUCTURED_TRANSITIONAL_PROVISIONS:
            return {}
            
        # Initialize result structure
        result = {
            "is_transitional": False,
            "effective_date": None,
            "expiry_date": None,
            "affected_groups": [],
            "previous_rule": None,
            "new_rule": None,
            "transition_type": None,  # gradual, immediate, optional, etc.
            "conditions": []
        }
        
        # Check if this is likely a transitional provision
        transition_indicators = [
            "övergångsbestämmelse", "övergångsregel", "ikraftträdande", 
            "träder i kraft", "gäller från och med", "upphör att gälla",
            "ersätter tidigare", "ersätter bestämmelse", "tidigare version",
            "tidigare avtal", "tidigare regler", "tidigare bestämmelser"
        ]
        
        text_lower = text.lower()
        is_transitional = any(indicator in text_lower for indicator in transition_indicators)
        
        if not is_transitional:
            return result
            
        # Mark as transitional
        result["is_transitional"] = True
        
        # Extract effective dates
        date_patterns = [
            # Format: YYYY-MM-DD
            r'(\d{4}-\d{2}-\d{2})',
            # Format: DD month YYYY
            r'(\d{1,2}\s+(?:januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december)\s+\d{4})',
            # Format: from YYYY
            r'från\s+(?:och\s+med\s+)?(?:den\s+)?(\d{1,2}\s+\w+\s+\d{4}|\d{4})',
            # Format: until YYYY
            r'till\s+(?:och\s+med\s+)?(?:den\s+)?(\d{1,2}\s+\w+\s+\d{4}|\d{4})'
        ]
        
        # Extract effective date
        for pattern in date_patterns:
            effective_matches = re.findall(r'träder\s+i\s+kraft\s+(?:den\s+)?'+pattern, text_lower)
            effective_matches.extend(re.findall(r'gäller\s+från\s+(?:och\s+med\s+)?(?:den\s+)?'+pattern, text_lower))
            
            if effective_matches:
                result["effective_date"] = effective_matches[0]
                break
                
        # Extract expiry date
        for pattern in date_patterns:
            expiry_matches = re.findall(r'gäller\s+till\s+(?:och\s+med\s+)?(?:den\s+)?'+pattern, text_lower)
            expiry_matches.extend(re.findall(r'upphör\s+att\s+gälla\s+(?:den\s+)?'+pattern, text_lower))
            
            if expiry_matches:
                result["expiry_date"] = expiry_matches[0]
                break
        
        # Extract affected groups
        affected_patterns = [
            r'gäller\s+för\s+([^.]+)',
            r'tillämpas\s+på\s+([^.]+)',
            r'omfattar\s+([^.]+)',
            r'för\s+(?:anställda|personer)\s+([^.]+)'
        ]
        
        for pattern in affected_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                # Clean up and add to affected groups
                for match in matches:
                    cleaned = match.strip()
                    if len(cleaned) > 3 and cleaned not in result["affected_groups"]:
                        result["affected_groups"].append(cleaned)
        
        # Determine transition type
        if "successiv" in text_lower or "gradvis" in text_lower or "stegvis" in text_lower:
            result["transition_type"] = "gradual"
        elif "omedelbar" in text_lower or "direkt" in text_lower:
            result["transition_type"] = "immediate"
        elif "valfri" in text_lower or "frivillig" in text_lower or "möjlighet att välja" in text_lower:
            result["transition_type"] = "optional"
        
        # Extract conditions
        condition_markers = ["under förutsättning att", "om", "villkor", "krav", "måste", "ska", "endast om"]
        for marker in condition_markers:
            pattern = marker + r'\s+([^.]+)'
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if len(match.strip()) > 5 and match.strip() not in result["conditions"]:
                    result["conditions"].append(match.strip())
        
        # Extract previous rule reference
        prev_patterns = [r'tidigare\s+(?:avtal|regel|bestämmelse|version)\s+([^.]+)', r'ersätter\s+([^.]+)']
        for pattern in prev_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                result["previous_rule"] = matches[0].strip()
                break
                
        return result


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
        """
        Load a PDF file, extract text and metadata, and return a list of Document objects.
        Uses an improved chunking strategy that keeps related information together.
        """
        logger.info(f"📄 Loading PDF: {pdf_path}")
        agreement_name = pdf_path.parent.name
        
        try:
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()
            
            # Group pages by chapter and section to keep related content together
            sections = []
            current_section = {
                "text": "",
                "chapter": None,
                "title": None,
                "pages": [],
                "paragraphs": set(),
                "linked_titles": set(),
                "references": set(),
                "is_amendment": False,
                "footnotes": "",
                "acronyms": set(),
                "definitions": {},
                "target_groups": set(),
                "language": "sv"
            }
            
            current_chapter = None
            current_paragraph = None
            
            # First pass: group pages by chapter/section
            for i, page in enumerate(pages):
                if not page.page_content.strip():
                    continue
                    
                text = page.page_content
                main_text, footnotes = self.isolate_main_text(text)
                
                # Detect language
                try:
                    lang = detect(main_text)
                except:
                    lang = "sv"  # Default to Swedish if detection fails
                
                # Extract chapter and title information
                chapter_title = self.extract_chapter_title(main_text)
                chapter_number = self.extract_chapter_number(main_text)
                paragraph_number = self.extract_paragraph_number(main_text)
                
                # Extract other metadata
                linked_titles, references, is_amendment = self.detect_linked_chunks(main_text)
                acronyms, definitions, target_groups = self.extract_acronyms_and_definitions(main_text)
                transitional_provisions = self.extract_transitional_provisions(main_text)
                
                # Determine if this is a new section
                new_section = False
                
                # Start a new section if chapter changes or we find a major title
                if chapter_number and chapter_number != current_section["chapter"]:
                    new_section = True
                    current_chapter = chapter_number
                elif chapter_title and chapter_title != current_section["title"] and len(main_text) < 1000:
                    # Only consider it a new section if the page is relatively short (likely a title page)
                    new_section = True
                
                # If this is a new section and we have content in the current section, save it
                if new_section and current_section["text"]:
                    sections.append(dict(current_section))  # Make a copy
                    
                    # Reset the current section
                    current_section = {
                        "text": "",
                        "chapter": chapter_number or current_section["chapter"],
                        "title": chapter_title or "",
                        "pages": [],
                        "paragraphs": set(),
                        "linked_titles": set(),
                        "references": set(),
                        "is_amendment": False,
                        "footnotes": "",
                        "acronyms": set(),
                        "definitions": {},
                        "target_groups": set(),
                        "language": lang
                    }
                
                # Update the current section
                if current_section["text"]:
                    current_section["text"] += "\n\n" + main_text
                else:
                    current_section["text"] = main_text
                    
                current_section["pages"].append(i + 1)
                
                if paragraph_number:
                    current_section["paragraphs"].add(paragraph_number)
                    current_paragraph = paragraph_number
                
                current_section["linked_titles"].update(linked_titles)
                current_section["references"].update(references)
                current_section["is_amendment"] = current_section["is_amendment"] or is_amendment
                
                if footnotes:
                    if current_section["footnotes"]:
                        current_section["footnotes"] += "\n" + footnotes
                    else:
                        current_section["footnotes"] = footnotes
                
                current_section["acronyms"].update(acronyms)
                current_section["definitions"].update(definitions)
                current_section["target_groups"].update(target_groups)
                
                # If the section text is getting too long, close it and start a new one
                if len(current_section["text"]) > 2000:
                    sections.append(dict(current_section))  # Make a copy
                    
                    # Start a new section with the same metadata
                    current_section = {
                        "text": "",
                        "chapter": current_section["chapter"],
                        "title": current_section["title"],
                        "pages": [],
                        "paragraphs": set(),
                        "linked_titles": set(),
                        "references": set(),
                        "is_amendment": current_section["is_amendment"],
                        "footnotes": "",
                        "acronyms": set(),
                        "definitions": {},
                        "target_groups": set(),
                        "language": lang
                    }
            
            # Add the last section if it has content
            if current_section["text"]:
                sections.append(current_section)
            
            # Second pass: create chunks from each section
            all_splits = []
            
            for section in sections:
                # Split the section text into chunks
                chunks = self.text_splitter.split_text(section["text"])
                
                # Create Document objects for each chunk
                for chunk in chunks:
                    # Format metadata
                    paragraphs_str = ", ".join([f"{p} §" for p in sorted(section["paragraphs"])]) if section["paragraphs"] else None
                    chapter_str = f"{section['chapter']} KAP" if section["chapter"] else None
                    
                    # Create the document with metadata
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "agreement_name": agreement_name,
                            "title": section["title"],
                            "chapter": chapter_str,
                            "paragraph": paragraphs_str,
                            "linked_titles": list(section["linked_titles"]),
                            "references": list(section["references"]),
                            "is_amendment": section["is_amendment"],
                            "footnotes": section["footnotes"],
                            "source": str(pdf_path.relative_to(self.agreements_dir)),
                            "file_path": str(pdf_path),
                            "page_numbers": section["pages"],  # Now a list of page numbers
                            "language": section["language"],
                            "acronyms": list(section["acronyms"]),
                            "definitions": section["definitions"],
                            "target_groups": list(section["target_groups"]),
                            "transitional_provisions": transitional_provisions if 'transitional_provisions' in locals() else {},
                            "semantic_section": True  # Flag to indicate this is a semantic chunk
                        }
                    )
                    all_splits.append(doc)

                # Rensa onödiga fält
                for k in ["producer", "creator", "title"]:
                    split.metadata.pop(k, None)

            all_splits.extend(splits)

            logger.info(f"🔹 Created {len(all_splits)} chunks from {pdf_path.name}")
            return all_splits
        except Exception as e:
            logger.error(f"❌ Error loading PDF {pdf_path}: {e}")
            return []





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
