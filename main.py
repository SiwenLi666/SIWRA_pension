import os
import uuid
import logging
from pathlib import Path
from typing import Dict
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
from src.agents.advice_agents import PensionAnalystAgent
from src.graph.state import AgentState

from src.utils.config import BASE_DIR  

static_dir = Path(BASE_DIR) / "static"


setup_logger()
load_dotenv()
logger = logging.getLogger('main')

processor = DocumentProcessor()
analyst_agent = PensionAnalystAgent(processor)
processor.analyst_agent = analyst_agent

class PensionAdvisorGraph:
    def __init__(self):
        self.graph = create_pension_graph()

    def run_with_visualization(self, message: str):
        logger.info(f"🔍 Initial user message: {message!r}")
        assert isinstance(message, str) and message.strip(), "❌ Tom eller ogiltig fråga skickades till LangGraph."

        state_dict = {
            "question": message.strip(),
            "state": AgentState.GATHERING_INFO.value,
            "conversation_id": str(uuid.uuid4()),
            "conversation_history": [],
            "user_profile": {},
            "token_usage": [],
        }

        logger.info(f"🧪 Building state: {state_dict}")

        final = None
        for step in self.graph.stream(state_dict):
            if "status" in step:
                logger.info(f"🧠 Status update: {step['status']}")
            final = step

        if final is None:
            logger.error("❌ LangGraph returned None. Something went wrong during execution.")
            raise RuntimeError("LangGraph returned None instead of a GraphState")

        logger.info(f"🧠 Final state from LangGraph:\n{final}")

        # ✅ Fallback if response is missing
        response_text = final.get("response") or final.get("draft_answer") or "Tyvärr, ingen respons genererades."

        # 💡 Force string for safety
        if not isinstance(response_text, str):
            response_text = str(response_text)

        # ✅ Final log
        logger.info(f"✅ Final response to frontend: {response_text[:300]}")

        return response_text, final





class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("🔁 Starting system initialization...")

        base_dir = Path(__file__).parent
        data_dir = base_dir / "data"
        docs_dir = base_dir / "docs"
        agreements_dir = docs_dir / "agreements"

        for directory in [data_dir, docs_dir, agreements_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Ensured directory exists: {directory}")

        # Initialize cost tracker DB if not present
        costs_db = data_dir / "costs.db"
        if not costs_db.exists():
            logger.info("🧾 Creating new cost tracking database...")
                        

        logger.info("✅ System initialization completed successfully")
        yield
        logger.info("🛑 Shutting down system...")

    except Exception as e:
        logger.error(f"❌ System initialization failed: {str(e)}", exc_info=True)
        raise e


host = os.getenv("HOST", "127.0.0.1")
port = int(os.getenv("PORT", "9090"))
app = FastAPI(lifespan=lifespan)

conversation_store: Dict[str, PensionAdvisorGraph] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, request: Request):
    try:
        logger.info(f"Received message: {message.message}")
        session_id = request.client.host if request.client and request.client.host else str(uuid.uuid4())
        logger.info(f"Session ID: {session_id}")

        if session_id not in conversation_store:
            logger.info(f"Creating new LangGraph session for {session_id}")
            conversation_store[session_id] = PensionAdvisorGraph()

        advisor = conversation_store[session_id]
        response, _ = advisor.run_with_visualization(message.message)

        # ✅ Safety net: force string
        if not isinstance(response, str):
            response = str(response)
        logger.info(f"Generated response: {response[:100]}...")
        logger.info(f"🚀 Returning to frontend: {response}")
        return ChatResponse(response=response)


    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return ChatResponse(response="Tyvärr uppstod ett fel. Försök igen senare.")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        logger.info("WebSocket connection established")

        session_id = str(uuid.uuid4())
        logger.info(f"WebSocket session ID: {session_id}")
        advisor = PensionAdvisorGraph()
        conversation_store[session_id] = advisor

        while True:
            try:
                message = await websocket.receive_text()
                logger.info(f"Received WebSocket message: {message}")
                response, _ = advisor.run_with_visualization(message)
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
   uvicorn.run(app, host=host, port=port)


# if __name__ == "__main__":
#     # Run test directly
#     advisor = PensionAdvisorGraph()
#     response, state = advisor.run_with_visualization("ignored because hardcoded inside")

#     print("\n🧪 Final response:")
#     print(response)

#     print("\n🧠 Final state:")
#     for k, v in state.items():
#         print(f"{k}: {v}")
