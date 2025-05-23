import os
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.utils.config import setup_logger
from src.graph.pension_graph import create_pension_graph
from src.graph.state import GraphState
from src.retriever.document_processor import DocumentProcessor
# Removed import of PensionAnalystAgent as part of refactoring
from src.graph.state import AgentState
from src.utils.config import BASE_DIR, USER_FEEDBACK_MECHANISM, CONVERSATION_CONTEXT, FOLLOW_UP_SUGGESTIONS
import langdetect

# Import feedback API if enabled
USER_FEEDBACK_MECHANISM = False
    
# Import conversation API if enabled
CONVERSATION_CONTEXT = False
    
# Import follow-up suggestions API if enabled
FOLLOW_UP_SUGGESTIONS = False
    

static_dir = Path(BASE_DIR) / "static"


setup_logger()
load_dotenv()
logger = logging.getLogger('main')

# Initialize document processor without analyst agent as part of refactoring
processor = DocumentProcessor()

def detect_language(text: str) -> str:
    try:
        lang = langdetect.detect(text)
        return "sv" if lang == "sv" else "en"
    except:
        return "en"

class PensionAdvisorGraph:
    def __init__(self):
        self.graph = create_pension_graph()
        # Initialize visualizer if available
        try:
            from src.graph.visualization import LangGraphVisualizer
            self.visualizer = LangGraphVisualizer(self.graph)
        except ImportError:
            logger.warning("LangGraph visualization module not available. Visualization features will be disabled.")
            self.visualizer = None

    def run_with_visualization(self, message: str, generate_viz: bool = False):
        """
        Run the graph with optional visualization.
        
        Args:
            message: The user message to process
            generate_viz: Whether to generate visualization artifacts
            
        Returns:
            Tuple of (response_text, final_state)
        """
        # Detect language
        language = detect_language(message)
        
        # Initialize state with minimal required fields
        state = {
            "question": message,
            "user_language": language,
            "conversation_history": [],
            "status": "🔍 Bearbetar frågan..."
        }
        
        # Generate visualization if requested
        if generate_viz and self.visualizer:
            try:
                viz_html = self.visualizer.generate_html(state)
                logger.info(f"Generated visualization HTML: {len(viz_html)} bytes")
                return viz_html, state
            except Exception as e:
                logger.error(f"Error generating visualization: {str(e)}")
                return f"Error generating visualization: {str(e)}", state
        
        # Run the graph with the simplified ToolUsingPensionAgent
        try:
            logger.info(f"Processing message: {message}")
            final_state = self.graph.invoke(state)
            
            # UNWRAP single-node result if needed
            if len(final_state) == 1 and isinstance(list(final_state.values())[0], dict):
                logger.warning("[DEBUG] Detected wrapped final state - unwrapping it.")
                final_state = list(final_state.values())[0]
            
            logger.info(f"Final state from LangGraph: {final_state}")
            logger.info(f"[DEBUG] state keys: {list(final_state.keys())}")
            
            response_text = (
                final_state.get("response")
                or final_state.get("draft_answer")
                or "Tyvärr, ingen respons genererades."
            )
            
            if not isinstance(response_text, str):
                response_text = str(response_text)
            response_text = response_text.strip().replace('\u202f', ' ').replace('\xa0', ' ')
            
            logger.info(f"Cleaned response: {response_text[:100]}..." if len(response_text) > 100 else response_text)
            return response_text, final_state
            
        except Exception as e:
            logger.error(f"Error running graph: {str(e)}")
            return f"Ett fel uppstod: {str(e)}", state







class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    conversation_id: Optional[str] = None
    suggestions: Optional[List[str]] = None
    suggestion_id: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info(" Starting system initialization...")

        base_dir = Path(__file__).parent
        data_dir = base_dir / "data"
        docs_dir = base_dir / "docs"
        agreements_dir = docs_dir / "agreements"

        for directory in [data_dir, docs_dir, agreements_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f" Ensured directory exists: {directory}")

        # Initialize cost tracker DB if not present
        costs_db = data_dir / "costs.db"
        if not costs_db.exists():
            logger.info(" Creating new cost tracking database...")
                        

        logger.info(" System initialization completed successfully")
        yield
        logger.info(" Shutting down system...")

    except Exception as e:
        logger.error(f" System initialization failed: {str(e)}", exc_info=True)
        raise e


host = os.getenv("HOST", "127.0.0.1")
port = int(os.getenv("PORT", "9095"))
app = FastAPI(lifespan=lifespan)

