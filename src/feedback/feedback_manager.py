import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger('feedback_manager')

class FeedbackManager:
    """
    Manages user feedback for answers provided by the pension advisor system.
    Handles storing, retrieving, and analyzing feedback data.
    """
    
    def __init__(self, feedback_dir: Union[str, Path] = None):
        """
        Initialize the feedback manager with a directory to store feedback data.
        
        Args:
            feedback_dir: Directory to store feedback data. If None, defaults to 'feedback' in the project root.
        """
        if feedback_dir is None:
            # Default to a 'feedback' directory in the project root
            self.feedback_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / 'feedback'
        else:
            self.feedback_dir = Path(feedback_dir)
            
        # Create the feedback directory if it doesn't exist
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        
        # Path to the feedback database file
        self.feedback_db_path = self.feedback_dir / 'feedback_data.json'
        
        # Initialize or load the feedback database
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize the feedback database or load it if it exists."""
        if not self.feedback_db_path.exists():
            # Create a new feedback database with initial structure
            initial_db = {
                "feedback": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_feedback_count": 0,
                    "positive_count": 0,
                    "negative_count": 0
                }
            }
            
            with open(self.feedback_db_path, 'w', encoding='utf-8') as f:
                json.dump(initial_db, f, ensure_ascii=False, indent=2)
                
            logger.info(f"✅ Created new feedback database at {self.feedback_db_path}")
        else:
            logger.info(f"📊 Using existing feedback database at {self.feedback_db_path}")
    
    def _load_db(self) -> Dict:
        """Load the feedback database from disk."""
        try:
            with open(self.feedback_db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error loading feedback database: {e}")
            # Return an empty database structure if loading fails
            return {
                "feedback": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_feedback_count": 0,
                    "positive_count": 0,
                    "negative_count": 0
                }
            }
    
    def _save_db(self, db: Dict):
        """Save the feedback database to disk."""
        try:
            # Update the last_updated timestamp
            db["metadata"]["last_updated"] = datetime.now().isoformat()
            
            with open(self.feedback_db_path, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
                
            logger.info(f"💾 Saved feedback database with {db['metadata']['total_feedback_count']} entries")
        except Exception as e:
            logger.error(f"❌ Error saving feedback database: {e}")
    
    def add_feedback(self, question_id: str, feedback: str, question: str, answer: str, 
                     user_id: Optional[str] = None, additional_comments: Optional[str] = None) -> bool:
        """
        Add user feedback for a specific answer.
        
        Args:
            question_id: Unique identifier for the question/answer pair
            feedback: Either 'positive' or 'negative'
            question: The original question asked
            answer: The answer that received feedback
            user_id: Optional identifier for the user providing feedback
            additional_comments: Optional additional comments from the user
            
        Returns:
            bool: True if feedback was successfully added, False otherwise
        """
        if feedback not in ['positive', 'negative']:
            logger.error(f"❌ Invalid feedback value: {feedback}. Must be 'positive' or 'negative'.")
            return False
        
        try:
            db = self._load_db()
            
            # Create the feedback entry
            feedback_entry = {
                "id": f"feedback_{len(db['feedback']) + 1}",
                "question_id": question_id,
                "feedback": feedback,
                "question": question,
                "answer": answer,
                "user_id": user_id,
                "additional_comments": additional_comments,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add the feedback entry to the database
            db["feedback"].append(feedback_entry)
            
            # Update metadata
            db["metadata"]["total_feedback_count"] += 1
            if feedback == "positive":
                db["metadata"]["positive_count"] += 1
            else:
                db["metadata"]["negative_count"] += 1
            
            # Save the updated database
            self._save_db(db)
            
            logger.info(f"👍 Added {feedback} feedback for question ID {question_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error adding feedback: {e}")
            return False
    
    def get_feedback_stats(self) -> Dict:
        """
        Get statistics about the collected feedback.
        
        Returns:
            Dict: Statistics about the feedback
        """
        try:
            db = self._load_db()
            
            # Calculate the positive feedback percentage
            total = db["metadata"]["total_feedback_count"]
            positive = db["metadata"]["positive_count"]
            
            positive_percentage = (positive / total) * 100 if total > 0 else 0
            
            stats = {
                "total_feedback_count": total,
                "positive_count": positive,
                "negative_count": db["metadata"]["negative_count"],
                "positive_percentage": round(positive_percentage, 2),
                "last_updated": db["metadata"]["last_updated"]
            }
            
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting feedback stats: {e}")
            return {
                "total_feedback_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "positive_percentage": 0,
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def get_recent_feedback(self, limit: int = 10) -> List[Dict]:
        """
        Get the most recent feedback entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List[Dict]: List of recent feedback entries
        """
        try:
            db = self._load_db()
            
            # Sort feedback by timestamp (newest first) and limit the results
            sorted_feedback = sorted(
                db["feedback"], 
                key=lambda x: x.get("timestamp", ""), 
                reverse=True
            )[:limit]
            
            return sorted_feedback
        except Exception as e:
            logger.error(f"❌ Error getting recent feedback: {e}")
            return []
    
    def get_feedback_by_question_id(self, question_id: str) -> List[Dict]:
        """
        Get all feedback entries for a specific question ID.
        
        Args:
            question_id: The question ID to filter by
            
        Returns:
            List[Dict]: List of feedback entries for the question
        """
        try:
            db = self._load_db()
            
            # Filter feedback by question_id
            filtered_feedback = [
                entry for entry in db["feedback"] 
                if entry.get("question_id") == question_id
            ]
            
            return filtered_feedback
        except Exception as e:
            logger.error(f"❌ Error getting feedback by question ID: {e}")
            return []
    
    def generate_feedback_report(self) -> Dict:
        """
        Generate a comprehensive report of the feedback data.
        
        Returns:
            Dict: A report containing various feedback metrics and insights
        """
        try:
            db = self._load_db()
            feedback_entries = db["feedback"]
            
            # Basic stats
            total = len(feedback_entries)
            positive = sum(1 for entry in feedback_entries if entry.get("feedback") == "positive")
            negative = total - positive
            
            # Calculate positive feedback percentage
            positive_percentage = (positive / total) * 100 if total > 0 else 0
            
            # Group feedback by day
            feedback_by_day = {}
            for entry in feedback_entries:
                timestamp = entry.get("timestamp", "")
                if timestamp:
                    day = timestamp.split("T")[0]  # Extract the date part
                    if day not in feedback_by_day:
                        feedback_by_day[day] = {"total": 0, "positive": 0, "negative": 0}
                    
                    feedback_by_day[day]["total"] += 1
                    if entry.get("feedback") == "positive":
                        feedback_by_day[day]["positive"] += 1
                    else:
                        feedback_by_day[day]["negative"] += 1
            
            # Sort days chronologically
            sorted_days = sorted(feedback_by_day.keys())
            
            # Format the report
            report = {
                "summary": {
                    "total_feedback": total,
                    "positive_feedback": positive,
                    "negative_feedback": negative,
                    "positive_percentage": round(positive_percentage, 2)
                },
                "daily_stats": [
                    {
                        "date": day,
                        "total": feedback_by_day[day]["total"],
                        "positive": feedback_by_day[day]["positive"],
                        "negative": feedback_by_day[day]["negative"],
                        "positive_percentage": round(
                            (feedback_by_day[day]["positive"] / feedback_by_day[day]["total"]) * 100
                            if feedback_by_day[day]["total"] > 0 else 0, 
                            2
                        )
                    }
                    for day in sorted_days
                ],
                "generated_at": datetime.now().isoformat()
            }
            
            return report
        except Exception as e:
            logger.error(f"❌ Error generating feedback report: {e}")
            return {
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
