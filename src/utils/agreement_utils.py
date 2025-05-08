"""
Utility functions for handling pension agreements
"""
import re
import logging
import os
from typing import Optional, List, Dict, Any, Tuple, Set

logger = logging.getLogger(__name__)

# List of supported agreements
SUPPORTED_AGREEMENTS = ["PA16", "SKR2023"]

# Default agreement to use when none is specified
DEFAULT_AGREEMENT = "PA16"

# Mapping of alternative names/spellings to standardized agreement names
AGREEMENT_ALIASES = {
    # PA16 variations
    "pa16": "PA16",
    "pa 16": "PA16",
    "pa-16": "PA16",
    "pensionsavtal 16": "PA16",
    "pensionsavtalet pa16": "PA16",
    "statligt pensionsavtal": "PA16",
    "statliga pensionsavtalet": "PA16",
    "statens pensionsavtal": "PA16",
    
    # PA03 variations (historical)
    "pa03": "PA03",
    "pa 03": "PA03",
    "pa-03": "PA03",
    
    # SKR2023 variations
    "skr2023": "SKR2023",
    "skr 2023": "SKR2023",
    "skr-2023": "SKR2023",
    "kommunal": "SKR2023",
    "kommunala": "SKR2023",
    "kommunalt": "SKR2023",
    "kommun": "SKR2023",
    "region": "SKR2023",
    "kommuner": "SKR2023",
    "regioner": "SKR2023",
    
    # Acronyms and specific terms that imply agreements
    "akap-kr": "SKR2023",
    "akap kr": "SKR2023",
    "akapkr": "SKR2023",
    "akap": "SKR2023",
    "avdelning 2": "PA16",
    "avdelning 1": "PA16",
    "avd 1": "PA16",
    "avd 2": "PA16",
    "avd. 1": "PA16",
    "avd. 2": "PA16",
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
        # Use word boundary check to avoid partial matches
        pattern = r'\b' + re.escape(agreement.lower()) + r'\b'
        if re.search(pattern, query_lower):
            logger.info(f"Detected agreement '{agreement}' in query")
            return agreement
    
    # Then check for aliases with word boundaries
    for alias, agreement in AGREEMENT_ALIASES.items():
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, query_lower) and agreement in SUPPORTED_AGREEMENTS:
            logger.info(f"Detected agreement '{agreement}' via alias '{alias}' in query")
            return agreement
    
    # Check for semantic indicators (terms that strongly imply an agreement)
    if any(term in query_lower for term in ["yrkesofficer", "officer", "militär", "försvarsmakten"]):
        logger.info(f"Detected semantic indicator for PA16 in query")
        return "PA16"
    
    if any(term in query_lower for term in ["kommun", "region", "landsting", "kommunanställd"]):
        logger.info(f"Detected semantic indicator for SKR2023 in query")
        return "SKR2023"
    
    # No agreement detected
    logger.info("No agreement detected in query")
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

def filter_documents_by_agreement(documents: List[Dict[str, Any]], query: str, strict_mode: bool = False) -> List[Dict[str, Any]]:
    """
    Filter documents to only include those from the agreement mentioned in the query.
    If no agreement is mentioned and strict_mode is False, return all documents.
    
    Args:
        documents: List of document dictionaries
        query: The user query string
        strict_mode: If True, always filter by an agreement (using default if none detected)
        
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
        # No agreement detected
        if strict_mode:
            # In strict mode, use the default agreement
            agreement = DEFAULT_AGREEMENT
            filtered_docs = []
            for doc in documents:
                metadata = doc.get("metadata", {})
                doc_agreement = metadata.get("agreement_name", "")
                
                if doc_agreement == agreement:
                    filtered_docs.append(doc)
            
            logger.info(f"No agreement detected, strict mode enabled. Filtered to {len(filtered_docs)} for default agreement '{agreement}'")
            return filtered_docs
        else:
            # In non-strict mode, return all documents for smart fallback processing
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

def get_relevant_agreements_for_query(query: str) -> List[str]:
    """
    Get a list of agreements that might be relevant to the query,
    based on both explicit mentions and semantic relationships.
    
    Args:
        query: The user query string
        
    Returns:
        List of potentially relevant agreement names
    """
    relevant_agreements = set()
    
    # First check for explicitly mentioned agreement
    detected_agreement = detect_agreement_name(query)
    if detected_agreement:
        relevant_agreements.add(detected_agreement)
    
    # Check for semantic relationships
    query_lower = query.lower()
    
    # Terms related to retirement age, pensions, etc. are relevant to all agreements
    general_pension_terms = [
        "pension", "pensionsålder", "förmånsbestämd", "avgiftsbestämd",
        "tjänstepension", "ålderspension", "efterlevandeskydd", "premiebestämd"
    ]
    
    if any(term in query_lower for term in general_pension_terms):
        # If query is about general pension concepts, include all agreements
        relevant_agreements.update(SUPPORTED_AGREEMENTS)
    
    # If no agreements found through any method, include all supported agreements
    if not relevant_agreements:
        relevant_agreements.update(SUPPORTED_AGREEMENTS)
    
    return list(relevant_agreements)
