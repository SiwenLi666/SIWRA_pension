import logging
import uuid
from typing import Dict, Optional, Callable
from datetime import datetime

from src.feedback.feedback_manager import FeedbackManager
from src.utils.config import USER_FEEDBACK_MECHANISM

logger = logging.getLogger('feedback_ui')

class FeedbackUI:
    """
    Provides UI components for collecting user feedback on answers.
    Integrates with the FeedbackManager to store and process feedback.
    """
    
    def __init__(self):
        """Initialize the feedback UI components."""
        self.feedback_manager = FeedbackManager()
        self.current_question_id = None
        self.current_question = None
        self.current_answer = None
    
    def prepare_feedback_ui(self, question: str, answer: str) -> str:
        """
        Prepare the feedback UI for a specific question and answer.
        
        Args:
            question: The question that was asked
            answer: The answer that was generated
            
        Returns:
            str: HTML/Markdown for the feedback UI, or empty string if feedback is disabled
        """
        if not USER_FEEDBACK_MECHANISM:
            return ""
        
        # Generate a unique ID for this question/answer pair
        self.current_question_id = f"q_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.current_question = question
        self.current_answer = answer
        
        # Create the feedback UI in markdown format
        feedback_ui = """
        
---

### Var detta svaret hjälpsamt?

<div style="display: flex; gap: 10px; margin-top: 10px;">
  <button onclick="submitFeedback('positive')" style="padding: 5px 15px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
    👍 Ja
  </button>
  <button onclick="submitFeedback('negative')" style="padding: 5px 15px; background-color: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer;">
    👎 Nej
  </button>
</div>

<div id="feedback-form" style="display: none; margin-top: 10px;">
  <textarea id="additional-feedback" placeholder="Berätta gärna varför (valfritt)" style="width: 100%; padding: 8px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #ddd;"></textarea>
  <button onclick="submitAdditionalFeedback()" style="padding: 5px 15px; background-color: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">
    Skicka
  </button>
</div>

<div id="feedback-thank-you" style="display: none; margin-top: 10px; padding: 10px; background-color: #e7f3fe; border-radius: 4px;">
  Tack för din feedback! Den hjälper oss att förbättra systemet.
</div>

<script>
  function submitFeedback(type) {
    // Show the additional feedback form
    document.getElementById('feedback-form').style.display = 'block';
    
    // Store the feedback type
    window.feedbackType = type;
    
    // Disable the feedback buttons
    const buttons = document.querySelectorAll('button');
    buttons[0].disabled = true;
    buttons[1].disabled = true;
    
    // Send the initial feedback
    fetch('/api/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question_id: '""" + self.current_question_id + """',
        feedback: type,
        question: '""" + self.current_question.replace("'", "\\'") + """',
        answer: '""" + self.current_answer.replace("'", "\\'") + """',
        additional_comments: ''
      }),
    });
  }
  
  function submitAdditionalFeedback() {
    // Get the additional feedback
    const additionalFeedback = document.getElementById('additional-feedback').value;
    
    // Hide the feedback form
    document.getElementById('feedback-form').style.display = 'none';
    
    // Show the thank you message
    document.getElementById('feedback-thank-you').style.display = 'block';
    
    // Send the additional feedback
    fetch('/api/feedback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question_id: '""" + self.current_question_id + """',
        feedback: window.feedbackType,
        question: '""" + self.current_question.replace("'", "\\'") + """',
        answer: '""" + self.current_answer.replace("'", "\\'") + """',
        additional_comments: additionalFeedback
      }),
    });
  }
</script>
"""
        
        return feedback_ui
    
    def handle_feedback_submission(self, feedback_data: Dict) -> Dict:
        """
        Handle the submission of feedback data from the UI.
        
        Args:
            feedback_data: Dictionary containing feedback data
            
        Returns:
            Dict: Response indicating success or failure
        """
        try:
            question_id = feedback_data.get('question_id')
            feedback = feedback_data.get('feedback')
            question = feedback_data.get('question')
            answer = feedback_data.get('answer')
            user_id = feedback_data.get('user_id')
            additional_comments = feedback_data.get('additional_comments')
            
            # Validate required fields
            if not all([question_id, feedback, question, answer]):
                logger.error(f"❌ Missing required fields in feedback submission")
                return {"success": False, "message": "Missing required fields"}
            
            # Add the feedback to the database
            success = self.feedback_manager.add_feedback(
                question_id=question_id,
                feedback=feedback,
                question=question,
                answer=answer,
                user_id=user_id,
                additional_comments=additional_comments
            )
            
            if success:
                logger.info(f"✅ Successfully recorded {feedback} feedback for question {question_id}")
                return {"success": True, "message": "Feedback recorded successfully"}
            else:
                logger.error(f"❌ Failed to record feedback")
                return {"success": False, "message": "Failed to record feedback"}
                
        except Exception as e:
            logger.error(f"❌ Error handling feedback submission: {e}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    def get_feedback_stats_display(self) -> str:
        """
        Get a formatted display of feedback statistics.
        
        Returns:
            str: HTML/Markdown for displaying feedback statistics
        """
        if not USER_FEEDBACK_MECHANISM:
            return ""
        
        try:
            stats = self.feedback_manager.get_feedback_stats()
            
            # Create the stats display in markdown format
            stats_display = f"""
### Feedback Statistik

- **Totalt antal feedback**: {stats['total_feedback_count']}
- **Positiv feedback**: {stats['positive_count']} ({stats['positive_percentage']}%)
- **Negativ feedback**: {stats['negative_count']} ({100 - stats['positive_percentage']}%)
- **Senast uppdaterad**: {stats['last_updated'].split('T')[0]}
"""
            
            return stats_display
        except Exception as e:
            logger.error(f"❌ Error getting feedback stats display: {e}")
            return "Error loading feedback statistics."
