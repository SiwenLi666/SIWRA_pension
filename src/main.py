"""
FastAPI server for the pension advisor chat interface.
"""
import os
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from .init_system import init_system
from .multi_agent_graph import PensionAdvisorGraph
from .agent import PensionAdvisor
from .multi_agent_graph import PensionAnalystAgent
from .document_processor import DocumentProcessor

# Create instances
doc_processor = DocumentProcessor()  # Ensure DocumentProcessor is initialized
analyst_agent = PensionAnalystAgent(doc_processor) 
advisor = PensionAdvisor(doc_processor, analyst_agent)  # Pass the analyst agent instance
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler("pension_advisor.log")  # Log to file
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# Initialize FastAPI with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting system initialization...")
    success = await init_system()
    if not success:
        logger.error("System initialization failed")
        raise Exception("Failed to initialize system")
    logger.info("System initialization completed successfully")
    yield
    # Shutdown
    logger.info("Shutting down system...")
    pass

# Create FastAPI app with explicit host and port
host = os.getenv("HOST", "127.0.0.1")
port = int(os.getenv("PORT", "9090"))
app = FastAPI(lifespan=lifespan)

# Store conversation instances by session ID
conversation_store: Dict[str, PensionAdvisorGraph] = {}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, request: Request):
    """REST endpoint for chat."""
    try:
        logger.info(f"Received message: {message.message}")
        
        # Use client IP as session ID (or generate a random one if not available)
        session_id = request.client.host if request.client and request.client.host else str(uuid.uuid4())
        logger.info(f"Session ID: {session_id}")
        
        # Get or create advisor instance for this session
        if session_id in conversation_store:
            logger.info(f"Using existing conversation for session {session_id}")
            advisor = conversation_store[session_id]
        else:
            logger.info(f"Creating new conversation for session {session_id}")
            advisor = PensionAdvisorGraph()
            conversation_store[session_id] = advisor
        
        # Run the conversation with the user's message
        logger.info("Processing message through advisor graph...")
        response, _ = advisor.run_with_visualization(message.message)
        
        logger.info(f"Generated response: {response[:100]}...")  # Log first 100 chars
        return ChatResponse(response=response)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        # Return a user-friendly error message
        return ChatResponse(response="Tyvärr uppstod ett fel. Försök igen senare.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for chat."""
    try:
        await websocket.accept()
        logger.info("WebSocket connection established")
        
        # Create a unique session ID for this WebSocket connection
        session_id = str(uuid.uuid4())
        logger.info(f"WebSocket session ID: {session_id}")
        
        # Create a new advisor instance for this session
        advisor = PensionAdvisorGraph()
        conversation_store[session_id] = advisor
        
        while True:
            try:
                # Receive message from client
                message = await websocket.receive_text()
                logger.info(f"Received WebSocket message: {message}")
                
                # Process the message
                try:
                    logger.info("Processing WebSocket message...")
                    response, _ = advisor.run_with_visualization(message)
                    logger.info(f"Generated WebSocket response: {response[:100]}...")  # Log first 100 chars
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {str(e)}", exc_info=True)
                    response = "Tyvärr uppstod ett fel. Försök igen senare."
                
                # Send response back to client
                await websocket.send_text(response)
                
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                # Clean up the conversation when the WebSocket disconnects
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
        # Clean up in case the try/except blocks didn't handle it
        try:
            if session_id in conversation_store:
                del conversation_store[session_id]
                logger.info(f"Cleaned up conversation for session {session_id}")
        except:
            pass

# Mount static files AFTER registering API routes
static_dir = Path(__file__).parent.parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=host, port=port)