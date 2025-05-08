import logging
import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from src.tools.base_tool import BaseTool
from src.utils.agreement_utils import filter_documents_by_agreement, get_agreement_for_query, detect_agreement_name, group_documents_by_agreement, extract_filename_from_path, get_relevant_agreements_for_query
from src.utils.glossary_utils import is_glossary_query, get_glossary_response
from src.utils.reference_utils import deduplicate_references, format_reference, rank_documents, deduplicate_html_references, log_unanswered_query

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
        """Retrieve information from the vector database with improved agreement handling"""
        logger.info("Running vector retriever tool")
        
        # Check if this is a glossary query
        is_glossary, term = is_glossary_query(question)
        if is_glossary and term:
            logger.info(f"Detected glossary query for term: {term}")
            glossary_response = get_glossary_response(term)
            if glossary_response:
                # For pure glossary queries, return immediately with no references
                if question.lower().strip() in [term.lower(), term.lower() + "?", f"vad är {term.lower()}?", 
                                                f"vad står {term.lower()} för?", f"vad betyder {term.lower()}?"]:
                    logger.info(f"Pure glossary query detected, bypassing retrieval for term: {term}")
                    state["response"] = glossary_response
                    state["response_source"] = "glossary"
                    return state
                
                # For mixed queries (glossary + other information), continue with retrieval
                # but keep the glossary response to prepend later
                state["glossary_response"] = glossary_response
                logger.info(f"Mixed query with glossary term: {term}, continuing with retrieval")
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
            
            # Special handling for amendment/change-related queries
            if any(term in question.lower() for term in ["ikraftträdande", "ändring", "ändringar", "träder i kraft", "gäller från"]):
                logger.info("Detected amendment/change-related query – prioritizing docs with is_amendment=True")
                # Don't filter out completely, just boost amendment docs in ranking
                for doc in documents:
                    if doc["metadata"].get("is_amendment") is True:
                        # Add a boost to the metadata for ranking
                        doc["metadata"]["amendment_boost"] = True

            # If no documents found, log the query and return a more helpful message
            if not documents:
                logger.warning("No documents found for query: " + question)
                # Log unanswered query for future improvement
                log_unanswered_query(question, [])
                
                # Get relevant agreements that should have been searched
                relevant_agreements = get_relevant_agreements_for_query(question)
                agreements_str = ", ".join(relevant_agreements)
                
                # Return a more helpful message mentioning which agreements were searched
                state["response"] = f"Jag sökte i följande pensionsavtal: {agreements_str}, men kunde tyvärr inte hitta specifik information om din fråga. Kan du omformulera frågan eller vara mer specifik?"
                state["response_source"] = "vector_db"
                logger.info(f"Returning no-results response with agreements searched: {agreements_str}")
                return state
            
            # Check if we have a glossary response to prepend
            glossary_prefix = ""
            if state.get("glossary_response"):
                glossary_prefix = state["glossary_response"] + "\n\nJag hittade även följande information i pensionsavtalen:\n\n"
                logger.info("Adding glossary response as prefix")
            
            # Determine if we should use multi-agreement response
            # Now based on document analysis, not just query detection
            agreement_groups = group_documents_by_agreement(documents)
            
            if len(agreement_groups) > 1 or not detect_agreement_name(question):
                logger.info(f"Using multi-agreement response with {len(agreement_groups)} agreement groups")
                response = self._generate_multi_agreement_response(question, documents)
            else:
                # Generate a regular response for a single agreement
                agreement = list(agreement_groups.keys())[0]
                logger.info(f"Using single agreement response for {agreement}")
                response = self._generate_response(question, documents)
            
            # If response is empty after generation, log and return a helpful message
            if not response:
                logger.warning("Empty response generated despite having documents")
                # Log the query for future improvement
                log_unanswered_query(question, documents)
                
                # Get the agreements that were searched
                agreements = list(group_documents_by_agreement(documents).keys())
                agreements_str = ", ".join(agreements)
                
                # Return a more helpful message
                state["response"] = f"Jag hittade viss information i {agreements_str}, men kunde inte sammanställa ett tydligt svar på din specifika fråga. Kan du omformulera frågan eller vara mer specifik?"
                state["response_source"] = "vector_db"
                return state
            
            # Combine glossary response (if any) with retrieval response
            if glossary_prefix and response:
                final_response = glossary_prefix + response
            else:
                final_response = response
                
            state["response"] = final_response
            state["response_source"] = "vector_db"
            logger.info(f"Returning response with {len(documents)} relevant documents")
            return state
        
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            state["response"] = "Jag kunde tyvärr inte hämta information just nu på grund av ett tekniskt problem. Vänligen försök igen om en stund."
            logger.info(f"Returning error response: {str(e)}")
            return state
    
    def _retrieve_documents(self, question: str, retriever) -> List[Dict[str, Any]]:
        """Retrieve relevant documents from the vector database with improved agreement filtering"""
        try:
            # Determine if we should use strict filtering based on agreement detection
            detected_agreement = detect_agreement_name(question)
            strict_mode = detected_agreement is not None
            
            # Get more documents for better filtering and ranking
            results = retriever.retrieve_relevant_docs(question, top_k=20)  # Increased from 15 to 20
            
            # Process the results
            documents = []
            for result in results:
                try:
                    # Ensure we have content - check both page_content and metadata.content
                    content = ""
                    if hasattr(result, 'page_content') and result.page_content:
                        content = result.page_content
                    elif hasattr(result, 'metadata') and 'content' in result.metadata and result.metadata['content']:
                        content = result.metadata['content']
                        
                    # More lenient content filtering - accept shorter content
                    if not content or len(content.strip()) < 30:  # Reduced from 50 to 30
                        logger.warning(f"Skipping document with missing or very short content")
                        continue
                    
                    # Ensure metadata is a dictionary
                    metadata = {}
                    if hasattr(result, 'metadata') and result.metadata:
                        metadata = result.metadata
                    
                    documents.append({
                        "page_content": content,
                        "content": content,  # Include both for compatibility
                        "metadata": metadata
                    })
                except Exception as doc_error:
                    logger.warning(f"Error processing document: {str(doc_error)}")
                    continue
            
            # If no valid documents were found, return empty list
            if not documents:
                logger.warning("No valid documents found in retrieval results")
                return []
            
            # Filter documents based on agreement mentioned in the question
            # Use strict mode only when an agreement is explicitly mentioned
            try:
                filtered_documents = filter_documents_by_agreement(documents, question, strict_mode=strict_mode)
            except Exception as filter_error:
                logger.warning(f"Error filtering documents: {str(filter_error)}")
                filtered_documents = documents
            
            # If strict filtering returned very few results, fall back to non-strict
            if strict_mode and len(filtered_documents) < 3 and len(documents) > 5:
                logger.info(f"Strict filtering returned only {len(filtered_documents)} documents, falling back to non-strict")
                try:
                    filtered_documents = filter_documents_by_agreement(documents, question, strict_mode=False)
                except Exception:
                    filtered_documents = documents
            
            # Rank documents based on relevance to the query with improved scoring
            try:
                ranked_documents = rank_documents(filtered_documents, question)
            except Exception as rank_error:
                logger.warning(f"Error ranking documents: {str(rank_error)}")
                ranked_documents = filtered_documents
            
            # Deduplicate documents to avoid repetition
            try:
                deduplicated_documents = deduplicate_references(ranked_documents)
            except Exception as dedup_error:
                logger.warning(f"Error deduplicating documents: {str(dedup_error)}")
                deduplicated_documents = ranked_documents
            
            # Keep more documents for better coverage
            top_documents = deduplicated_documents[:10]  # Increased from 7 to 10
            
            # Log if we have very few documents after all processing
            if len(top_documents) < 3 and len(documents) > 5:
                logger.warning(f"Only {len(top_documents)} documents after filtering and ranking, might need to adjust thresholds")
            
            return top_documents
            
        except Exception as e:
            logger.error(f"Error in _retrieve_documents: {str(e)}")
            return []
    
    def _generate_response(self, question: str, documents: List[Dict[str, Any]]) -> str:
        """Generate a response based on the retrieved documents using an LLM with improved handling of partial information"""
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            from src.utils.config import OPENAI_API_KEY
            
            # If no documents, return empty string (handled by the caller)
            if not documents:
                logger.warning("No documents to generate response from")
                return ""
            
            # More lenient filtering - accept shorter content
            filtered_docs = []
            for doc in documents:
                content = doc.get("page_content", doc.get("content", ""))
                # Reduced minimum length from 50 to 30 characters
                if not content or len(content.strip()) < 30 or content == "...":
                    continue
                filtered_docs.append(doc)
            
            # If no documents after filtering, return empty string (handled by the caller)
            if not filtered_docs:
                logger.warning("No relevant documents after filtering")
                return ""
            
            # Extract the content and metadata from the documents
            contents = []
            references = []
            
            for i, doc in enumerate(filtered_docs):
                # Extract metadata fields
                metadata = doc["metadata"]
                # Use page_content if available, otherwise try content field
                content = doc.get("page_content", doc.get("content", ""))
                
                # If content is still empty, try to get it from metadata
                if not content and "content" in metadata:
                    content = metadata["content"]
                    
                # Skip this document if we still don't have content
                # Reduced minimum length from 50 to 30 characters
                if not content or len(content.strip()) < 30:
                    logger.warning(f"Skipping document {i} with missing or too short content")
                    continue
                
                # Create reference ID
                ref_id = f"[{i+1}]"

                # Add content with reference ID
                contents.append(f"{content} {ref_id}")

                # Use the reference_utils format_reference function for consistent formatting
                reference = format_reference(ref_id, metadata)
                references.append(reference)
            
            # If no valid contents after processing, return empty string (handled by the caller)
            if not contents:
                logger.warning("No valid contents after processing documents")
                return ""
                
            combined_content = "\n\n".join(contents)
            references_text = "\n".join(references)

            # Create the LLM client
            llm = ChatOpenAI(model="gpt-4", temperature=0.2, openai_api_key=OPENAI_API_KEY)

            # Get the agreement name from the query
            agreement_name = get_agreement_for_query(question)
            
            # Build improved prompt that encourages using partial information
            system_prompt = (
                "Du är en pensionsrådgivare som hjälper till att svara på frågor om pensioner och pensionsavtal. "
                "Du ska svara på svenska och vara hjälpsam, koncis och korrekt. "
                f"Frågan handlar om pensionsavtalet {agreement_name}. "
                "Basera ditt svar på den information som finns i kontexten nedan. "
                "Inkludera referensnummer [1], [2], etc. i ditt svar för att visa vilken källa informationen kommer från. "
                "Använd referensnumren direkt efter relevant information, t.ex. 'Enligt pensionsavtalet är pensionsåldern 65 år [1].' "
                "Använd endast referensnummer för information som faktiskt finns i kontexten. "
                "Var noga med att endast referera till information som kommer från samma pensionsavtal som frågan handlar om. "
                "VIKTIGT: Om du bara hittar delvis relevant information, använd den ändå och förklara vad du vet och vad som saknas. "
                "Till exempel: 'Kontexten nämner förändringar i pensionsavtalet, men anger inte exakt datum för ikraftträdande [1].' "
                "Undvik att be om ursäkt eller säga att du inte kan svara om det finns någon relevant information i kontexten. "
                "Om det inte finns NÅGON relevant information alls, skriv ENDAST 'INGEN_RELEVANT_INFORMATION' och inget annat."
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
            
            # Check if the response indicates no relevant information
            if "INGEN_RELEVANT_INFORMATION" in response:
                logger.info("No relevant information in response, returning empty string")
                return ""

            # Post-process to remove apologetic language
            response = self._remove_apologetic_language(response)

            # Deduplicate references before formatting HTML
            deduplicated_refs = deduplicate_html_references(references)
            
            # Format references as HTML for proper display in frontend
            html_references = "<p><strong>Källor:</strong></p><ul>"
            for ref in deduplicated_refs:
                ref_parts = ref.split(' ', 1)
                if len(ref_parts) == 2:
                    ref_id, ref_content = ref_parts
                    html_references += f"<li><strong>{ref_id}</strong> {ref_content}</li>"
            html_references += "</ul>"

            final_response = f"{response}\n\n{html_references}"
            return final_response

        except Exception as e:
            logger.error(f"Error in _generate_response: {str(e)}")
            return "Jag kunde inte generera ett fullständigt svar baserat på den tillgängliga informationen. Vänligen omformulera din fråga eller var mer specifik."
            
    def _remove_apologetic_language(self, text: str) -> str:
        """
        Remove apologetic language from responses to make them more assertive and helpful.
        
        Args:
            text: The response text to process
            
        Returns:
            Processed text with apologetic language removed
        """
        # Phrases to remove or replace
        apologetic_phrases = [
            (r"\btyvärr\b", ""),
            (r"\bbeklagligen\b", ""),
            (r"\bbeklagligtvis\b", ""),
            (r"\bkan inte svara\b", "har inte tillräcklig information för att svara fullständigt"),
            (r"\bkan jag inte svara\b", "har jag inte tillräcklig information för att svara fullständigt"),
            (r"\bkan inte besvara\b", "har inte tillräcklig information för att besvara"),
            (r"\bkan jag inte besvara\b", "har jag inte tillräcklig information för att besvara"),
            (r"\bkan inte ge\b", "har inte tillräcklig information för att ge"),
            (r"\bkan jag inte ge\b", "har jag inte tillräcklig information för att ge"),
            (r"\bber om ursäkt\b", ""),
            (r"\bursäkta\b", ""),
            (r"\bframgår inte\b", "nämns inte specifikt"),
            (r"\bspecificeras inte\b", "anges inte i detalj"),
            (r"\binte tillräckligt med information\b", "begränsad information"),
            (r"\bsaknar information\b", "har begränsad information"),
            (r"\binte tillgång till\b", "begränsad information om"),
        ]
        
        # Apply replacements
        processed_text = text
        for pattern, replacement in apologetic_phrases:
            processed_text = re.sub(pattern, replacement, processed_text, flags=re.IGNORECASE)
        
        # Remove double spaces and trim
        processed_text = re.sub(r"\s+", " ", processed_text).strip()
        
        return processed_text
    
    def _generate_multi_agreement_response(self, question: str, documents: List[Dict[str, Any]]) -> str:
        """Generate a response with information grouped by agreement, with improved handling of partial information"""
        try:
            # Group documents by agreement
            grouped_docs = group_documents_by_agreement(documents)
            
            # If no agreements found or all documents were filtered out
            if not grouped_docs:
                # Check if a specific agreement was mentioned but not found
                detected_agreement = detect_agreement_name(question)
                if detected_agreement:
                    logger.warning(f"Agreement '{detected_agreement}' mentioned but no documents found")
                    return f"Jag sökte efter information om {detected_agreement} men kunde inte hitta något som besvarar din specifika fråga."
                
                # Get all relevant agreements for the query
                relevant_agreements = get_relevant_agreements_for_query(question)
                agreements_str = ", ".join(relevant_agreements)
                
                # Return a more helpful message mentioning which agreements were searched
                logger.warning(f"No valid grouped documents found, searched agreements: {agreements_str}")
                return f"Jag sökte i följande pensionsavtal: {agreements_str}, men kunde inte hitta specifik information som besvarar din fråga."
            
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
                    # More lenient filtering - accept shorter content
                    if not content or len(content.strip()) < 30:  # Reduced from 50 to 30
                        logger.warning(f"Skipping document {i} with missing or very short content")
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
                    
                    # Use the reference_utils format_reference function for consistent formatting
                    reference = format_reference(ref_id, metadata, page_numbers)
                    references.append(reference)
                    all_references.append(reference)
                
                # More lenient filtering - accept shorter content
                if not contents or all(len(c.strip()) < 30 or "..." in c for c in contents):  # Reduced from 50 to 30
                    logger.warning(f"No relevant content for agreement: {agreement}, skipping")
                    continue
                    
                # Build prompt for this agreement with improved handling of partial information
                combined_content = "\n\n".join(contents)
                
                system_prompt = (
                    "Du är en pensionsrådgivare som hjälper till att svara på frågor om pensioner och pensionsavtal. "
                    "Du ska svara på svenska och vara hjälpsam, koncis och korrekt. "
                    f"Frågan handlar om pensionsavtalet {agreement}. "
                    "Basera ditt svar på den information som finns i kontexten nedan. "
                    "Inkludera referensnummer [1], [2], etc. i ditt svar för att visa vilken källa informationen kommer från. "
                    "Använd referensnumren direkt efter relevant information, t.ex. 'Enligt pensionsavtalet är pensionsåldern 65 år [1].' "
                    "Använd endast referensnummer för information som faktiskt finns i kontexten. "
                    "VIKTIGT: Om du bara hittar delvis relevant information, använd den ändå och förklara vad du vet och vad som saknas. "
                    "Till exempel: 'Kontexten nämner förändringar i pensionsavtalet, men anger inte exakt datum för ikraftträdande [1].' "
                    "Undvik att be om ursäkt eller säga att du inte kan svara om det finns någon relevant information i kontexten. "
                    "Om det inte finns NÅGON relevant information alls, skriv ENDAST 'INGEN_RELEVANT_INFORMATION' och inget annat."
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
                
                # Check if the response indicates no relevant information
                if "INGEN_RELEVANT_INFORMATION" in agreement_response:
                    logger.info(f"No relevant information for agreement: {agreement}, skipping")
                    continue
                    
                # Post-process to remove apologetic language
                agreement_response = self._remove_apologetic_language(agreement_response)
                
                # Add valid response to the dictionary
                agreement_responses[agreement] = agreement_response
            
            # If no valid responses after filtering, return a helpful message
            if not agreement_responses:
                # Get all relevant agreements for the query
                relevant_agreements = get_relevant_agreements_for_query(question)
                agreements_str = ", ".join(relevant_agreements)
                
                # Log the query for future improvement
                log_unanswered_query(question, documents)
                
                return f"Jag sökte i följande pensionsavtal: {agreements_str}, men kunde inte hitta tillräckligt specifik information som besvarar din fråga. Kan du omformulera eller vara mer specifik?"
            
            # Combine responses from different agreements with double line breaks for better visual separation
            final_response = "Jag hittade information om din fråga i flera olika pensionsavtal:\n\n"
            
            for agreement, response in agreement_responses.items():
                final_response += f"## {agreement}\n{response}\n\n"
            
            # Deduplicate references before formatting HTML
            deduplicated_refs = deduplicate_html_references(all_references)
            
            # Only add references if we have any
            if deduplicated_refs:
                # Format references as HTML with clear visual separation
                html_references = "<p><strong>Källor:</strong></p><ul>"
                for ref in deduplicated_refs:
                    ref_parts = ref.split(' ', 1)
                    if len(ref_parts) == 2:
                        ref_id, ref_content = ref_parts
                        html_references += f"<li><strong>{ref_id}</strong> {ref_content}</li>"
                html_references += "</ul>"
                
                # Add double line break before references for better visual separation
                final_response += f"\n\n{html_references}"
            return final_response
            
        except Exception as e:
            logger.error(f"Error in _generate_multi_agreement_response: {str(e)}")
            return "Jag kunde inte generera ett fullständigt svar baserat på den tillgängliga informationen. Vänligen omformulera din fråga eller var mer specifik."
