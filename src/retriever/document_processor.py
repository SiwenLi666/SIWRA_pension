import os
import json
import time
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import pdfplumber
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


    def is_valid_pdf_content(self, text: str) -> bool:
        """
        Check if the extracted PDF content is valid and contains meaningful text.
        
        Args:
            text: Extracted text from PDF
            
        Returns:
            True if the content is valid, False otherwise
        """
        if not text or len(text.strip()) < 50:  # Too short to be meaningful
            return False
            
        # Check if content only contains signatures or names
        signature_patterns = [
            r'^\s*[A-Z][a-z]+ [A-Z][a-z]+\s*$',  # Just a name like "Helena Larsson"
            r'^\s*Vid protokollet\s*$',
            r'^\s*Justerat den\s*',
            r'^\s*För [A-Z]',  # Organization signatures
            r'^\s*[A-Z][a-z]+ [A-Z][a-z]+\s*\n\s*[A-Z][a-z]+ [A-Z][a-z]+\s*$'  # Multiple names
        ]
        
        # If the text matches any signature pattern and is short, it's likely not valid content
        if len(text.strip()) < 200:  # Short text
            for pattern in signature_patterns:
                if re.match(pattern, text.strip(), re.MULTILINE):
                    return False
        
        # Check for actual pension-related content
        pension_terms = ['pension', 'avtal', 'förmån', 'ersättning', 'kapitel', 'paragraf', '§', 'kap']
        has_pension_terms = any(term in text.lower() for term in pension_terms)
        
        return has_pension_terms


    def group_words_by_line(self, words: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Group words into lines based on their vertical position.
        
        Args:
            words: List of word dictionaries from pdfplumber
            
        Returns:
            List of lines, where each line is a list of word dictionaries
        """
        if not words:
            return []
            
        # Sort words by top position (vertically)
        sorted_words = sorted(words, key=lambda w: w['top'])
        
        lines = []
        current_line = [sorted_words[0]]
        current_top = sorted_words[0]['top']
        
        # Group words with similar vertical position
        for word in sorted_words[1:]:
            # If the word is within 5 units of the current line, add it to the current line
            if abs(word['top'] - current_top) < 5:
                current_line.append(word)
            else:
                # Sort words in the current line by horizontal position
                current_line = sorted(current_line, key=lambda w: w['x0'])
                lines.append(current_line)
                
                # Start a new line
                current_line = [word]
                current_top = word['top']
                
        # Add the last line
        if current_line:
            current_line = sorted(current_line, key=lambda w: w['x0'])
            lines.append(current_line)
            
        return lines
        
    def is_bold_line(self, line: List[Dict[str, Any]]) -> bool:
        """
        Check if a line contains bold text (used to identify chapter titles).
        
        Args:
            line: List of word dictionaries representing a line
            
        Returns:
            True if the line contains bold text, False otherwise
        """
        if not line:
            return False
            
        # Check if any word in the line has a font name containing "Bold"
        for word in line:
            if 'fontname' in word and ('Bold' in word['fontname'] or 'bold' in word['fontname'].lower()):
                return True
                
        return False
        
    def extract_chapters_from_pdf(self, pdf: Any) -> List[Dict[str, Any]]:
        """
        Extract chapters from a PDF file using pdfplumber with enhanced metadata.
        
        Args:
            pdf: A pdfplumber PDF object
            
        Returns:
            List of chapter dictionaries with text and metadata including character positions
        """
        chapters = []
        current_chapter = {
            "text": "",
            "chapter_number": None,
            "title": None,
            "pages": [],
            "paragraphs": set(),
            "chunk_start_page": None,
            "chunk_end_page": None,
            "chunk_start_char": 0,
            "chunk_end_char": 0
        }
        
        # Check if PDF has enough pages to be a valid document
        if len(pdf.pages) < 3:
            logger.warning(f"[WARNING] PDF has only {len(pdf.pages)} pages, might not be a valid document")
        
        total_words = 0
        for page_num, page in enumerate(pdf.pages):
            # Extract words with their formatting information
            try:
                words = page.extract_words(
                    x_tolerance=3,
                    y_tolerance=3,
                    keep_blank_chars=False,
                    use_text_flow=True,
                    extra_attrs=["fontname", "size"]
                )
                total_words += len(words)
            except Exception as e:
                logger.warning(f"[WARNING] Error extracting words from page {page_num+1}: {e}")
                continue
            
            if not words:
                logger.debug(f"No words found on page {page_num+1}")
                continue
                
            # Group words into lines
            lines = self.group_words_by_line(words)
            
            # Extract text from each line
            page_text = ""
            for i, line in enumerate(lines):
                line_text = " ".join(word["text"] for word in line)
                
                # Check if this is a chapter title (bold text and matches chapter pattern)
                is_chapter_title = self.is_bold_line(line) and re.search(r"\b\d+\s*(?:kap|kapitel)\b", line_text.lower())
                
                # If this is a chapter title and we have content in the current chapter, save it
                if is_chapter_title and current_chapter["text"].strip():
                    # Only add the chapter if it contains valid content
                    if self.is_valid_pdf_content(current_chapter["text"]):
                        # Set the end character position
                        current_chapter["chunk_end_char"] = len(current_chapter["text"])
                        current_chapter["chunk_end_page"] = page_num
                        chapters.append(dict(current_chapter))
                    else:
                        logger.debug(f"Skipping invalid chapter content: {current_chapter['text'][:100]}...")
                    
                    # Extract chapter number
                    chapter_match = re.search(r"\b(\d+)\s*(?:kap|kapitel)\b", line_text.lower())
                    chapter_number = chapter_match.group(1) if chapter_match else None
                    
                    # Extract chapter title (text after "kap" or "kapitel")
                    title_match = re.search(r"\b\d+\s*(?:kap|kapitel)\b\s*(.*)", line_text, re.IGNORECASE)
                    title = title_match.group(1).strip() if title_match else line_text
                    
                    # Start a new chapter
                    current_chapter = {
                        "text": line_text + "\n",
                        "chapter_number": chapter_number,
                        "title": title,
                        "pages": [page_num + 1],
                        "paragraphs": set(),
                        "chunk_start_page": page_num + 1,
                        "chunk_end_page": page_num + 1,
                        "chunk_start_char": 0,
                        "chunk_end_char": len(line_text) + 1
                    }
                else:
                    # Add the line to the current chapter
                    if current_chapter["text"]:
                        # Track the character position
                        current_position = len(current_chapter["text"])
                        current_chapter["text"] += line_text + "\n"
                        current_chapter["chunk_end_char"] = len(current_chapter["text"])
                    else:
                        current_chapter["text"] = line_text + "\n"
                        current_chapter["chunk_start_page"] = page_num + 1
                        current_chapter["chunk_start_char"] = 0
                        current_chapter["chunk_end_char"] = len(line_text) + 1
                    
                    # Update chapter metadata
                    if page_num + 1 not in current_chapter["pages"]:
                        current_chapter["pages"].append(page_num + 1)
                    
                    # Update end page
                    current_chapter["chunk_end_page"] = page_num + 1
                    
                    # Check for paragraph numbers
                    paragraph_match = re.search(r"\n\s*(\d+)\s*§", line_text)
                    if paragraph_match:
                        current_chapter["paragraphs"].add(paragraph_match.group(1))
                
                page_text += line_text + "\n"
        
        # Add the last chapter if it has content and it's valid
        if current_chapter["text"].strip() and self.is_valid_pdf_content(current_chapter["text"]):
            # Set the end character position if not already set
            if not current_chapter["chunk_end_char"]:
                current_chapter["chunk_end_char"] = len(current_chapter["text"])
            chapters.append(current_chapter)
        
        # Validate that we have extracted meaningful chapters
        if not chapters:
            logger.warning(f"[WARNING] No valid chapters extracted from PDF with {len(pdf.pages)} pages and {total_words} words")
        else:
            logger.info(f"[INFO] Extracted {len(chapters)} valid chapters with {sum(len(c['text']) for c in chapters)} characters")
            
        return chapters
        
    def split_into_paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs based on newlines, section markers, and semantic boundaries.
        
        Args:
            text: The text to split into paragraphs
            
        Returns:
            List of paragraph strings with meaningful content
        """
        if not text or len(text.strip()) < 50:
            return []
            
        # First, try to split on double newlines which is the most common paragraph separator
        paragraphs = re.split(r"\n\s*\n", text)
        
        # If we got only one paragraph and it's long, try to split on single newlines
        # that are followed by capital letters or numbers (likely paragraph starts)
        if len(paragraphs) == 1 and len(paragraphs[0]) > 1000:
            potential_splits = re.split(r"\n(?=[A-Z\u00c5\u00c4\u00d60-9])", paragraphs[0])
            if len(potential_splits) > 1:
                paragraphs = potential_splits
        
        # Further split paragraphs that contain section markers
        result = []
        for para in paragraphs:
            # Skip paragraphs that are too short to be meaningful
            if len(para.strip()) < 50:
                continue
                
            # Check for section markers like "1 §" or "§ 1"
            if re.search(r"\b\d+\s*§|§\s*\d+\b", para):
                # Split on section markers
                sections = re.split(r"(\b\d+\s*§|§\s*\d+\b)", para)
                
                # Combine the section marker with the following text
                i = 0
                while i < len(sections) - 1:
                    if re.match(r"\b\d+\s*§|§\s*\d+\b", sections[i]):
                        # Section marker is at i, text is at i+1
                        combined = sections[i] + sections[i+1]
                        if len(combined.strip()) >= 50:  # Only add if it's substantial
                            result.append(combined)
                        i += 2
                    else:
                        # Text is at i, section marker is at i+1
                        if i == 0 and len(sections[i].strip()) >= 50:  # First section might not have a marker before it
                            result.append(sections[i])
                        i += 1
                        
                # Add the last section if there's one left
                if i < len(sections) and len(sections[i].strip()) >= 50:
                    result.append(sections[i])
            else:
                # Check if paragraph contains bullet points or numbered lists
                if re.search(r"\n\s*[•\-\*]|\n\s*\d+\.\s", para):
                    # Keep bullet points together as they're related
                    result.append(para)
                elif len(para.strip()) >= 50:  # Only add substantial paragraphs
                    result.append(para)
        
        # Final cleanup - ensure each paragraph is meaningful
        cleaned_result = []
        for p in result:
            p = p.strip()
            # Skip paragraphs that are just numbers, single words, or very short phrases
            if p and len(p) >= 50 and not re.match(r'^\d+$', p) and len(p.split()) > 5:
                # Remove excessive whitespace
                p = re.sub(r'\s+', ' ', p)
                cleaned_result.append(p)
        
        return cleaned_result
        
    def load_pdf(self, pdf_path: Path) -> List[Document]:
        """
        Load a PDF file, extract text and metadata, and return a list of Document objects.
        Uses pdfplumber for paragraph-accurate PDF processing with enhanced metadata.
        """
        logger.info(f"[INFO] Loading PDF: {pdf_path}")
        agreement_name = pdf_path.parent.name
        all_splits = []
        
        try:
            # Try using pdfplumber for enhanced paragraph extraction
            with pdfplumber.open(pdf_path) as pdf:
                    
                # Extract chapters with their structure
                chapters = self.extract_chapters_from_pdf(pdf)
                
                if not chapters:
                    logger.warning(f"[WARNING] No valid chapters found in {pdf_path.name}. Trying fallback method.")
                    raise ValueError("No valid chapters extracted")
                
                # Process each chapter
                for chapter_idx, chapter in enumerate(chapters):
                    # Skip chapters with invalid content (e.g., just signatures)
                    if not self.is_valid_pdf_content(chapter["text"]):
                        logger.debug(f"Skipping invalid chapter {chapter_idx} in {pdf_path.name}")
                        continue
                        
                    # Split the chapter text into paragraphs
                    paragraphs = self.split_into_paragraphs(chapter["text"])
                    
                    # Process each paragraph
                    for paragraph_idx, paragraph_text in enumerate(paragraphs):
                        # Skip empty or too short paragraphs
                        if not paragraph_text.strip() or len(paragraph_text.strip()) < 50:
                            continue
                            
                        # Detect language
                        try:
                            lang = detect(paragraph_text)
                        except:
                            lang = "sv"  # Default to Swedish if detection fails
                        
                        # Extract metadata
                        linked_titles, references, is_amendment = self.detect_linked_chunks(paragraph_text)
                        acronyms, definitions, target_groups = self.extract_acronyms_and_definitions(paragraph_text)
                        transitional_provisions = self.extract_transitional_provisions(paragraph_text)
                        
                        # Extract main text and footnotes
                        main_text, footnotes = self.isolate_main_text_and_footnotes(paragraph_text)
                        
                        # Skip if main text is too short after footnote removal
                        if len(main_text.strip()) < 50:
                            continue
                        
                        # Split the paragraph into chunks if it's too long
                        chunks = self.text_splitter.split_text(main_text)
                        
                        # Track character positions for chunks
                        chunk_start_char = 0
                        
                        # Create Document objects for each chunk
                        for chunk_idx, chunk in enumerate(chunks):
                            # Skip empty chunks or chunks that are too short
                            if not chunk.strip() or len(chunk.strip()) < 50:
                                continue
                                
                            # Calculate character positions
                            chunk_end_char = chunk_start_char + len(chunk)
                            
                            # Format metadata
                            paragraphs_str = ", ".join([f"{p} §" for p in sorted(chapter["paragraphs"])]) if chapter["paragraphs"] else None
                            chapter_str = f"{chapter['chapter_number']} KAP" if chapter["chapter_number"] else None
                            
                            # Create the document with metadata
                            doc = Document(
                                page_content=chunk,
                                metadata={
                                    "agreement_name": agreement_name,
                                    "title": chapter["title"],
                                    "chapter": chapter_str,
                                    "paragraph": paragraphs_str,
                                    "linked_titles": list(linked_titles),
                                    "references": list(references),
                                    "is_amendment": is_amendment,
                                    "footnotes": footnotes,
                                    "source": str(pdf_path.relative_to(self.agreements_dir)),
                                    "file_path": str(pdf_path),
                                    "page_numbers": chapter["pages"],
                                    "language": lang,
                                    "acronyms": list(acronyms),
                                    "definitions": definitions,
                                    "target_groups": list(target_groups),
                                    "transitional_provisions": transitional_provisions,
                                    "semantic_section": True,  # Flag to indicate this is a semantic chunk
                                    "chunk_start_page": chapter["chunk_start_page"],
                                    "chunk_end_page": chapter["chunk_end_page"],
                                    "chunk_start_char": chunk_start_char,
                                    "chunk_end_char": chunk_end_char,
                                    "chapter_idx": chapter_idx,
                                    "paragraph_idx": paragraph_idx,
                                    "chunk_idx": chunk_idx,
                                    "content": chunk  # Add content field for BM25 compatibility
                                }
                            )
                            all_splits.append(doc)
                            
                            # Update start position for next chunk
                            chunk_start_char = chunk_end_char
                
                if not all_splits:
                    logger.warning(f"[WARNING] No valid chunks created from {pdf_path.name} using pdfplumber. Trying fallback.")
                    raise ValueError("No valid chunks created")
                    
                logger.info(f"[INFO] Created {len(all_splits)} chunks from {pdf_path.name} using pdfplumber")
                return all_splits
                
        except Exception as e:
            logger.warning(f"[WARNING] Error using pdfplumber for {pdf_path}: {e}. Falling back to basic processing.")
            
            # If pdfplumber fails, try to fall back to a simpler approach
            try:
                from langchain_community.document_loaders import PyPDFLoader
                
                loader = PyPDFLoader(str(pdf_path))
                pages = loader.load()
                
                # Simple processing: just split each page into chunks
                for page_idx, page in enumerate(pages):
                    if not page.page_content.strip() or len(page.page_content.strip()) < 50:
                        continue
                        
                    # Skip pages that only contain signatures or short text
                    if not self.is_valid_pdf_content(page.page_content):
                        continue
                        
                    # Extract metadata
                    text = page.page_content
                    chapter_title = self.extract_chapter_title(text)
                    paragraph_number = self.extract_paragraph_number(text)
                    linked_titles, references, is_amendment = self.detect_linked_chunks(text)
                    acronyms, definitions, target_groups = self.extract_acronyms_and_definitions(text)
                    
                    # Split the page into chunks
                    chunks = self.text_splitter.split_text(text)
                    
                    # Track character positions
                    chunk_start_char = 0
                    
                    # Create Document objects for each chunk
                    for chunk_idx, chunk in enumerate(chunks):
                        # Skip empty chunks or chunks that are too short
                        if not chunk.strip() or len(chunk.strip()) < 50:
                            continue
                            
                        # Calculate character positions
                        chunk_end_char = chunk_start_char + len(chunk)
                        
                        doc = Document(
                            page_content=chunk,
                            metadata={
                                "agreement_name": agreement_name,
                                "title": chapter_title,
                                "chapter": None,
                                "paragraph": paragraph_number,
                                "linked_titles": list(linked_titles),
                                "references": list(references),
                                "is_amendment": is_amendment,
                                "footnotes": "",
                                "source": str(pdf_path.relative_to(self.agreements_dir)),
                                "file_path": str(pdf_path),
                                "page_numbers": [page.metadata.get("page", 0) + 1],
                                "language": "sv",
                                "acronyms": list(acronyms),
                                "definitions": definitions,
                                "target_groups": list(target_groups),
                                "transitional_provisions": {},
                                "semantic_section": False,  # Flag to indicate this is not a semantic chunk
                                "chunk_start_page": page.metadata.get("page", 0) + 1,
                                "chunk_end_page": page.metadata.get("page", 0) + 1,
                                "chunk_start_char": chunk_start_char,
                                "chunk_end_char": chunk_end_char,
                                "page_idx": page_idx,
                                "chunk_idx": chunk_idx,
                                "content": chunk  # Add content field for BM25 compatibility
                            }
                        )
                        all_splits.append(doc)
                        
                        # Update start position for next chunk
                        chunk_start_char = chunk_end_char
                
                if not all_splits:
                    logger.warning(f"[WARNING] No valid chunks created from {pdf_path.name} using fallback method.")
                    return []
                    
                logger.info(f"[INFO] Created {len(all_splits)} chunks from {pdf_path.name} using fallback method")
                return all_splits
                
            except Exception as e:
                logger.error(f"[ERROR] Error loading PDF {pdf_path}: {e}")
                return []


    def process_documents(self) -> Optional[FAISS]:
        if not self.agreements_dir.exists():
            logger.error(f"[ERROR] Agreements folder missing: {self.agreements_dir}")
            return

        json_path = Path(SUMMARY_JSON_PATH)
        existing_agreements = set()
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                existing_agreements = {entry["name"] for entry in existing_data.get("agreements", [])}
            except Exception as e:
                logger.warning(f"[WARNING] Could not parse summary.json: {e}")

        found_agreements = {f.name for f in self.agreements_dir.iterdir() if f.is_dir()}
        if found_agreements != existing_agreements:
            logger.info("Detected changes in agreement folders — rebuilding vectorstore.")
            self.rebuild_vectorstore(found_agreements)
        else:
            logger.info("All agreements matched. Vectorstore already built.")

        index_file = self.persist_dir / "index.faiss"
        if index_file.exists():
            return FAISS.load_local(str(self.persist_dir), self.embeddings, allow_dangerous_deserialization=True)
        else:
            logger.warning(f"[WARNING] Vectorstore missing at {index_file} — rebuilding.")
            self.rebuild_vectorstore(found_agreements)
            return FAISS.load_local(str(self.persist_dir), self.embeddings, allow_dangerous_deserialization=True)

    def rebuild_vectorstore(self, all_agreements: set):
        """
        Rebuild the vectorstore from PDF files in the agreements directory.
        Extracts text, generates chunks, creates previews, and builds the FAISS index.
        
        Args:
            all_agreements: Set of agreement names to process
        """
        logger.info("Rebuilding FAISS vectorstore from PDFs...")
        all_splits = []
        all_summaries = {}

        # Create directory if it doesn't exist
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare directory for chunks.json and other files
        chunks_path = self.persist_dir / "chunks.json"
        
        for folder in self.agreements_dir.iterdir():
            if not folder.is_dir():
                continue
                
            agreement_name = folder.name
            folder_splits = []  # Collect chunks for this agreement
            all_summaries[agreement_name] = []
            
            logger.info(f"[INFO] Processing agreement: {agreement_name}")

            for pdf_path in folder.glob("*.pdf"):
                logger.info(f"[INFO] Processing PDF: {pdf_path.name}")
                splits = self.load_pdf(pdf_path)
                
                if not splits:
                    logger.warning(f"[WARNING] No valid chunks extracted from {pdf_path.name}")
                    continue
                    
                folder_splits.extend(splits)  # Collect chunks for this agreement

                # Generate a summary of the document
                try:
                    # Use the first few chunks to generate a summary
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
                except Exception as e:
                    logger.warning(f"[WARNING] Error generating summary for {pdf_path.name}: {e}")
                    all_summaries[agreement_name].append({
                        "file": pdf_path.name,
                        "summary": f"Dokument från {agreement_name}"
                    })

            logger.info(f"[INFO] Processed {len(folder_splits)} chunks from {agreement_name}")
            all_splits.extend(folder_splits)

        # Check if we have any valid chunks
        if not all_splits:
            logger.error("No valid chunks extracted from any PDF. Vectorstore build failed.")
            return
            
        # The chunks.json file will be generated by update_chunk_preview
        
        # Generate and save chunk previews
        self.update_chunk_preview(all_splits)

        # Embed in batches for better memory management
        batch_size = 1000
        logger.info(f"[INFO] Embedding {len(all_splits)} chunks...")
        for i in range(0, len(all_splits), batch_size):
            batch = all_splits[i:i+batch_size]
            if i == 0:  # First batch - create the index
                faiss_index = FAISS.from_documents(batch, self.embeddings)
            else:  # Subsequent batches - add to existing index
                batch_index = FAISS.from_documents(batch, self.embeddings)
                faiss_index.merge_from(batch_index)
                
            # Save after each batch to prevent data loss
            faiss_index.save_local(str(self.persist_dir))
            logger.info(f"[INFO] Embedded and saved batch {i//batch_size + 1}/{(len(all_splits)-1)//batch_size + 1}")

        # Save summary data
        self.save_summary_json(all_agreements, all_summaries)
        logger.info("Vectorstore build complete with enhanced chunk extraction and previews.")


    def update_chunk_preview(self, documents: List[Document]):
        """
        Update the chunk_preview.json file with meaningful previews for each chunk.
        
        Args:
            documents: List of Document objects with chunks and metadata
        """
        preview_path = self.persist_dir / "chunk_preview.json"
        previews = {}
        
        # Create preview for each document
        for i, doc in enumerate(documents):
            # Skip documents with empty content
            if not doc.page_content or len(doc.page_content.strip()) < 50:
                logger.warning(f"[WARNING] Skipping empty or short chunk {i} when generating preview")
                continue
                
            # Generate a unique ID for the chunk
            chunk_id = f"chunk_{i}"
            
            # Extract metadata for preview
            metadata = doc.metadata
            agreement = metadata.get("agreement_name", "")
            chapter = metadata.get("chapter", "")
            title = metadata.get("title", "")
            paragraph = metadata.get("paragraph", "")
            page_numbers = metadata.get("page_numbers", [])
            
            # Create a preview of the content (first 100 characters)
            content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
            
            # Format the preview with key information
            preview_text = f"{agreement} - "
            if chapter:
                preview_text += f"{chapter} "
            if title:
                preview_text += f"{title}"
            preview_text += "\n"
            
            if paragraph:
                preview_text += f"Paragraph: {paragraph}\n"
            
            if page_numbers:
                preview_text += f"Pages: {', '.join(map(str, page_numbers))}\n\n"
            else:
                preview_text += "\n"
                
            preview_text += content_preview
            
            # Add to previews dictionary
            previews[chunk_id] = {
                "id": chunk_id,
                "agreement": agreement,
                "chapter": chapter,
                "title": title,
                "paragraph": paragraph,
                "pages": page_numbers,
                "preview": content_preview,
                "formatted_preview": preview_text,
                "content": doc.page_content  # Include full content for BM25 compatibility
            }
        
        # Save to JSON file
        with open(preview_path, "w", encoding="utf-8") as f:
            json.dump(previews, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[INFO] Created {len(previews)} chunk previews in {preview_path}")
        
        # Also save a chunks.json file for BM25 compatibility
        chunks_path = self.persist_dir / "chunks.json"
        chunks_data = []
        
        # Create a list of valid documents with their chunk IDs
        valid_docs = []
        for i, doc in enumerate(documents):
            if doc.page_content and len(doc.page_content.strip()) >= 50:
                valid_docs.append((f"chunk_{i}", doc))
        
        # Generate chunks.json data
        for chunk_id, doc in valid_docs:
            chunks_data.append({
                "id": chunk_id,
                "text": doc.page_content,
                "content": doc.page_content,  # Include both text and content fields for compatibility
                "metadata": doc.metadata
            })
        
        # Write to file
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[INFO] Saved {len(chunks_data)} chunks to {chunks_path} for BM25 retrieval")


    def save_summary_json(self, agreements: set, all_summaries: Dict[str, List[Dict[str, str]]]):
        """
        Save summary data to JSON file.
        """
        summary_path = Path(SUMMARY_JSON_PATH)
        
        # Create summary structure
        summary_data = {
            "agreements": list(agreements),
            "summaries": all_summaries
        }
        
        # Save to JSON file
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[INFO] Saved summary data to {summary_path}")


    def load_vectorstore(self) -> Optional[FAISS]:
        return self.process_documents()


if __name__ == "__main__":
    print("Running upgraded DocumentProcessor...")
    processor = DocumentProcessor()
    
    # Check if we should force rebuild
    import sys
    force_rebuild = "--force" in sys.argv
    
    if force_rebuild:
        print("Forcing vectorstore rebuild...")
        # Get the list of agreements
        agreements = {folder.name for folder in processor.agreements_dir.iterdir() if folder.is_dir()}
        # Force rebuild
        processor.rebuild_vectorstore(agreements)
    else:
        # Normal operation
        processor.load_vectorstore()
        
    print("DocumentProcessor completed.")
