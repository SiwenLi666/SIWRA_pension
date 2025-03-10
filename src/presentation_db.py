"""
Database for storing and managing presentation factors and common information patterns.
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from contextlib import contextmanager
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class InformationFactor:
    """Represents an important information factor for pension advising"""
    category: str  # e.g., "personal", "employment", "financial", "goals"
    name: str
    description: str
    importance: int  # 1-5
    question_templates: List[str]
    related_factors: List[str]
    frequency: int = 0  # How often this factor comes up

class PresentationDatabase:
    def __init__(self, db_path: str = "data/presentation.db"):
        """Initialize the presentation database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema"""
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS information_factors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    question_templates TEXT NOT NULL,
                    related_factors TEXT NOT NULL,
                    frequency INTEGER DEFAULT 0,
                    UNIQUE(category, name)
                )
            """)
            
            # Add some initial factors if the table is empty
            if not conn.execute("SELECT 1 FROM information_factors LIMIT 1").fetchone():
                self._add_initial_factors(conn)

    def _add_initial_factors(self, conn: sqlite3.Connection):
        """Add initial information factors"""
        initial_factors = [
            InformationFactor(
                category="personal",
                name="age",
                description="Current age of the person",
                importance=5,
                question_templates=[
                    "Hur gammal är du?",
                    "När är du född?",
                    "Skulle du kunna berätta din ålder?"
                ],
                related_factors=["retirement_age", "life_expectancy"]
            ),
            InformationFactor(
                category="employment",
                name="employment_type",
                description="Type of employment (public, private, self-employed)",
                importance=5,
                question_templates=[
                    "Vilken typ av anställning har du?",
                    "Arbetar du inom offentlig eller privat sektor?",
                    "Är du egenföretagare eller anställd?"
                ],
                related_factors=["employer", "sector", "contract_type"]
            ),
            InformationFactor(
                category="financial",
                name="current_salary",
                description="Current monthly salary before tax",
                importance=5,
                question_templates=[
                    "Vad är din nuvarande månadslön före skatt?",
                    "Hur mycket tjänar du per månad?",
                    "Kan du berätta om din månadsinkomst?"
                ],
                related_factors=["bonus", "benefits", "total_compensation"]
            ),
            # Add more initial factors as needed
        ]
        
        for factor in initial_factors:
            self.add_factor(factor)

    @contextmanager
    def _get_db(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_factor(self, factor: InformationFactor):
        """Add a new information factor to the database"""
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO information_factors 
                (category, name, description, importance, question_templates, 
                 related_factors, frequency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                factor.category,
                factor.name,
                factor.description,
                factor.importance,
                json.dumps(factor.question_templates),
                json.dumps(factor.related_factors),
                factor.frequency
            ))

    def get_missing_factors(self, user_profile: Dict) -> List[InformationFactor]:
        """Get a list of important factors that are missing from the user profile"""
        with self._get_db() as conn:
            all_factors = conn.execute("""
                SELECT * FROM information_factors 
                ORDER BY importance DESC, frequency DESC
            """).fetchall()
            
            missing_factors = []
            for row in all_factors:
                factor_name = row[2]  # name column
                if factor_name not in user_profile or not user_profile[factor_name]:
                    missing_factors.append(InformationFactor(
                        category=row[1],
                        name=row[2],
                        description=row[3],
                        importance=row[4],
                        question_templates=json.loads(row[5]),
                        related_factors=json.loads(row[6]),
                        frequency=row[7]
                    ))
            
            return missing_factors

    def increment_factor_frequency(self, factor_name: str):
        """Increment the frequency counter for a factor"""
        with self._get_db() as conn:
            conn.execute("""
                UPDATE information_factors 
                SET frequency = frequency + 1 
                WHERE name = ?
            """, (factor_name,))

    def get_question_templates(self, factor_name: str) -> List[str]:
        """Get question templates for a specific factor"""
        with self._get_db() as conn:
            row = conn.execute("""
                SELECT question_templates 
                FROM information_factors 
                WHERE name = ?
            """, (factor_name,)).fetchone()
            
            return json.loads(row[0]) if row else []

    def add_question_template(self, factor_name: str, template: str):
        """Add a new question template for a factor"""
        with self._get_db() as conn:
            current = conn.execute("""
                SELECT question_templates 
                FROM information_factors 
                WHERE name = ?
            """, (factor_name,)).fetchone()
            
            if current:
                templates = json.loads(current[0])
                if template not in templates:
                    templates.append(template)
                    conn.execute("""
                        UPDATE information_factors 
                        SET question_templates = ? 
                        WHERE name = ?
                    """, (json.dumps(templates), factor_name))

# Global instance
presentation_db = PresentationDatabase()
