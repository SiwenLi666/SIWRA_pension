"""
Track and monitor API costs for the pension advisor system.
"""
import sqlite3
from pathlib import Path
import logging
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime, date
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@dataclass
class TokenUsage:
    """Track token usage for a single API call"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float

@dataclass
class AgentCostLog:
    """Log entry for agent API usage"""
    timestamp: datetime
    agent_type: str  # conversational, analyst, calculation
    action: str  # e.g., "generate_response", "analyze_needs"
    token_usage: TokenUsage
    conversation_id: str

class CostTracker:
    def __init__(self, db_path: str = "data/costs.db"):
        """Initialize the cost tracker"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema"""
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    agent_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    cost REAL NOT NULL,
                    conversation_id TEXT NOT NULL
                )
            """)

    @contextmanager
    def _get_db(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def log_cost(self, cost_log: AgentCostLog):
        """Log a cost entry to the database"""
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO cost_logs 
                (timestamp, agent_type, action, prompt_tokens, completion_tokens, 
                 total_tokens, cost, conversation_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cost_log.timestamp,
                cost_log.agent_type,
                cost_log.action,
                cost_log.token_usage.prompt_tokens,
                cost_log.token_usage.completion_tokens,
                cost_log.token_usage.total_tokens,
                cost_log.token_usage.cost,
                cost_log.conversation_id
            ))

    async def log_request_cost(self, graph_data: List[Dict]):
        """Log costs from a graph execution"""
        try:
            for step in graph_data:
                # Extract cost data from graph step
                if "token_usage" in step:
                    usage = step["token_usage"]
                    cost_log = AgentCostLog(
                        timestamp=datetime.now(),
                        agent_type=step.get("agent_type", "unknown"),
                        action=step.get("action", "unknown"),
                        token_usage=TokenUsage(
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                            total_tokens=usage.get("total_tokens", 0),
                            cost=usage.get("cost", 0.0)
                        ),
                        conversation_id=step.get("conversation_id", "unknown")
                    )
                    self.log_cost(cost_log)
                    
                    # Check budget thresholds
                    await self._check_budget_thresholds()

        except Exception as e:
            logger.error(f"Error logging request cost: {e}")

    async def _check_budget_thresholds(self):
        """Check if we're approaching or exceeding budget thresholds"""
        try:
            daily_cost = self.get_cost_for_period("today")
            monthly_cost = self.get_cost_for_period("month")
            
            # Daily budget threshold ($5)
            if daily_cost > 4.5:  # 90% of daily budget
                logger.warning(f"Approaching daily budget limit! Current: ${daily_cost:.2f}")
            if daily_cost > 5.0:
                logger.error(f"Daily budget exceeded! Current: ${daily_cost:.2f}")
            
            # Monthly budget threshold ($100)
            if monthly_cost > 90:  # 90% of monthly budget
                logger.warning(f"Approaching monthly budget limit! Current: ${monthly_cost:.2f}")
            if monthly_cost > 100:
                logger.error(f"Monthly budget exceeded! Current: ${monthly_cost:.2f}")
                
        except Exception as e:
            logger.error(f"Error checking budget thresholds: {e}")

    def get_cost_for_period(self, period: str) -> float:
        """Get total cost for a specific period (today/month/all)"""
        with self._get_db() as conn:
            if period == "today":
                today = date.today()
                result = conn.execute("""
                    SELECT SUM(cost) FROM cost_logs 
                    WHERE date(timestamp) = date(?)
                """, (today.isoformat(),)).fetchone()
            elif period == "month":
                today = date.today()
                result = conn.execute("""
                    SELECT SUM(cost) FROM cost_logs 
                    WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', ?)
                """, (today.isoformat(),)).fetchone()
            else:  # all time
                result = conn.execute("""
                    SELECT SUM(cost) FROM cost_logs
                """).fetchone()
            
            return result[0] or 0.0

    def get_usage_report(self, period: str = "today") -> Dict:
        """Get a detailed usage report for a period"""
        with self._get_db() as conn:
            # Base query parts
            select_base = """
                SELECT agent_type, 
                       COUNT(*) as total_calls,
                       SUM(total_tokens) as total_tokens,
                       SUM(cost) as total_cost
                FROM cost_logs
            """
            
            # Add time filter if needed
            where_clause = ""
            params = ()
            if period == "today":
                where_clause = "WHERE date(timestamp) = date(?)"
                params = (date.today().isoformat(),)
            elif period == "month":
                where_clause = "WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', ?)"
                params = (date.today().isoformat(),)
            
            # Get agent costs
            agent_costs = []
            for row in conn.execute(f"""
                {select_base}
                {where_clause}
                GROUP BY agent_type
                ORDER BY total_cost DESC
            """, params):
                agent_costs.append({
                    "agent_type": row[0],
                    "total_calls": row[1],
                    "total_tokens": row[2],
                    "total_cost": row[3]
                })
            
            # Get action costs
            action_costs = []
            for row in conn.execute(f"""
                {select_base}
                {where_clause}
                GROUP BY action
                ORDER BY total_cost DESC
            """, params):
                action_costs.append({
                    "action": row[0],
                    "total_calls": row[1],
                    "total_tokens": row[2],
                    "total_cost": row[3]
                })
            
            return {
                "period": period,
                "agent_costs": agent_costs,
                "action_costs": action_costs
            }

# Global instance
cost_tracker = CostTracker()