conversation_store: Dict[str, PensionAdvisorGraph] = {}

# Initialize conversation manager if enabled
conversation_manager = ConversationManager() if CONVERSATION_CONTEXT else None

# Initialize suggestion manager if enabled
suggestion_manager = SuggestionManager() if FOLLOW_UP_SUGGESTIONS else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include feedback router if enabled
if USER_FEEDBACK_MECHANISM:
    app.include_router(feedback_router)
    logger.info(" Feedback API routes enabled")
    
# Include follow-up suggestions router if enabled
if FOLLOW_UP_SUGGESTIONS:
    app.include_router(suggestion_router)
    logger.info(" Suggestion API routes enabled")
    
    
# Include conversation router if enabled
if CONVERSATION_CONTEXT:
    app.include_router(conversation_router)
    logger.info(" Conversation API routes enabled")
    
# Include suggestion router if enabled
if FOLLOW_UP_SUGGESTIONS:
    app.include_router(suggestion_router)
    logger.info(" Follow-up suggestions API routes enabled")
    

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, request: Request):
    try:
        # Get original message
        original_message = message.message
        logger.info(f"Received message: {original_message}")
        
        # Generate session ID
        session_id = request.client.host if request.client and request.client.host else str(uuid.uuid4())
        logger.info(f"Session ID: {session_id}")
        
        # Handle conversation context if enabled
        conversation_id = None
        if CONVERSATION_CONTEXT and conversation_manager:
            # Get or create conversation ID from request headers
            conversation_id = request.headers.get("X-Conversation-ID")
            
            if not conversation_id or conversation_id not in conversation_manager.active_conversations:
                # Create new conversation if none exists
                conversation_id = conversation_manager.create_conversation(user_id=session_id)
                logger.info(f"Created new conversation context: {conversation_id}")
            
            # Resolve references in the message based on conversation context
            resolved_message = conversation_manager.resolve_references(conversation_id, original_message)
            if resolved_message != original_message:
                logger.info(f"Resolved message: {resolved_message}")
                message.message = resolved_message
        
        # Create or get LangGraph session
        if session_id not in conversation_store:
            logger.info(f"Creating new LangGraph session for {session_id}")
            conversation_store[session_id] = PensionAdvisorGraph()

        # Run the advisor
        advisor = conversation_store[session_id]
        response, state_dict = advisor.run_with_visualization(message.message)

        #  Safety net: force string
        if not isinstance(response, str):
            response = str(response)
        
        # Store the conversation context if enabled
        if CONVERSATION_CONTEXT and conversation_manager and conversation_id:
            # Extract metadata from state
            metadata = {}
            
            if "selected_agreement" in state_dict:
                metadata["selected_agreement"] = state_dict["selected_agreement"]
                
            if "question_type" in state_dict:
                metadata["topics"] = [state_dict["question_type"]]
                
            if "entities" in state_dict:
                metadata["entities"] = state_dict["entities"]
            
            # Add user message to conversation history
            conversation_manager.add_message(
                conversation_id=conversation_id,
                message=original_message,
                role="user",
                metadata=metadata
            )
            
            # Add assistant response to conversation history
            conversation_manager.add_message(
                conversation_id=conversation_id,
                message=response,
                role="assistant",
                metadata=metadata
            )
        
        logger.info(f"[chat endpoint] Final response: {repr(response)}")
        
        # Generate follow-up suggestions if enabled
        suggestions = []
        suggestion_id = None
        if FOLLOW_UP_SUGGESTIONS and suggestion_manager and conversation_id:
            try:
                # Detect language
                language = detect_language(original_message)
                
                # Extract metadata
                metadata = {}
                if "selected_agreement" in state_dict:
                    metadata["selected_agreement"] = state_dict["selected_agreement"]
                if "question_type" in state_dict:
                    metadata["topics"] = [state_dict["question_type"]]
                if "entities" in state_dict:
                    metadata["entities"] = state_dict["entities"]
                
                # Generate suggestions using the manager directly
                suggestions = suggestion_manager.generate_suggestions(
                    conversation_id=conversation_id,
                    question=original_message,
                    answer=response,
                    metadata=metadata,
                    language=language
                )
                
                # Get the suggestion ID (the latest one)
                if suggestion_manager.suggestions_db:
                    suggestion_id = list(suggestion_manager.suggestions_db.keys())[-1]
                
                logger.info(f"Generated {len(suggestions)} follow-up suggestions")
            except Exception as e:
                logger.error(f"Error generating follow-up suggestions: {str(e)}")
        
        # Add suggestions to the response
        response_data = {
            "conversation_id": conversation_id,
            "suggestions": suggestions,
            "suggestion_id": suggestion_id
        }
        
        return ChatResponse(response=response, **response_data)


    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return ChatResponse(response="Tyvärr uppstod ett fel. Försök igen senare.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = str(uuid.uuid4())
    conversation_id = None
    
    try:
        await websocket.accept()
        logger.info("WebSocket connection established")
        logger.info(f"WebSocket session ID: {session_id}")
        
        # Create LangGraph advisor
        advisor = PensionAdvisorGraph()
        conversation_store[session_id] = advisor
        
        # Create conversation context if enabled
        if CONVERSATION_CONTEXT and conversation_manager:
            conversation_id = conversation_manager.create_conversation(user_id=session_id)
            logger.info(f"Created new conversation context for WebSocket: {conversation_id}")
            
            # Send conversation ID to client
            await websocket.send_json({
                "type": "conversation_id",
                "conversation_id": conversation_id
            })

        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                logger.info(f"Received WebSocket message: {data}")
                
                # Parse message data
                original_message = data
                
                # Handle conversation context if enabled
                if CONVERSATION_CONTEXT and conversation_manager and conversation_id:
                    # Resolve references in the message based on conversation context
                    resolved_message = conversation_manager.resolve_references(conversation_id, original_message)
                    if resolved_message != original_message:
                        logger.info(f"Resolved WebSocket message: {resolved_message}")
                        data = resolved_message
                
                # Process the message
                response, state_dict = advisor.run_with_visualization(data)
                
                # Extract calculation parameters if available and send to frontend
                if "last_calculation" in state_dict and state_dict["last_calculation"] and "input" in state_dict["last_calculation"]:
                    calculation_params = state_dict["last_calculation"]["input"]
                    # Send calculation parameters to frontend for display in calculator
                    await websocket.send_json({
                        "type": "chat_calculation_update",
                        "calculationParams": calculation_params
                    })
                    logger.info(f"Sent calculation parameters to frontend: {calculation_params}")
                
                # Store the conversation context if enabled
                if CONVERSATION_CONTEXT and conversation_manager and conversation_id:
                    # Extract metadata from state
                    metadata = {}
                    
                    if "selected_agreement" in state_dict:
                        metadata["selected_agreement"] = state_dict["selected_agreement"]
                        
                    if "question_type" in state_dict:
                        metadata["topics"] = [state_dict["question_type"]]
                        
                    if "entities" in state_dict:
                        metadata["entities"] = state_dict["entities"]
                    
                    # Add user message to conversation history
                    conversation_manager.add_message(
                        conversation_id=conversation_id,
                        message=original_message,
                        role="user",
                        metadata=metadata
                    )
                    
                    # Add assistant response to conversation history
                    conversation_manager.add_message(
                        conversation_id=conversation_id,
                        message=response,
                        role="assistant",
                        metadata=metadata
                    )
                
                # Send response to client
                await websocket.send_text(response)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                if session_id in conversation_store:
                    del conversation_store[session_id]
                    logger.info(f"Removed conversation for session {session_id}")
                break
                
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}", exc_info=True)
                try:
                    await websocket.send_text("Tyvärr uppstod ett fel. Försök igen senare.")
                except:
                    logger.error("Failed to send error message to WebSocket client")
                    break
    except Exception as e:
        logger.error(f"Critical WebSocket error: {str(e)}", exc_info=True)
    finally:
        try:
            if session_id in conversation_store:
                del conversation_store[session_id]
                logger.info(f"Cleaned up conversation for session {session_id}")
        except:
            pass


app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
   import uvicorn
   import argparse
   
   # Parse command-line arguments
   parser = argparse.ArgumentParser(description="Pension Advisor API Server")
   parser.add_argument("--host", type=str, default=host, help="Host to bind the server to")
   parser.add_argument("--port", type=int, default=port, help="Port to bind the server to")
   args = parser.parse_args()
   
   # Use the parsed arguments
   logger.info(f"Starting server on {args.host}:{args.port}")
   uvicorn.run(app, host=args.host, port=args.port)


# if __name__ == "__main__":
#     # Run test directly
#     advisor = PensionAdvisorGraph()
#     response, state = advisor.run_with_visualization("ignored because hardcoded inside")

#     print("\n Final response:")
#     print(response)

#     print("\n Final state:")
#     for k, v in state.items():
#         print(f"{k}: {v}")
