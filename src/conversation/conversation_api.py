import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.conversation.conversation_manager import ConversationManager
from src.utils.config import CONVERSATION_CONTEXT

logger = logging.getLogger('conversation_api')

# Create a router for conversation endpoints
conversation_router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# Define the conversation models
class Message(BaseModel):
    content: str
    role: str
    metadata: Optional[Dict] = None

class ConversationResponse(BaseModel):
    conversation_id: str
    success: bool
    message: str

# Create a conversation manager instance
conversation_manager = ConversationManager()

@conversation_router.post("/create", response_model=ConversationResponse)
async def create_conversation(request: Request):
    """
    Create a new conversation session.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        # Extract user ID from request if available
        user_id = None
        if hasattr(request, "session") and "user_id" in request.session:
            user_id = request.session["user_id"]
        
        conversation_id = conversation_manager.create_conversation(user_id)
        
        if conversation_id == "error_creating_conversation":
            logger.error("❌ Failed to create conversation")
            raise HTTPException(status_code=500, detail="Failed to create conversation")
        
        logger.info(f"✅ Successfully created conversation {conversation_id}")
        return {
            "conversation_id": conversation_id,
            "success": True,
            "message": "Conversation created successfully"
        }
    
    except Exception as e:
        logger.error(f"❌ Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.post("/{conversation_id}/messages", response_model=ConversationResponse)
async def add_message(conversation_id: str, message: Message):
    """
    Add a message to the conversation history.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        success = conversation_manager.add_message(
            conversation_id=conversation_id,
            message=message.content,
            role=message.role,
            metadata=message.metadata
        )
        
        if not success:
            logger.error(f"❌ Failed to add message to conversation {conversation_id}")
            raise HTTPException(status_code=500, detail="Failed to add message to conversation")
        
        logger.info(f"✅ Successfully added message to conversation {conversation_id}")
        return {
            "conversation_id": conversation_id,
            "success": True,
            "message": "Message added successfully"
        }
    
    except Exception as e:
        logger.error(f"❌ Error adding message to conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.get("/{conversation_id}/history")
async def get_conversation_history(conversation_id: str, max_messages: Optional[int] = None):
    """
    Get the conversation history.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        history = conversation_manager.get_conversation_history(
            conversation_id=conversation_id,
            max_messages=max_messages
        )
        
        if not history and conversation_id != "conversation_disabled":
            logger.warning(f"⚠️ No history found for conversation {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found or no history available")
        
        logger.info(f"✅ Successfully retrieved history for conversation {conversation_id}")
        return history
    
    except Exception as e:
        logger.error(f"❌ Error retrieving conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.get("/{conversation_id}/context")
async def get_conversation_context(conversation_id: str, max_context_messages: Optional[int] = 5):
    """
    Get the conversation context for context-aware question answering.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        context, metadata = conversation_manager.get_conversation_context(
            conversation_id=conversation_id,
            max_context_messages=max_context_messages
        )
        
        if not context and not metadata and conversation_id != "conversation_disabled":
            logger.warning(f"⚠️ No context found for conversation {conversation_id}")
            raise HTTPException(status_code=404, detail="Conversation not found or no context available")
        
        logger.info(f"✅ Successfully retrieved context for conversation {conversation_id}")
        return {
            "context": context,
            "metadata": metadata
        }
    
    except Exception as e:
        logger.error(f"❌ Error retrieving conversation context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.post("/{conversation_id}/resolve")
async def resolve_references(conversation_id: str, message: Message):
    """
    Resolve references in the message based on conversation context.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        resolved_message = conversation_manager.resolve_references(
            conversation_id=conversation_id,
            message=message.content
        )
        
        logger.info(f"✅ Successfully resolved references for conversation {conversation_id}")
        return {
            "original_message": message.content,
            "resolved_message": resolved_message
        }
    
    except Exception as e:
        logger.error(f"❌ Error resolving references: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.delete("/{conversation_id}", response_model=ConversationResponse)
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        success = conversation_manager.delete_conversation(conversation_id)
        
        if not success:
            logger.error(f"❌ Failed to delete conversation {conversation_id}")
            raise HTTPException(status_code=500, detail="Failed to delete conversation")
        
        logger.info(f"✅ Successfully deleted conversation {conversation_id}")
        return {
            "conversation_id": conversation_id,
            "success": True,
            "message": "Conversation deleted successfully"
        }
    
    except Exception as e:
        logger.error(f"❌ Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@conversation_router.get("/")
async def get_active_conversations():
    """
    Get a list of active conversations.
    """
    if not CONVERSATION_CONTEXT:
        raise HTTPException(status_code=404, detail="Conversation context management is disabled")
    
    try:
        conversations = conversation_manager.get_active_conversations()
        
        logger.info(f"✅ Successfully retrieved {len(conversations)} active conversations")
        return conversations
    
    except Exception as e:
        logger.error(f"❌ Error retrieving active conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
