import logging
from typing import Dict, Any, List, Optional, Tuple
from src.tools.base_tool import BaseTool
from src.utils.agreement_utils import filter_documents_by_agreement, get_agreement_for_query, detect_agreement_name, group_documents_by_agreement, extract_filename_from_path
from src.utils.glossary_utils import is_glossary_query, get_glossary_response

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
        
        # Check if this is a glossary query
        is_glossary, term = is_glossary_query(question)
        if is_glossary and term:
            logger.info(f"Detected glossary query for term: {term}")
            glossary_response = get_glossary_response(term)
            if glossary_response:
                state["response"] = glossary_response
                logger.info(f"Returning glossary response for term: {term}")
                return state
            else:
                logger.info(f"No glossary entry found for term: {term}, falling back to RAG")
        
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
            
            # Check if we need to use smart fallback (no agreement specified)
            if not detect_agreement_name(question):
                logger.info("No agreement specified in query, using smart fallback")
                response = self._generate_multi_agreement_response(question, documents)
            else:
                # Generate a regular response for a specific agreement
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
            # Use the retriever to get relevant documents - get more for filtering
            results = retriever.retrieve_relevant_docs(question, top_k=10)
            
            # Process the results
            documents = []
            for result in results:
                # Ensure we have content - check both page_content and metadata.content
                content = ""
                if hasattr(result, 'page_content') and result.page_content:
                    content = result.page_content
                elif hasattr(result, 'metadata') and 'content' in result.metadata and result.metadata['content']:
                    content = result.metadata['content']
                    
                # Skip documents with no content
                if not content or len(content.strip()) < 50:
                    logger.warning(f"Skipping document with missing or short content")
                    continue
                    
                documents.append({
                    "page_content": content,
                    "content": content,  # Include both for compatibility
                    "metadata": result.metadata
                })
            
            # Filter documents based on agreement mentioned in the question
            filtered_documents = filter_documents_by_agreement(documents, question)
            
            # Take the top 5 documents after filtering
            return filtered_documents[:5]
            
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
                # Use page_content if available, otherwise try content field
                content = doc.get("page_content", doc.get("content", ""))
                
                # If content is still empty, try to get it from metadata
                if not content and "content" in metadata:
                    content = metadata["content"]
                    
                # Skip this document if we still don't have content
                if not content:
                    logger.warning(f"Skipping document {i} with missing content")
                    continue
                    
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
                
                # Format page numbers as string (limit to at most 3 pages)
                limited_page_numbers = page_numbers[:3] if page_numbers else []
                page = f"sida {', '.join(map(str, limited_page_numbers))}" if limited_page_numbers else ""

                # Create reference ID
                ref_id = f"[{i+1}]"

                # Add content with reference ID
                contents.append(f"{content} {ref_id}")

                # Build reference parts with cleaner formatting
                ref_parts = []
                
                # Always include agreement name
                if agreement:
                    ref_parts.append(agreement)
                else:
                    # If no agreement name, use default
                    agreement_name = get_agreement_for_query(question)
                    ref_parts.append(agreement_name)
                    logger.warning(f"Missing agreement name in document {i}, using detected: {agreement_name}")
                
                # Get filename from path and add it to reference
                filename = ""
                if "file_path" in metadata:
                    filename = extract_filename_from_path(metadata["file_path"])
                    ref_parts.append(filename)
                elif "source" in metadata:
                    filename = extract_filename_from_path(metadata["source"])
                    ref_parts.append(filename)
                else:
                    logger.warning(f"No file path or source found for document {i}")
                
                # Format chapter and paragraph in a cleaner way
                if chapter:
                    # Remove "kapitel:" prefix for cleaner display
                    clean_chapter = chapter
                    ref_parts.append(clean_chapter)
                
                # Add paragraph if available
                if paragraph:
                    # Clean up paragraph format
                    clean_paragraph = paragraph
                    ref_parts.append(clean_paragraph)
                elif "paragraphs" in metadata and metadata["paragraphs"]:
                    # Try alternative paragraph formats
                    if isinstance(metadata["paragraphs"], list) and metadata["paragraphs"]:
                        clean_paragraph = f"{', '.join(map(str, metadata['paragraphs']))}"
                        ref_parts.append(clean_paragraph)
                    elif isinstance(metadata["paragraphs"], str) and metadata["paragraphs"]:
                        clean_paragraph = metadata["paragraphs"]
                        ref_parts.append(clean_paragraph)

                # Add page numbers if available
                if limited_page_numbers:
                    ref_parts.append(page)

                reference = f"{ref_id} {' | '.join(ref_parts)}"
                references.append(reference)
            
            combined_content = "\n\n".join(contents)
            references_text = "\n".join(references)

            # Create the LLM client
            llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=OPENAI_API_KEY)

            # Get the agreement name from the query
            agreement_name = get_agreement_for_query(question)
            
            # Build prompt
            system_prompt = (
                "Du är en pensionsrådgivare som hjälper till att svara på frågor om pensioner och pensionsavtal. "
                "Du ska svara på svenska och vara hjälpsam, koncis och korrekt. "
                f"Frågan handlar om pensionsavtalet {agreement_name}. "
                "Basera ditt svar endast på den information som finns i kontexten nedan. "
                "Inkludera referensnummer [1], [2], etc. i ditt svar för att visa vilken källa informationen kommer från. "
                "Använd referensnumren direkt efter relevant information, t.ex. 'Enligt pensionsavtalet är pensionsåldern 65 år [1].' "
                "Använd endast referensnummer för information som faktiskt finns i kontexten. "
                "Var noga med att endast referera till information som kommer från samma pensionsavtal som frågan handlar om. "
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
            
    def _generate_multi_agreement_response(self, question: str, documents: List[Dict[str, Any]]) -> str:
        """Generate a response with information grouped by agreement"""
        try:
            # Group documents by agreement
            grouped_docs = group_documents_by_agreement(documents)
            
            if not grouped_docs:
                logger.warning("No valid grouped documents found")
                return "Jag kunde inte hitta relevant information i tillgängliga avtal."
            
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            from src.utils.config import OPENAI_API_KEY
            
            # Create the LLM client
            llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=OPENAI_API_KEY)
            
            # Process each agreement group separately
            agreement_responses = {}
            all_references = []
            ref_counter = 1
            
            for agreement, docs in grouped_docs.items():
                # Extract content and create references for this agreement
                contents = []
                references = []
                
                for i, doc in enumerate(docs):
                    # Extract metadata fields
                    metadata = doc["metadata"]
                    # Use page_content if available, otherwise try content field
                    content = doc.get("page_content", doc.get("content", ""))
                    
                    # If content is still empty, try to get it from metadata
                    if not content and "content" in metadata:
                        content = metadata["content"]
                        
                    # Skip this document if we still don't have content
                    if not content:
                        logger.warning(f"Skipping document {i} with missing content")
                        continue
                    
                    # Create reference ID
                    ref_id = f"[{ref_counter}]"
                    ref_counter += 1
                    
                    # Add content with reference ID
                    contents.append(f"{content} {ref_id}")
                    
                    # Get filename from path
                    filename = ""
                    if "file_path" in metadata:
                        filename = extract_filename_from_path(metadata["file_path"])
                    elif "source" in metadata:
                        filename = extract_filename_from_path(metadata["source"])
                    
                    # Format page numbers
                    page_numbers = []
                    if "page_numbers" in metadata and metadata["page_numbers"]:
                        page_numbers = metadata["page_numbers"][:3]  # Limit to 3 pages
                    elif "pages" in metadata and metadata["pages"]:
                        page_numbers = metadata["pages"][:3]
                    elif "page_number" in metadata:
                        if isinstance(metadata["page_number"], list):
                            page_numbers = metadata["page_number"][:3]
                        else:
                            page_numbers = [metadata["page_number"]]
                    
                    page_str = f"sida {', '.join(map(str, page_numbers))}" if page_numbers else ""
                    
                    # Build reference parts
                    ref_parts = [agreement]
                    
                    # Add filename if available
                    if filename:
                        ref_parts.append(filename)
                    
                    # Add chapter if available
                    chapter = metadata.get("chapter", "")
                    if chapter:
                        ref_parts.append(chapter)
                    
                    # Add paragraph if available
                    paragraph = metadata.get("paragraph", "")
                    if paragraph:
                        ref_parts.append(paragraph)
                    elif "paragraphs" in metadata and metadata["paragraphs"]:
                        if isinstance(metadata["paragraphs"], list) and metadata["paragraphs"]:
                            ref_parts.append(f"{', '.join(map(str, metadata['paragraphs']))}")
                        elif isinstance(metadata["paragraphs"], str) and metadata["paragraphs"]:
                            ref_parts.append(metadata["paragraphs"])
                    
                    # Add page numbers if available
                    if page_str:
                        ref_parts.append(page_str)
                    
                    reference = f"{ref_id} {' | '.join(ref_parts)}"
                    references.append(reference)
                    all_references.append(reference)
                
                # Skip if no content for this agreement
                if not contents:
                    continue
                    
                # Build prompt for this agreement
                combined_content = "\n\n".join(contents)
                
                system_prompt = (
                    "Du är en pensionsrådgivare som hjälper till att svara på frågor om pensioner och pensionsavtal. "
                    "Du ska svara på svenska och vara hjälpsam, koncis och korrekt. "
                    f"Frågan handlar om pensionsavtalet {agreement}. "
                    "Basera ditt svar endast på den information som finns i kontexten nedan. "
                    "Inkludera referensnummer [1], [2], etc. i ditt svar för att visa vilken källa informationen kommer från. "
                    "Använd referensnumren direkt efter relevant information, t.ex. 'Enligt pensionsavtalet är pensionsåldern 65 år [1].' "
                    "Använd endast referensnummer för information som faktiskt finns i kontexten. "
                    "Om du inte kan besvara frågan baserat på kontexten, säg att du inte har tillräcklig information."
                )
                
                query_with_context = f"""Fråga: {question}

Kontext:
{combined_content}"""
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=query_with_context)
                ]
                
                # Generate response for this agreement
                agreement_response = llm.invoke(messages).content
                agreement_responses[agreement] = agreement_response
            
            # If no valid responses, return fallback message
            if not agreement_responses:
                return "Jag kunde inte hitta relevant information i tillgängliga avtal."
            
            # Combine responses from different agreements
            final_response = "Jag hittade information om din fråga i flera olika pensionsavtal:\n\n"
            
            for agreement, response in agreement_responses.items():
                final_response += f"## {agreement}\n{response}\n\n"
            
            # Format references as HTML
            html_references = "<p><strong>Källor:</strong></p><ul>"
            for ref in all_references:
                ref_parts = ref.split(' ', 1)
                if len(ref_parts) == 2:
                    ref_id, ref_content = ref_parts
                    html_references += f"<li><strong>{ref_id}</strong> {ref_content}</li>"
            html_references += "</ul>"
            
            final_response += f"\n\n{html_references}"
            return final_response
            
        except Exception as e:
            logger.error(f"Error in _generate_multi_agreement_response: {str(e)}")
            return "Tyvärr kunde jag inte generera ett svar baserat på den hämtade informationen."
