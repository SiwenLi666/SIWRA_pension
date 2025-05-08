"""
Test script for verifying reference summary formatting improvements.
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary modules
from src.tools.vector_retriever import VectorRetrieverTool

def test_vector_retriever(queries: List[str]):
    """Test the vector retriever with various queries"""
    logger.info("Testing vector retriever with reference summary improvements...")
    
    retriever = VectorRetrieverTool()
    results = []
    
    for query in queries:
        logger.info(f"Testing query: '{query}'")
        state = {}
        response = retriever.run(query, state)
        
        # Extract and log the response
        answer = response.get("response", "No response generated")
        source = response.get("response_source", "unknown")
        
        logger.info(f"Response source: {source}")
        logger.info(f"Response for query '{query}':\n{answer[:200]}...")  # Show first 200 chars
        
        results.append({
            "query": query,
            "response": answer,
            "source": source
        })
    
    return results

def main():
    """Run tests for improved retrieval and answer generation logic"""
    logger.info("Starting tests for improved retrieval and answer generation logic...")
    
    # Test queries as specified in the requirements
    test_queries = [
        # Original test queries
        "Vad är PA16 och när träder ändringarna i kraft?",
        "Vilka ändringar träder i kraft 1 januari 2025?",
        "Hur länge kan en yrkesofficerare skjuta upp sin pension?",
        "Vad står AKAP-KR för?",
        
        # New test queries from the requirements
        "Vilka övergångsbestämmelser gäller för 1965 års födda?",
        "När träder ändringarna i AKAP-KR i kraft?",
        "Vilka är de viktigaste skillnaderna mellan PA16 och SKR2023?"
    ]
    
    # Run the tests
    results = test_vector_retriever(test_queries)
    
    # Print summary
    logger.info("=== TEST SUMMARY ===")
    for i, result in enumerate(results):
        query = result["query"]
        source = result["source"]
        response_preview = result["response"][:150] + "..." if len(result["response"]) > 150 else result["response"]
        
        logger.info(f"Query {i+1}: '{query}'")
        logger.info(f"Source: {source}")
        logger.info(f"Response preview: {response_preview}")
        logger.info("-" * 50)
    
    # Check if unanswered queries were logged
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "unanswered_queries.json")
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                unanswered_queries = json.load(f)
                logger.info(f"Found {len(unanswered_queries)} logged unanswered queries")
        except Exception as e:
            logger.error(f"Error reading unanswered queries log: {str(e)}")
    
    logger.info("Tests completed successfully!")

if __name__ == "__main__":
    main()
