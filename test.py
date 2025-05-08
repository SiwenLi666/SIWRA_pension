import sys
import json
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from src.utils.config import VECTORSTORE_DIR, OPENAI_API_KEY
from src.tools.vector_retriever import VectorRetrieverTool

# Set console encoding to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Setup
vectorstore_path = str(VECTORSTORE_DIR)
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
faiss_index = FAISS.load_local(vectorstore_path, embeddings, allow_dangerous_deserialization=True)

# Hardcoded test query
query = "Vad säger PA16 om ålderspension?"

# Perform vector search with metadata filter for PA16
results = faiss_index.similarity_search(
    query,
    k=10,  # Get more results initially
    filter={"agreement_name": "PA16"}  # Filter for PA16 documents only
)

# Further filter results to only include those about ålderspension
filtered_results = []
for doc in results:
    if "ålderspension" in doc.page_content.lower():
        filtered_results.append(doc)

# Take the top 5 results
results = filtered_results[:5]

# Show top results
print("\n=== Vector Search Results ===\n")
for i, doc in enumerate(results, 1):
    print(f"\n--- Result {i} ---")
    print(f"Agreement: {doc.metadata.get('agreement_name', 'N/A')}")
    print(f"Chapter: {doc.metadata.get('chapter', 'N/A')}")
    print(f"Paragraph: {doc.metadata.get('paragraph', 'N/A')}")
    print(f"Pages: {doc.metadata.get('page_numbers', 'N/A')}")
    print("Text Preview:\n", doc.page_content[:200], "...")

# Test the vector retriever directly with our filtered documents
print("\n\n=== Testing Vector Retriever with Reference Formatting ===\n")
try:
    # Create a vector retriever tool
    retriever_tool = VectorRetrieverTool()
    
    # Create a mock retriever that returns our filtered results
    class MockRetriever:
        def retrieve_relevant_docs(self, query, top_k=5):
            return results
    
    # Create a state dictionary with the query and our mock retriever
    state = {
        "question": query,
        "retriever": MockRetriever()
    }
    
    # Run the vector retriever tool
    result = retriever_tool.run(query, state)
    
    # Print the formatted response with references
    print("\nFormatted Response with References:")
    print(result.get("response", "No response generated"))
    
    print("\nTest completed successfully!")
except Exception as e:
    print(f"\nError testing vector retriever: {str(e)}")

