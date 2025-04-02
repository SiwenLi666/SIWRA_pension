from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from src.utils.config import VECTORSTORE_DIR, OPENAI_API_KEY

# Setup
vectorstore_path = str(VECTORSTORE_DIR)
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
faiss_index = FAISS.load_local(vectorstore_path, embeddings, allow_dangerous_deserialization=True)

# Hardcoded test query
query = """ Vilka regler finns för efterlevandepension i Pensionsavtal 2016 (PA16)?

FAISS sökfrågor:
1. `regler för efterlevandepension i PA16`
2. `efterlevandepension i Pensionsavtal 2016`
3. `bestämmelser om efterlevandepension i Pensionsavtal 2016`
4. `vad säger PA16 om efterlevandepension`
5. `efterlevandepension regelverk i Pensionsavtal 2016`

Metadata: `agreement_name="PA16"`


"""

# Perform vector search
results = faiss_index.similarity_search(query, k=5)

# Show top results
for i, doc in enumerate(results, 1):
    print(f"\n--- Result {i} ---")
    print(f"Score (not shown here directly)")
    print("Metadata:", doc.metadata)
    print("Text Preview:\n", doc.page_content[:400])
