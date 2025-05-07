import logging
from typing import Dict, Any, List
from src.tools.base_tool import BaseTool

logger = logging.getLogger("vector_retriever_logger")

class VectorRetrieverTool(BaseTool):
    """Tool for retrieving information from the vector database"""
    
    def __init__(self):
        super().__init__(
            name="vector_retriever",
            description="Retrieves relevant information from the vector database"
        )
    
    def can_handle(self, question: str, state: Dict[str, Any]) -> bool:
        """
        This tool can handle any question as a fallback
        It should be used after more specific tools have failed
        """
        # This is a fallback tool, so it can handle any question
        return True
    
    def run(self, question: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve information from the vector database"""
        logger.info("Running vector retriever tool")
        
        # Get the retriever from the state if available
        retriever = state.get("retriever")
        if not retriever:
            # Create a new retriever if not available
            from src.retriever.retriever_tool import RetrieverTool
            retriever = RetrieverTool()
            state["retriever"] = retriever
        
        # Retrieve relevant documents
        try:
            documents = self._retrieve_documents(question, retriever)
            # if "ikraftträdande" in question.lower() or "ändring" in question.lower():
            #     logger.info("Detected 'ikraftträdande' or 'ändring' in question – filtering docs with is_amendment=True")
            #     documents = [doc for doc in documents if doc["metadata"].get("is_amendment") is True]

            if not documents:
                state["response"] = "Tyvärr kunde jag inte hitta någon information om det."
                logger.info(f"Returning response: {state.get('response')}")
                return state
            
            # Generate a response based on the retrieved documents
            response = self._generate_response(question, documents)
            state["response"] = response
            state["response_source"] = "vector_db"
            logger.info(f"Returning response: {state.get('response')}")
            return state
        
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            state["response"] = "Tyvärr kunde jag inte hämta information just nu."
            logger.info(f"Returning response: {state.get('response')}")
            return state
    
    def _retrieve_documents(self, question: str, retriever) -> List[Dict[str, Any]]:
        """Retrieve relevant documents from the vector database"""
        try:
            # Use the retriever to get relevant documents
            results = retriever.retrieve_relevant_docs(question, top_k=5)
            
            # Process the results
            documents = []
            for result in results:
                documents.append({
                    "content": result.page_content,
                    "metadata": result.metadata
                })
            
            return documents
            
        except Exception as e:
            logger.error(f"Error in _retrieve_documents: {str(e)}")
            return []
    
    def _generate_response(self, question: str, documents: List[Dict[str, Any]]) -> str:
        """Generate a response based on the retrieved documents using an LLM"""
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            from src.utils.config import OPENAI_API_KEY
            
            # Extract the content and metadata from the documents
            contents = []
            references = []
            
            for i, doc in enumerate(documents):
                # Extract metadata fields
                metadata = doc["metadata"]
                content = doc["page_content"]
                agreement = metadata.get("agreement_name", "")
                chapter = metadata.get("chapter", "")
                
                # Handle paragraph field which could be in different formats
                paragraph = metadata.get("paragraph", "")
                if not paragraph and isinstance(metadata.get("paragraphs", []), list):
                    paragraph = ", ".join(metadata.get("paragraphs", []))
                
                # Handle page numbers which could be in different formats
                page_numbers = []
                if "page_numbers" in metadata and metadata["page_numbers"]:
                    page_numbers = metadata["page_numbers"]
                elif "pages" in metadata and metadata["pages"]:
                    page_numbers = metadata["pages"]
                elif "page_number" in metadata:
                    if isinstance(metadata["page_number"], list):
                        page_numbers = metadata["page_number"]
                    else:
                        page_numbers = [metadata["page_number"]]
                
                # Format page numbers as string
                page = f"sida {', '.join(map(str, page_numbers))}" if page_numbers else ""

                # Create reference ID
                ref_id = f"[{i+1}]"

                # Add content with reference ID
                contents.append(f"{content} {ref_id}")

                # Build reference parts (fallback to "saknas" if missing)
                ref_parts = [
                    agreement,
                    f"kapitel: {chapter}" if chapter else "kapitel: saknas",
                    f"paragraf: {paragraph}" if paragraph else "paragraf: saknas",
                ]

                # Add page if nothing else
                if not chapter and not paragraph and page:
                    ref_parts.append(page)

                reference = f"{ref_id} {' | '.join(ref_parts)}"
                references.append(reference)
            
            combined_content = "\n\n".join(contents)
            references_text = "\n".join(references)

            # Create the LLM client
            llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=OPENAI_API_KEY)

            # Build prompt
            system_prompt = (
                "Du är en pensionsrådgivare som hjälper till att svara på frågor om pensioner och pensionsavtal. "
                "Du ska svara på svenska och vara hjälpsam, koncis och korrekt. "
                "Basera ditt svar endast på den information som finns i kontexten nedan. "
                "Inkludera referensnummer [1], [2], etc. i ditt svar för att visa vilken källa informationen kommer från. "
                "Använd referensnumren direkt efter relevant information, t.ex. 'Enligt pensionsavtalet är pensionsåldern 65 år [1].' "
                "Om du inte kan besvara frågan baserat på kontexten, säg att du inte har tillräcklig information."
            )

            query_with_context = f"""Fråga: {question}

    Kontext:
    {combined_content}

    Källor:
    {references_text}"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query_with_context)
            ]

            response = llm.invoke(messages).content
            logger.info(f"Generated response using LLM with source references")

            # Format references as HTML for proper display in frontend
            html_references = "<p><strong>Källor:</strong></p><ul>"
            for ref in references:
                ref_parts = ref.split(' ', 1)
                if len(ref_parts) == 2:
                    ref_id, ref_content = ref_parts
                    html_references += f"<li><strong>{ref_id}</strong> {ref_content}</li>"
            html_references += "</ul>"

            final_response = f"{response}\n\n{html_references}"
            return final_response

        except Exception as e:
            logger.error(f"Error in _generate_response: {str(e)}")
            return "Tyvärr kunde jag inte generera ett svar baserat på den hämtade informationen."
