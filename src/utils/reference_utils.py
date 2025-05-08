"""
Utility functions for handling references in the pension advisor system
"""
import re
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)

# Directory for logging unanswered queries
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
UNANSWERED_QUERIES_FILE = os.path.join(LOGS_DIR, "unanswered_queries.json")

def create_document_identifier(metadata: Dict[str, Any], content_preview: str = None) -> str:
    """
    Create a unique identifier for a document based on its metadata and content.
    
    Args:
        metadata: Document metadata
        content_preview: Optional preview of content to include in the hash
        
    Returns:
        A unique identifier string
    """
    # Extract key metadata fields
    agreement = metadata.get("agreement_name", "")
    source = metadata.get("source", metadata.get("file_path", ""))
    chapter = metadata.get("chapter", "")
    paragraph = metadata.get("paragraph", "")
    
    # Handle paragraphs field which could be in different formats
    paragraphs = metadata.get("paragraphs", "")
    if isinstance(paragraphs, list):
        paragraphs = ",".join(map(str, paragraphs))
    
    # Create a string combining key metadata
    identifier_parts = [
        agreement,
        source,
        chapter,
        paragraph,
        str(paragraphs)
    ]
    
    # Add content preview to the identifier if provided
    if content_preview:
        # Use only first 100 chars to avoid excessive length
        identifier_parts.append(content_preview[:100])
    
    # Join parts and create a hash
    identifier_string = "|".join(identifier_parts)
    return hashlib.md5(identifier_string.encode()).hexdigest()

