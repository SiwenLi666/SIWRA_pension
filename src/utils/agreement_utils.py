"""
Utility functions for handling pension agreements
"""
import re
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# List of supported agreements
SUPPORTED_AGREEMENTS = ["PA16", "SKR2023"]

# Default agreement to use when none is specified
DEFAULT_AGREEMENT = "PA16"

# Mapping of alternative names/spellings to standardized agreement names
AGREEMENT_ALIASES = {
    "pa16": "PA16",
    "pa 16": "PA16",
    "pa-16": "PA16",
    "pensionsavtal 16": "PA16",
    "pensionsavtalet pa16": "PA16",
    "pa03": "PA03",
    "pa 03": "PA03",
    "pa-03": "PA03",
    "skr2023": "SKR2023",
    "skr 2023": "SKR2023",
    "skr-2023": "SKR2023",
    "kommunal": "SKR2023",
    "kommunala": "SKR2023",
    "kommunalt": "SKR2023",
}

def detect_agreement_name(query: str) -> Optional[str]:
    """
    Detect pension agreement name in a query string.
    
    Args:
        query: The user query string
        
    Returns:
        The detected agreement name or None if no agreement is detected
    """
    # Convert query to lowercase for case-insensitive matching
    query_lower = query.lower()
    
    # First check for exact matches of supported agreements (case-insensitive)
    for agreement in SUPPORTED_AGREEMENTS:
        if agreement.lower() in query_lower:
            logger.info(f"Detected agreement '{agreement}' in query")
            return agreement
    
    # Then check for aliases
    for alias, agreement in AGREEMENT_ALIASES.items():
        if alias in query_lower and agreement in SUPPORTED_AGREEMENTS:
            logger.info(f"Detected agreement '{agreement}' via alias '{alias}' in query")
            return agreement
    
    # No agreement detected
    logger.info(f"No agreement detected in query, defaulting to {DEFAULT_AGREEMENT}")
    return None

def get_agreement_for_query(query: str) -> str:
    """
    Get the agreement name to use for a query.
    If an agreement is detected in the query, use that.
    Otherwise, use the default agreement (PA16).
    
    Args:
        query: The user query string
        
    Returns:
        The agreement name to use
    """
    detected_agreement = detect_agreement_name(query)
    if detected_agreement:
        return detected_agreement
    
    # Log that we're using the default agreement
    logger.info(f"Using default agreement {DEFAULT_AGREEMENT} for query: '{query}'")
    return DEFAULT_AGREEMENT

def filter_documents_by_agreement(documents: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """
    Filter documents to only include those from the agreement mentioned in the query.
    If no agreement is mentioned, use the default agreement (PA16).
    
    Args:
        documents: List of document dictionaries
        query: The user query string
        
    Returns:
        Filtered list of documents
    """
    detected_agreement = detect_agreement_name(query)
    
    # If an agreement is detected, filter by that agreement
    if detected_agreement:
        agreement = detected_agreement
        
        # Filter documents to only include those from the specified agreement
        filtered_docs = []
        for doc in documents:
            metadata = doc.get("metadata", {})
            doc_agreement = metadata.get("agreement_name", "")
            
            if doc_agreement == agreement:
                filtered_docs.append(doc)
        
        # If no documents match the agreement, log a warning and return the original documents
        if not filtered_docs and documents:
            logger.warning(f"No documents found for agreement '{agreement}', returning all documents")
            return documents
        
        logger.info(f"Filtered {len(documents)} documents to {len(filtered_docs)} for agreement '{agreement}'")
        return filtered_docs
    else:
        # No agreement detected, return all documents for smart fallback processing
        logger.info(f"No agreement detected in query, returning all documents for smart fallback processing")
        return documents

def group_documents_by_agreement(documents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group documents by their agreement name.
    
    Args:
        documents: List of document dictionaries
        
    Returns:
        Dictionary mapping agreement names to lists of documents
    """
    grouped_docs = {}
    
    for doc in documents:
        metadata = doc.get("metadata", {})
        agreement = metadata.get("agreement_name", "")
        
        # Skip documents with no agreement name
        if not agreement:
            logger.warning(f"Document has no agreement_name in metadata, skipping")
            continue
        
        # Add document to the appropriate group
        if agreement not in grouped_docs:
            grouped_docs[agreement] = []
        
        grouped_docs[agreement].append(doc)
    
    # Log the grouping results
    for agreement, docs in grouped_docs.items():
        logger.info(f"Group '{agreement}' contains {len(docs)} documents")
    
    return grouped_docs

def extract_filename_from_path(file_path: str) -> str:
    """
    Extract just the filename from a full file path.
    
    Args:
        file_path: The full file path
        
    Returns:
        The filename without the path
    """
    if not file_path:
        return ""
    
    # Handle both Windows and Unix-style paths
    if '\\' in file_path:
        return file_path.split('\\')[-1]
    elif '/' in file_path:
        return file_path.split('/')[-1]
    else:
        return file_path
