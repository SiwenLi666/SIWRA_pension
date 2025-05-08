"""
Test script for verifying reference deduplication, glossary improvements, and smart fallback behavior.
"""
import os
import sys
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary modules
from src.tools.vector_retriever import VectorRetrieverTool
from src.utils.glossary_utils import is_glossary_query, get_glossary_response
from src.utils.reference_utils import deduplicate_references, format_reference, deduplicate_html_references

def test_glossary_detection():
    """Test the improved glossary query detection"""
    logger.info("Testing glossary detection...")
    
    test_queries = [
        "Vad är PA16?",
        "Vad betyder ITP1?",
        "Vad innebär AKAP-KR?",
        "Förklara tjänstepension",
        "Vad menas med förmånsbestämd pension?",
        "Vad står KPA för?",
        "Vad är definitionen av pensionsålder?",
        "PA16",  # Direct term
        "PA16?",  # Direct term with question mark
        "Vad är pa16",  # Case insensitive
        "Vad är PA 16?",  # Space instead of hyphen
        "Vad står KR för?",  # Part of a compound term
    ]
    
    results = []
    for query in test_queries:
        is_glossary, term = is_glossary_query(query)
        result = {
            "query": query,
            "is_glossary": is_glossary,
            "matched_term": term,
            "definition": get_glossary_response(term) if term else None
        }
        results.append(result)
        
        if is_glossary and term:
            logger.info(f"✅ Successfully detected glossary query: '{query}' -> '{term}'")
        else:
            logger.info(f"❌ Failed to detect glossary query: '{query}'")
    
    return results

def test_reference_deduplication():
    """Test reference deduplication functionality"""
    logger.info("Testing reference deduplication...")
    
    # Create test documents with duplicate metadata
    test_documents = [
        {
            "page_content": "This is content from document 1",
            "metadata": {
                "agreement_name": "PA16",
                "chapter": "Kapitel 3",
                "paragraph": "§5",
                "page_number": 10,
                "file_path": "/path/to/PA16.pdf"
            }
        },
        {
            "page_content": "This is content from document 2",
            "metadata": {
                "agreement_name": "PA16",
                "chapter": "Kapitel 3",
                "paragraph": "§5",
                "page_number": 11,
                "file_path": "/path/to/PA16.pdf"
            }
        },
        {
            "page_content": "This is content from document 1",  # Duplicate content
            "metadata": {
                "agreement_name": "PA16",
                "chapter": "Kapitel 3",
                "paragraph": "§5",
                "page_number": 10,
                "file_path": "/path/to/PA16.pdf"
            }
        },
        {
            "page_content": "This is content from document 3",
            "metadata": {
                "agreement_name": "SKR2023",
                "chapter": "Kapitel 2",
                "paragraph": "§10",
                "page_number": 15,
                "file_path": "/path/to/SKR2023.pdf"
            }
        }
    ]
    
    # Test document deduplication
    deduplicated_docs = deduplicate_references(test_documents)
    logger.info(f"Original documents: {len(test_documents)}, Deduplicated: {len(deduplicated_docs)}")
    
    # Test HTML reference deduplication
    references = [
        "[1] PA16 | PA16.pdf | Kapitel 3 | §5 | sida 10",
        "[2] PA16 | PA16.pdf | Kapitel 3 | §5 | sida 11",
        "[3] PA16 | PA16.pdf | Kapitel 3 | §5 | sida 10",  # Duplicate reference
        "[4] SKR2023 | SKR2023.pdf | Kapitel 2 | §10 | sida 15"
    ]
    
    deduplicated_refs = deduplicate_html_references(references)
    logger.info(f"Original references: {len(references)}, Deduplicated: {len(deduplicated_refs)}")
    
    for ref in deduplicated_refs:
        logger.info(f"Deduplicated reference: {ref}")
    
    return {
        "original_docs": len(test_documents),
        "deduplicated_docs": len(deduplicated_docs),
        "original_refs": len(references),
        "deduplicated_refs": len(deduplicated_refs),
        "deduplicated_references": deduplicated_refs
    }

def test_vector_retriever(queries: List[str]):
    """Test the vector retriever with various queries"""
    logger.info("Testing vector retriever...")
    
    retriever = VectorRetrieverTool()
    results = []
    
    for query in queries:
        logger.info(f"Testing query: '{query}'")
        state = {}
        response = retriever.run(query, state)
        
        # Extract and log the response
        answer = response.get("response", "No response generated")
        logger.info(f"Response for query '{query}':\n{answer[:200]}...")  # Show first 200 chars
        
        results.append({
            "query": query,
            "response": answer,
            "source": response.get("response_source")
        })
    
    return results

def main():
    """Run all tests"""
    logger.info("Starting tests for reference fixes...")
    
    # Test glossary detection
    glossary_results = test_glossary_detection()
    logger.info(f"Completed glossary detection tests with {sum(1 for r in glossary_results if r['is_glossary'])} successful matches")
    
    # Test reference deduplication
    dedup_results = test_reference_deduplication()
    logger.info(f"Completed reference deduplication tests")
    
    # Test vector retriever with various query types
    test_queries = [
        # Glossary queries
        "Vad är PA16?",
        "Vad står ITP för?",
        
        # Agreement-specific queries
        "Hur beräknas pensionen enligt PA16?",
        "Vad säger SKR2023 om pensionsålder?",
        
        # Multi-agreement queries (no specific agreement mentioned)
        "Hur beräknas tjänstepensionen?",
        "Vad är pensionsgrundande inkomst?",
        
        # Edge cases
        "Vad säger avtalet om föräldraledighet?",
        "När träder pensionsavtalet i kraft?"
    ]
    
    retriever_results = test_vector_retriever(test_queries)
    logger.info("Completed vector retriever tests")
    
    # Print summary
    logger.info("=== TEST SUMMARY ===")
    logger.info(f"Glossary detection: {sum(1 for r in glossary_results if r['is_glossary'])}/{len(glossary_results)} successful matches")
    logger.info(f"Reference deduplication: {dedup_results['original_docs']} -> {dedup_results['deduplicated_docs']} documents")
    logger.info(f"HTML reference deduplication: {dedup_results['original_refs']} -> {dedup_results['deduplicated_refs']} references")
    logger.info(f"Vector retriever: Tested {len(retriever_results)} queries")
    
    logger.info("Tests completed successfully!")

if __name__ == "__main__":
    main()