def deduplicate_references(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate documents based on their source, agreement, chapter, and paragraph.
    Combines page numbers from duplicate documents.
    
    Args:
        documents: List of document dictionaries
        
    Returns:
        Deduplicated list of documents
    """
    if not documents:
        return []
    
    # Dictionary to store unique documents by their identifier
    unique_docs = {}
    
    for doc in documents:
        metadata = doc.get("metadata", {})
        content = doc.get("page_content", doc.get("content", ""))
        
        # Create a unique identifier for this document
        doc_id = create_document_identifier(metadata, content[:50])
        
        # If this is a new unique document, add it to our dictionary
        if doc_id not in unique_docs:
            unique_docs[doc_id] = doc
            continue
        
        # If this is a duplicate, merge page numbers
        existing_doc = unique_docs[doc_id]
        existing_metadata = existing_doc.get("metadata", {})
        
        # Get page numbers from both documents
        existing_pages = get_page_numbers(existing_metadata)
        current_pages = get_page_numbers(metadata)
        
        # Combine page numbers and update the existing document
        combined_pages = list(set(existing_pages + current_pages))
        
        # Update the page numbers in the existing document
        if "page_numbers" in existing_metadata:
            existing_metadata["page_numbers"] = combined_pages
        elif "pages" in existing_metadata:
            existing_metadata["pages"] = combined_pages
        elif "page_number" in existing_metadata:
            existing_metadata["page_number"] = combined_pages
    
    logger.info(f"Deduplicated {len(documents)} documents to {len(unique_docs)} unique documents")
    return list(unique_docs.values())

def get_page_numbers(metadata: Dict[str, Any]) -> List[int]:
    """
    Extract page numbers from metadata in a consistent way, handling different formats.
    
    Args:
        metadata: Document metadata
        
    Returns:
        List of page numbers
    """
    page_numbers = []
    
    if "page_numbers" in metadata and metadata["page_numbers"]:
        if isinstance(metadata["page_numbers"], list):
            page_numbers = metadata["page_numbers"]
        else:
            page_numbers = [metadata["page_numbers"]]
    elif "pages" in metadata and metadata["pages"]:
        if isinstance(metadata["pages"], list):
            page_numbers = metadata["pages"]
        else:
            page_numbers = [metadata["pages"]]
    elif "page_number" in metadata and metadata["page_number"] is not None:
        if isinstance(metadata["page_number"], list):
            page_numbers = metadata["page_number"]
        else:
            page_numbers = [metadata["page_number"]]
    
    # Filter out None values
    page_numbers = [p for p in page_numbers if p is not None]
    
    # Convert all page numbers to integers and remove duplicates
    try:
        return list(set([int(p) if isinstance(p, str) and p.isdigit() else p for p in page_numbers]))
    except (TypeError, ValueError):
        # Handle any conversion errors by filtering out problematic values
        cleaned_numbers = []
        for p in page_numbers:
            try:
                if isinstance(p, str) and p.isdigit():
                    cleaned_numbers.append(int(p))
                elif isinstance(p, int):
                    cleaned_numbers.append(p)
            except (TypeError, ValueError):
                pass
        return list(set(cleaned_numbers))

def format_reference(ref_id: str, metadata: Dict[str, Any], page_numbers: List[int] = None) -> str:
    """
    Format a reference string following the pattern:
    AGREEMENT_NAME | FILENAME.pdf | CHAPTER | PARAGRAPH | page x, y, z
    
    Args:
        ref_id: Reference identifier (e.g., "[1]")
        metadata: Document metadata
        page_numbers: Optional list of page numbers to use (otherwise extracted from metadata)
        
    Returns:
        Formatted reference string
    """
    if not metadata:
        return f"{ref_id} Unknown source"
        
    # Extract metadata fields
    agreement = metadata.get("agreement_name", "")
    chapter = metadata.get("chapter", "")
    
    # Handle paragraph field which could be in different formats
    paragraph = metadata.get("paragraph", "")
    if not paragraph and isinstance(metadata.get("paragraphs", []), list):
        paragraphs_list = [str(p) for p in metadata.get("paragraphs", []) if p is not None]
        paragraph = ", ".join(paragraphs_list) if paragraphs_list else ""
    elif not paragraph and isinstance(metadata.get("paragraphs", ""), str):
        paragraph = metadata.get("paragraphs", "")
    
    # Get filename from path
    filename = ""
    if "file_path" in metadata and metadata["file_path"]:
        from src.utils.agreement_utils import extract_filename_from_path
        filename = extract_filename_from_path(metadata["file_path"])
    elif "source" in metadata and metadata["source"]:
        from src.utils.agreement_utils import extract_filename_from_path
        filename = extract_filename_from_path(metadata["source"])
    
    # Get page numbers if not provided
    if page_numbers is None:
        page_numbers = get_page_numbers(metadata)
    
    # Ensure page_numbers is a list and contains no None values
    if page_numbers is None:
        page_numbers = []
    elif not isinstance(page_numbers, list):
        page_numbers = [page_numbers]
    
    # Filter out None values and non-integers
    page_numbers = [p for p in page_numbers if p is not None]
    
    # Limit to top 3 pages
    limited_page_numbers = sorted(page_numbers)[:3] if page_numbers else []
    page_str = f"sida {', '.join(map(str, limited_page_numbers))}" if limited_page_numbers else ""
    
    # Build reference parts
    ref_parts = []
    
    # Always include agreement name
    if agreement:
        ref_parts.append(agreement)
    
    # Add filename if available
    if filename:
        ref_parts.append(filename)
    
    # Add chapter if available
    if chapter:
        ref_parts.append(chapter)
    
    # Add paragraph if available
    if paragraph:
        ref_parts.append(paragraph)
    
    # Add page numbers if available
    if page_str:
        ref_parts.append(page_str)
    
    # If we have no parts, add a default
    if not ref_parts:
        ref_parts.append("Unknown source")
    
    # Format the reference
    reference = f"{ref_id} {' | '.join(ref_parts)}"
    return reference

def rank_documents(documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Rank documents based on relevance to the query, using multiple ranking factors:
    - Token matching between query and content
    - Content length and quality
    - Page numbers (penalizing generic front pages)
    - Existing BM25 and vector scores if available
    
    Args:
        documents: List of document dictionaries
        query: The user query
        
    Returns:
        Ranked list of documents
    """
    if not documents:
        return []
    
    # Normalize query for token matching
    query_tokens = set(query.lower().split())
    
    # Extract key terms from query for weighted matching
    key_terms = extract_key_terms(query)
    
    # Score each document
    scored_docs = []
    for doc in documents:
        # Start with base score
        score = 0
        metadata = doc.get("metadata", {})
        content = doc.get("page_content", doc.get("content", ""))
        
        # Get page numbers
        page_numbers = get_page_numbers(metadata)
        
        # Penalize documents with only first pages (likely generic content)
        # But less aggressively than before
        if page_numbers and all(p < 3 for p in page_numbers):
            score -= 2  # Reduced penalty
        
        # Reward documents with more matching tokens from the query
        if content:
            content_lower = content.lower()
            content_tokens = set(content_lower.split())
            
            # Basic token matching
            matching_tokens = query_tokens.intersection(content_tokens)
            score += len(matching_tokens) * 2
            
            # Key term matching (weighted higher)
            for term in key_terms:
                if term.lower() in content_lower:
                    score += 3  # Higher weight for key terms
            
            # Check for exact phrase matches
            for phrase in extract_phrases(query):
                if phrase.lower() in content_lower:
                    score += len(phrase.split()) * 2  # Reward based on phrase length
        
        # Reward longer, more informative chunks but with a better curve
        if content:
            content_length = len(content.split())
            # Normalize length score: optimal length around 150-250 words
            if content_length > 50:
                if content_length < 150:
                    length_score = content_length / 150  # Ramp up to 1.0
                elif content_length < 250:
                    length_score = 1.0  # Perfect length
                else:
                    length_score = max(0.5, 1.0 - ((content_length - 250) / 500))  # Gradually decrease
                score += length_score * 3  # Higher weight for good length
        
        # Include existing scores from BM25 or vector search if available
        if "bm25_score" in metadata:
            score += metadata["bm25_score"] * 5  # Higher weight for BM25
        if "vector_score" in metadata:
            score += metadata["vector_score"] * 4
        if "hybrid_score" in metadata:
            score += metadata["hybrid_score"] * 6  # Highest weight for hybrid score
        
        # Boost documents that have agreement names matching the query
        doc_agreement = metadata.get("agreement_name", "")
        if doc_agreement and doc_agreement.lower() in query.lower():
            score += 5  # Significant boost for agreement match
        
        # Add document and its score to the list
        scored_docs.append((doc, score))
    
    # Sort documents by score (descending)
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    
    # Return just the documents
    return [doc for doc, _ in scored_docs]


def extract_key_terms(query: str) -> List[str]:
    """
    Extract key terms from a query that are likely to be important for ranking.
    
    Args:
        query: The user query
        
    Returns:
        List of key terms
    """
    # Common Swedish stopwords to exclude
    stopwords = set([
        "och", "i", "att", "det", "som", "en", "på", "är", "av", "för", "med", "till",
        "den", "har", "de", "inte", "om", "ett", "han", "men", "var", "jag", "från",
        "så", "kan", "hur", "när", "vad", "vem", "vilken", "vilka", "vart", "varför"
    ])
    
    # Extract words, filtering out stopwords and short words
    words = []
    for word in query.lower().split():
        word = word.strip(".,?!()[]{}'\"").lower()
        if word and word not in stopwords and len(word) > 2:
            words.append(word)
    
    return words


def extract_phrases(query: str) -> List[str]:
    """
    Extract meaningful phrases from a query.
    
    Args:
        query: The user query
        
    Returns:
        List of phrases
    """
    # Simple phrase extraction based on punctuation and conjunctions
    phrases = []
    
    # Split by common delimiters
    for part in re.split(r'[,.?!;:]', query):
        # Further split by conjunctions
        for subpart in re.split(r'\s+(och|eller|samt|men)\s+', part):
            subpart = subpart.strip()
            if len(subpart.split()) >= 2:  # Only phrases with at least 2 words
                phrases.append(subpart)
    
    # If no phrases found, use the whole query
    if not phrases and len(query.split()) >= 2:
        phrases.append(query)
        
    return phrases

def log_unanswered_query(query: str, documents: List[Dict[str, Any]]):
    """
    Log queries that couldn't be answered properly to help improve the system.
    
    Args:
        query: The user query that couldn't be answered
        documents: The top retrieved documents that didn't provide a good answer
    """
    try:
        # Create logs directory if it doesn't exist
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        # Prepare log entry
        log_entry = {
            "query": query,
            "timestamp": import_time().strftime("%Y-%m-%d %H:%M:%S"),
            "retrieved_chunks": []
        }
        
        # Add retrieved chunks with minimal info to avoid huge log files
        for doc in documents[:5]:  # Only log top 5 chunks
            content = doc.get("page_content", doc.get("content", ""))
            metadata = doc.get("metadata", {})
            
            log_entry["retrieved_chunks"].append({
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                "agreement": metadata.get("agreement_name", ""),
                "source": metadata.get("source", metadata.get("file_path", "")),
                "page": metadata.get("page_number", metadata.get("page", ""))
            })
        
        # Read existing log file if it exists
        existing_logs = []
        if os.path.exists(UNANSWERED_QUERIES_FILE):
            with open(UNANSWERED_QUERIES_FILE, "r", encoding="utf-8") as f:
                try:
                    existing_logs = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh
                    existing_logs = []
        
        # Append new log entry
        existing_logs.append(log_entry)
        
        # Write back to file
        with open(UNANSWERED_QUERIES_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_logs, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Logged unanswered query to {UNANSWERED_QUERIES_FILE}")
    except Exception as e:
        logger.error(f"Error logging unanswered query: {str(e)}")


def import_time():
    """Import time module only when needed to avoid circular imports"""
    import datetime
    return datetime.datetime.now()


def deduplicate_html_references(references: List[str]) -> List[str]:
    """
    Deduplicate HTML reference strings by combining references with the same content.
    
    Args:
        references: List of reference strings
        
    Returns:
        Deduplicated list of reference strings
    """
    if not references:
        return []
    
    # Dictionary to store unique references by their content (without the ref_id)
    unique_refs = {}
    
    for ref in references:
        # Split reference into ID and content
        ref_parts = ref.split(' ', 1)
        if len(ref_parts) != 2:
            continue
            
        ref_id, ref_content = ref_parts
        
        # If this content is new, add it to our dictionary
        if ref_content not in unique_refs:
            unique_refs[ref_content] = [ref_id]
        else:
            # If this is a duplicate, add the ID to the list
            unique_refs[ref_content].append(ref_id)
    
    # Rebuild references with combined IDs
    deduplicated_refs = []
    for content, ids in unique_refs.items():
        # Sort IDs numerically
        sorted_ids = sorted(ids, key=lambda x: int(x.strip('[]')))
        combined_id = ', '.join(sorted_ids)
        deduplicated_refs.append(f"{combined_id} {content}")
    
    logger.info(f"Deduplicated {len(references)} references to {len(deduplicated_refs)} unique references")
    return deduplicated_refs
