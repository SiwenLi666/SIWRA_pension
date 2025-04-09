"""
API endpoints for follow-up question suggestions.
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.suggestions.suggestion_manager import SuggestionManager
from src.utils.config import FOLLOW_UP_SUGGESTIONS

logger = logging.getLogger('suggestion_api')

# Initialize suggestion manager
suggestion_manager = SuggestionManager()

# Create API router
suggestion_router = APIRouter(
    prefix="/api/suggestions",
    tags=["suggestions"],
    responses={404: {"description": "Not found"}},
)

class SuggestionRequest(BaseModel):
    """Request model for generating suggestions."""
    conversation_id: str
    question: str
    answer: str
    metadata: Optional[Dict] = None
    language: Optional[str] = "sv"

class SuggestionResponse(BaseModel):
    """Response model for suggestions."""
    suggestion_id: str
    suggestions: List[str]

class SuggestionUsageRequest(BaseModel):
    """Request model for tracking suggestion usage."""
    suggestion_id: str
    selected_suggestion: str

class SuggestionUsageResponse(BaseModel):
    """Response model for suggestion usage tracking."""
    success: bool
    message: str

class SuggestionStatsResponse(BaseModel):
    """Response model for suggestion statistics."""
    total_suggestions_used: int
    unique_suggestions: int
    usage_rate: float
    top_suggestions: List
    top_topics: List
    agreement_distribution: List
    most_popular_topic: str

@suggestion_router.post("/generate", response_model=SuggestionResponse)
async def generate_suggestions(request: SuggestionRequest):
    """
    Generate follow-up question suggestions based on the current conversation.
    
    Args:
        request: SuggestionRequest containing conversation details.
        
    Returns:
        SuggestionResponse: Contains suggestion ID and list of suggestions.
    """
    if not FOLLOW_UP_SUGGESTIONS:
        raise HTTPException(status_code=400, detail="Follow-up suggestions feature is disabled")
    
    try:
        # Generate suggestions
        suggestions = suggestion_manager.generate_suggestions(
            conversation_id=request.conversation_id,
            question=request.question,
            answer=request.answer,
            metadata=request.metadata,
            language=request.language
        )
        
        # Get suggestion ID (the latest one)
        suggestion_id = list(suggestion_manager.suggestions_db.keys())[-1]
        
        return SuggestionResponse(
            suggestion_id=suggestion_id,
            suggestions=suggestions
        )
    except Exception as e:
        logger.error(f"Error generating suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating suggestions: {str(e)}")

@suggestion_router.post("/track", response_model=SuggestionUsageResponse)
async def track_suggestion_usage(request: SuggestionUsageRequest):
    """
    Track which suggestion was used by the user.
    
    Args:
        request: SuggestionUsageRequest containing suggestion ID and selected suggestion.
        
    Returns:
        SuggestionUsageResponse: Contains success status and message.
    """
    if not FOLLOW_UP_SUGGESTIONS:
        raise HTTPException(status_code=400, detail="Follow-up suggestions feature is disabled")
    
    try:
        # Track suggestion usage
        success = suggestion_manager.track_suggestion_usage(
            suggestion_id=request.suggestion_id,
            selected_suggestion=request.selected_suggestion
        )
        
        if success:
            return SuggestionUsageResponse(
                success=True,
                message="Suggestion usage tracked successfully"
            )
        else:
            return SuggestionUsageResponse(
                success=False,
                message="Failed to track suggestion usage"
            )
    except Exception as e:
        logger.error(f"Error tracking suggestion usage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error tracking suggestion usage: {str(e)}")

@suggestion_router.get("/stats", response_model=SuggestionStatsResponse)
async def get_suggestion_stats():
    """
    Get statistics about suggestion usage.
    
    Returns:
        SuggestionStatsResponse: Contains suggestion usage statistics.
    """
    if not FOLLOW_UP_SUGGESTIONS:
        raise HTTPException(status_code=400, detail="Follow-up suggestions feature is disabled")
    
    try:
        # Get suggestion stats
        stats = suggestion_manager.get_suggestion_stats()
        
        return SuggestionStatsResponse(
            total_suggestions_used=stats["total_suggestions_used"],
            top_suggestions=stats["top_suggestions"],
            top_topics=stats["top_topics"]
        )
    except Exception as e:
        logger.error(f"Error getting suggestion stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting suggestion stats: {str(e)}")

@suggestion_router.get("/{suggestion_id}", response_model=SuggestionResponse)
async def get_suggestions(suggestion_id: str):
    """
    Get suggestions by ID.
    
    Args:
        suggestion_id: ID of the suggestion set.
        
    Returns:
        SuggestionResponse: Contains suggestion ID and list of suggestions.
    """
    if not FOLLOW_UP_SUGGESTIONS:
        raise HTTPException(status_code=400, detail="Follow-up suggestions feature is disabled")
    
    try:
        # Get suggestions from database
        if suggestion_id not in suggestion_manager.suggestions_db:
            raise HTTPException(status_code=404, detail=f"Suggestion ID {suggestion_id} not found")
        
        suggestions = suggestion_manager.suggestions_db[suggestion_id]["suggestions"]
        
        return SuggestionResponse(
            suggestion_id=suggestion_id,
            suggestions=suggestions
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting suggestions: {str(e)}")
