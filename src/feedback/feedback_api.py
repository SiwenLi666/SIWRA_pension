import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.feedback.feedback_manager import FeedbackManager
from src.utils.config import USER_FEEDBACK_MECHANISM

logger = logging.getLogger('feedback_api')

# Create a router for feedback endpoints
feedback_router = APIRouter(prefix="/api/feedback", tags=["feedback"])

# Define the feedback submission model
class FeedbackSubmission(BaseModel):
    question_id: str
    feedback: str
    question: str
    answer: str
    user_id: str = None
    additional_comments: str = None

# Create a feedback manager instance
feedback_manager = FeedbackManager()

@feedback_router.post("/")
async def submit_feedback(feedback: FeedbackSubmission):
    """
    Submit user feedback for an answer.
    """
    if not USER_FEEDBACK_MECHANISM:
        raise HTTPException(status_code=404, detail="Feedback mechanism is disabled")
    
    try:
        success = feedback_manager.add_feedback(
            question_id=feedback.question_id,
            feedback=feedback.feedback,
            question=feedback.question,
            answer=feedback.answer,
            user_id=feedback.user_id,
            additional_comments=feedback.additional_comments
        )
        
        if success:
            logger.info(f"✅ Successfully recorded {feedback.feedback} feedback for question {feedback.question_id}")
            return {"success": True, "message": "Feedback recorded successfully"}
        else:
            logger.error(f"❌ Failed to record feedback")
            raise HTTPException(status_code=500, detail="Failed to record feedback")
    
    except Exception as e:
        logger.error(f"❌ Error handling feedback submission: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@feedback_router.get("/stats")
async def get_feedback_stats():
    """
    Get statistics about the collected feedback.
    """
    if not USER_FEEDBACK_MECHANISM:
        raise HTTPException(status_code=404, detail="Feedback mechanism is disabled")
    
    try:
        stats = feedback_manager.get_feedback_stats()
        return stats
    
    except Exception as e:
        logger.error(f"❌ Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@feedback_router.get("/recent")
async def get_recent_feedback(limit: int = 10):
    """
    Get the most recent feedback entries.
    """
    if not USER_FEEDBACK_MECHANISM:
        raise HTTPException(status_code=404, detail="Feedback mechanism is disabled")
    
    try:
        recent_feedback = feedback_manager.get_recent_feedback(limit=limit)
        return recent_feedback
    
    except Exception as e:
        logger.error(f"❌ Error getting recent feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@feedback_router.get("/report")
async def get_feedback_report():
    """
    Generate a comprehensive report of the feedback data.
    """
    if not USER_FEEDBACK_MECHANISM:
        raise HTTPException(status_code=404, detail="Feedback mechanism is disabled")
    
    try:
        report = feedback_manager.generate_feedback_report()
        return report
    
    except Exception as e:
        logger.error(f"❌ Error generating feedback report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
