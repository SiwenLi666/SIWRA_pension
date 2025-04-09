"""
Module for generating and managing follow-up question suggestions.
This module provides functionality to generate contextually relevant follow-up questions
based on conversation history and track which suggestions are most helpful.
"""

import json
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
from pathlib import Path

from src.utils.config import BASE_DIR

logger = logging.getLogger('suggestion_manager')

class SuggestionManager:
    """
    Class for managing follow-up question suggestions.
    Generates contextually relevant follow-up questions based on conversation history
    and tracks which suggestions are most helpful.
    """
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the SuggestionManager.
        
        Args:
            data_dir: Directory to store suggestion data. Defaults to BASE_DIR/data/suggestions.
        """
        if data_dir is None:
            self.data_dir = os.path.join(BASE_DIR, "data", "suggestions")
        else:
            self.data_dir = data_dir
            
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Path to the suggestions database
        self.suggestions_db_path = os.path.join(self.data_dir, "suggestions_db.json")
        
        # Path to the suggestion stats database
        self.suggestion_stats_path = os.path.join(self.data_dir, "suggestion_stats.json")
        
        # Load or create suggestions database
        self.suggestions_db = self._load_or_create_db(self.suggestions_db_path)
        
        # Load or create suggestion stats database
        self.suggestion_stats = self._load_or_create_db(self.suggestion_stats_path)
        
        # Template-based suggestions for common topics
        self.template_suggestions = {
            "eligibility": [
                "Vilka ålderskrav gäller för denna pension?",
                "Hur beräknas min pensionsgrundande inkomst?",
                "Påverkar deltidsarbete min pension?",
                "What age requirements apply to this pension?",
                "How is my pension-qualifying income calculated?",
                "Does part-time work affect my pension?"
            ],
            "benefits": [
                "Hur mycket kan jag förvänta mig att få i pension?",
                "Finns det ett tak för pensionsutbetalningar?",
                "Hur indexeras pensionen över tid?",
                "How much can I expect to receive in pension?",
                "Is there a cap on pension payments?",
                "How is the pension indexed over time?"
            ],
            "application": [
                "Hur ansöker jag om denna pension?",
                "Vilka dokument behöver jag för att ansöka?",
                "När bör jag ansöka om pension?",
                "How do I apply for this pension?",
                "What documents do I need to apply?",
                "When should I apply for pension?"
            ],
            "comparison": [
                "Hur skiljer sig detta från andra pensionsavtal?",
                "Vilka är fördelarna med detta avtal jämfört med andra?",
                "Kan jag byta pensionsavtal?",
                "How does this differ from other pension agreements?",
                "What are the benefits of this agreement compared to others?",
                "Can I switch pension agreements?"
            ],
            "calculation": [
                "Hur beräknas min pension?",
                "Vilka faktorer påverkar beräkningen?",
                "Kan jag få en uppskattning av min framtida pension?",
                "How is my pension calculated?",
                "What factors affect the calculation?",
                "Can I get an estimate of my future pension?"
            ]
        }
    
    def _load_or_create_db(self, db_path: str) -> Dict:
        """
        Load database from file or create a new one if it doesn't exist.
        
        Args:
            db_path: Path to the database file.
            
        Returns:
            Dict: The loaded or newly created database.
        """
        if os.path.exists(db_path):
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error decoding JSON from {db_path}. Creating new database.")
                return {}
        else:
            return {}
    
    def _save_db(self, db: Dict, db_path: str) -> None:
        """
        Save database to file.
        
        Args:
            db: Database to save.
            db_path: Path to save the database to.
        """
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    
    def generate_suggestions(self, 
                            conversation_id: str, 
                            question: str, 
                            answer: str, 
                            metadata: Optional[Dict[str, Any]] = None,
                            language: str = "sv") -> List[str]:
        """
        Generate follow-up question suggestions based on the current conversation.
        
        Args:
            conversation_id: ID of the conversation.
            question: Current question from the user.
            answer: Answer provided to the user.
            metadata: Additional metadata about the conversation.
            language: Language of the conversation (sv or en).
            
        Returns:
            List[str]: List of suggested follow-up questions.
        """
        # Default metadata if none provided
        if metadata is None:
            metadata = {}
        
        # Generate suggestion ID
        suggestion_id = str(uuid.uuid4())
        
        # Determine topics from metadata or extract from question/answer
        topics = metadata.get("topics", [])
        if not topics:
            topics = self._extract_topics(question, answer)
        
        # Get selected agreement from metadata
        selected_agreement = metadata.get("selected_agreement", None)
        
        # Generate suggestions based on topics and selected agreement
        suggestions = self._generate_topic_based_suggestions(topics, language)
        
        # Add agreement-specific suggestions if an agreement is selected
        if selected_agreement:
            agreement_suggestions = self._generate_agreement_specific_suggestions(selected_agreement, language)
            suggestions.extend(agreement_suggestions)
        
        # Limit to 3 suggestions
        suggestions = suggestions[:3]
        
        # Store suggestions in database
        self.suggestions_db[suggestion_id] = {
            "conversation_id": conversation_id,
            "question": question,
            "answer": answer,
            "suggestions": suggestions,
            "topics": topics,
            "selected_agreement": selected_agreement,
            "language": language,
            "timestamp": datetime.now().isoformat(),
            "used_suggestions": []
        }
        
        # Save database
        self._save_db(self.suggestions_db, self.suggestions_db_path)
        
        return suggestions
    
    def _extract_topics(self, question: str, answer: str) -> List[str]:
        """
        Extract topics from question and answer.
        
        Args:
            question: Question from the user.
            answer: Answer provided to the user.
            
        Returns:
            List[str]: List of extracted topics.
        """
        # Simple keyword-based topic extraction
        topics = []
        
        # Check for eligibility-related keywords
        eligibility_keywords = ["eligible", "qualify", "requirements", "berättigad", "kvalificera", "krav", "ålder", "age"]
        if any(keyword in question.lower() or keyword in answer.lower() for keyword in eligibility_keywords):
            topics.append("eligibility")
        
        # Check for benefits-related keywords
        benefits_keywords = ["benefits", "amount", "payment", "förmåner", "belopp", "utbetalning"]
        if any(keyword in question.lower() or keyword in answer.lower() for keyword in benefits_keywords):
            topics.append("benefits")
        
        # Check for application-related keywords
        application_keywords = ["apply", "application", "process", "ansöka", "ansökan", "process"]
        if any(keyword in question.lower() or keyword in answer.lower() for keyword in application_keywords):
            topics.append("application")
        
        # Check for comparison-related keywords
        comparison_keywords = ["compare", "difference", "better", "jämföra", "skillnad", "bättre"]
        if any(keyword in question.lower() or keyword in answer.lower() for keyword in comparison_keywords):
            topics.append("comparison")
        
        # Check for calculation-related keywords
        calculation_keywords = ["calculate", "formula", "computation", "beräkna", "formel", "beräkning"]
        if any(keyword in question.lower() or keyword in answer.lower() for keyword in calculation_keywords):
            topics.append("calculation")
        
        # Default to eligibility if no topics found
        if not topics:
            topics.append("eligibility")
        
        return topics
    
    def _generate_topic_based_suggestions(self, topics: List[str], language: str) -> List[str]:
        """
        Generate suggestions based on topics.
        
        Args:
            topics: List of topics.
            language: Language of the conversation (sv or en).
            
        Returns:
            List[str]: List of suggested follow-up questions.
        """
        suggestions = []
        
        # Get suggestions for each topic
        for topic in topics:
            if topic in self.template_suggestions:
                topic_suggestions = self.template_suggestions[topic]
                
                # Filter by language
                if language == "sv":
                    filtered_suggestions = [s for s in topic_suggestions if not any(english_word in s for english_word in ["How", "What", "When", "Is", "Can", "Does"])]
                else:
                    filtered_suggestions = [s for s in topic_suggestions if any(english_word in s for english_word in ["How", "What", "When", "Is", "Can", "Does"])]
                
                # Add suggestions
                suggestions.extend(filtered_suggestions)
        
        # Shuffle suggestions to add variety
        import random
        random.shuffle(suggestions)
        
        return suggestions
    
    def _generate_agreement_specific_suggestions(self, agreement: str, language: str) -> List[str]:
        """
        Generate agreement-specific suggestions.
        
        Args:
            agreement: Selected pension agreement.
            language: Language of the conversation (sv or en).
            
        Returns:
            List[str]: List of suggested follow-up questions.
        """
        # Agreement-specific suggestions
        agreement_suggestions = {
            "ITP1": {
                "sv": [
                    "Hur fungerar ITP1 för mig som tjänsteman?",
                    "Vilka valmöjligheter har jag inom ITP1?",
                    "Hur påverkar löneväxling min ITP1?"
                ],
                "en": [
                    "How does ITP1 work for me as a white-collar worker?",
                    "What choices do I have within ITP1?",
                    "How does salary exchange affect my ITP1?"
                ]
            },
            "ITP2": {
                "sv": [
                    "Hur beräknas min ITPK inom ITP2?",
                    "Vad händer med min ITP2 om jag byter jobb?",
                    "Kan jag ta ut min ITP2 i förtid?"
                ],
                "en": [
                    "How is my ITPK calculated within ITP2?",
                    "What happens to my ITP2 if I change jobs?",
                    "Can I withdraw my ITP2 early?"
                ]
            },
            "SAF-LO": {
                "sv": [
                    "Hur fungerar SAF-LO för mig som arbetare?",
                    "Vilka bolag kan jag välja för min SAF-LO?",
                    "Hur påverkas min SAF-LO av arbetsbyte?"
                ],
                "en": [
                    "How does SAF-LO work for me as a blue-collar worker?",
                    "Which companies can I choose for my SAF-LO?",
                    "How is my SAF-LO affected by changing jobs?"
                ]
            },
            "PA16": {
                "sv": [
                    "Vilka delar ingår i PA16?",
                    "Hur skiljer sig PA16 från tidigare statliga pensionsavtal?",
                    "Vilka valmöjligheter har jag inom PA16?"
                ],
                "en": [
                    "What parts are included in PA16?",
                    "How does PA16 differ from previous state pension agreements?",
                    "What choices do I have within PA16?"
                ]
            }
        }
        
        # Get suggestions for the selected agreement
        if agreement in agreement_suggestions:
            lang_key = "en" if language == "en" else "sv"
            return agreement_suggestions[agreement][lang_key]
        
        return []
    
    def track_suggestion_usage(self, suggestion_id: str, selected_suggestion: str) -> bool:
        """
        Track which suggestion was used by the user.
        
        Args:
            suggestion_id: ID of the suggestion set.
            selected_suggestion: The suggestion that was selected by the user.
            
        Returns:
            bool: True if tracking was successful, False otherwise.
        """
        try:
            # Check if suggestion ID exists
            if suggestion_id not in self.suggestions_db:
                logger.warning(f"Suggestion ID {suggestion_id} not found")
                return False
                
            # Get suggestion data
            suggestion_data = self.suggestions_db[suggestion_id]
            
            # Check if selected suggestion is in the suggestions list
            if selected_suggestion not in suggestion_data["suggestions"]:
                logger.warning(f"Selected suggestion '{selected_suggestion}' not found in suggestion set {suggestion_id}")
                return False
                
            # Update suggestion stats
            if selected_suggestion not in self.suggestion_stats:
                self.suggestion_stats[selected_suggestion] = {
                    "count": 0,
                    "topics": {},
                    "agreements": {},
                    "languages": {}
                }
                
            # Increment count
            self.suggestion_stats[selected_suggestion]["count"] += 1
            
            # Update topics
            for topic in suggestion_data.get("topics", []):
                if topic not in self.suggestion_stats[selected_suggestion]["topics"]:
                    self.suggestion_stats[selected_suggestion]["topics"][topic] = 0
                self.suggestion_stats[selected_suggestion]["topics"][topic] += 1
                
            # Update agreements
            agreement = suggestion_data.get("selected_agreement")
            if agreement:
                if agreement not in self.suggestion_stats[selected_suggestion]["agreements"]:
                    self.suggestion_stats[selected_suggestion]["agreements"][agreement] = 0
                self.suggestion_stats[selected_suggestion]["agreements"][agreement] += 1
                
            # Update languages
            language = suggestion_data.get("language")
            if language:
                if language not in self.suggestion_stats[selected_suggestion]["languages"]:
                    self.suggestion_stats[selected_suggestion]["languages"][language] = 0
                self.suggestion_stats[selected_suggestion]["languages"][language] += 1
                
            # Save suggestion stats
            self._save_db(self.suggestion_stats, self.suggestion_stats_path)
            
            return True
        except Exception as e:
            logger.error(f"Error tracking suggestion usage: {str(e)}")
            return False
            
    def get_suggestion_stats(self) -> Dict[str, Any]:
        """
        Get statistics about suggestion usage.
        
        Returns:
            Dict[str, Any]: Dictionary containing suggestion usage statistics.
        """
        try:
            # Calculate total suggestions used
            total_suggestions_used = sum(data["count"] for data in self.suggestion_stats.values())
            unique_suggestions = len(self.suggestion_stats)
            
            # Format top suggestions for the dashboard
            formatted_suggestions = []
            for suggestion, data in sorted(
                self.suggestion_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:10]:  # Limit to top 10
                # Get the top topics for this suggestion
                suggestion_topics = sorted(
                    data.get("topics", {}).items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                # Get the top languages for this suggestion
                suggestion_languages = sorted(
                    data.get("languages", {}).items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                # Get the top agreements for this suggestion
                suggestion_agreements = sorted(
                    data.get("agreements", {}).items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                formatted_suggestions.append({
                    "suggestion": suggestion,
                    "count": data["count"],
                    "topics": [topic for topic, _ in suggestion_topics],
                    "primary_language": suggestion_languages[0][0] if suggestion_languages else "unknown",
                    "primary_agreement": suggestion_agreements[0][0] if suggestion_agreements else None
                })
            
            # Aggregate topics across all suggestions
            topic_counts = {}
            for suggestion, data in self.suggestion_stats.items():
                for topic, count in data.get("topics", {}).items():
                    if topic not in topic_counts:
                        topic_counts[topic] = 0
                    topic_counts[topic] += count
            
            # Format top topics for the dashboard
            formatted_topics = []
            for topic, count in sorted(
                topic_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]:  # Limit to top 5
                formatted_topics.append({
                    "topic": topic,
                    "count": count,
                    "percentage": round((count / total_suggestions_used) * 100, 1) if total_suggestions_used > 0 else 0
                })
            
            # Calculate usage rate (percentage of suggestions that have been used)
            usage_rate = 0
            if len(self.suggestions_db) > 0:
                total_generated = sum(len(data.get("suggestions", [])) for data in self.suggestions_db.values())
                if total_generated > 0:
                    usage_rate = round((total_suggestions_used / total_generated) * 100, 1)
            
            # Get agreement distribution
            agreement_counts = {}
            for suggestion, data in self.suggestion_stats.items():
                for agreement, count in data.get("agreements", {}).items():
                    if agreement not in agreement_counts:
                        agreement_counts[agreement] = 0
                    agreement_counts[agreement] += count
            
            # Format agreement distribution
            formatted_agreements = []
            for agreement, count in sorted(
                agreement_counts.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                formatted_agreements.append({
                    "agreement": agreement,
                    "count": count,
                    "percentage": round((count / total_suggestions_used) * 100, 1) if total_suggestions_used > 0 else 0
                })
            
            return {
                "total_suggestions_used": total_suggestions_used,
                "unique_suggestions": unique_suggestions,
                "usage_rate": usage_rate,
                "top_suggestions": formatted_suggestions,
                "top_topics": formatted_topics,
                "agreement_distribution": formatted_agreements,
                "most_popular_topic": formatted_topics[0]["topic"] if formatted_topics else "None"
            }
        except Exception as e:
            logger.error(f"Error getting suggestion stats: {str(e)}")
            return {
                "total_suggestions_used": 0,
                "unique_suggestions": 0,
                "usage_rate": 0,
                "top_suggestions": [],
                "top_topics": [],
                "agreement_distribution": [],
                "most_popular_topic": "None"
            }
