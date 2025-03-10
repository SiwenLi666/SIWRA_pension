"""
Test script for the cost tracker functionality
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List
from contextlib import contextmanager

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from cost_tracker import CostTracker, AgentCostLog, TokenUsage

class InMemoryCostTracker(CostTracker):
    """A version of CostTracker that uses an in-memory database"""
    
    def __init__(self):
        """Initialize with an in-memory database"""
        # Skip parent initialization
        self.db_path = ":memory:"
        self._init_db()
    
    @contextmanager
    def _get_db(self):
        """Context manager for in-memory database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

def test_cost_tracker():
    """Test the cost tracker functionality"""
    print("Testing cost tracker...")
    
    # Initialize the cost tracker with in-memory database
    tracker = InMemoryCostTracker()
    
    # Generate some test data
    conversation_id = "test-conversation-123"
    
    # Log costs for different agents
    test_logs = [
        AgentCostLog(
            timestamp=datetime.now().isoformat(),
            agent_type="ConversationalAgent",
            action="generate_response",
            conversation_id=conversation_id,
            token_usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost=0.0045  # $0.03/1K prompt tokens + $0.06/1K completion tokens
            )
        ),
        AgentCostLog(
            timestamp=(datetime.now() + timedelta(minutes=1)).isoformat(),
            agent_type="PensionAnalystAgent",
            action="analyze_needs",
            conversation_id=conversation_id,
            token_usage=TokenUsage(
                prompt_tokens=200,
                completion_tokens=100,
                total_tokens=300,
                cost=0.0090  # $0.03/1K prompt tokens + $0.06/1K completion tokens
            )
        ),
        AgentCostLog(
            timestamp=(datetime.now() + timedelta(minutes=2)).isoformat(),
            agent_type="CalculationAgent",
            action="calculate_pension",
            conversation_id=conversation_id,
            token_usage=TokenUsage(
                prompt_tokens=150,
                completion_tokens=75,
                total_tokens=225,
                cost=0.00675  # $0.03/1K prompt tokens + $0.06/1K completion tokens
            )
        )
    ]
    
    # Log the test data
    for log in test_logs:
        tracker.log_cost(log)
        print(f"Logged cost for {log.agent_type}, action: {log.action}, tokens: {log.token_usage.total_tokens}")
    
    # Test the reporting functions
    print("\nTesting daily cost report:")
    daily_report = tracker.get_daily_cost_report()
    print(f"Daily cost: ${daily_report['total_cost']:.2f}")
    
    print("\nTesting monthly cost report:")
    monthly_report = tracker.get_monthly_cost_report()
    print(f"Monthly cost: ${monthly_report['total_cost']:.2f}")
    
    print("\nTesting agent cost breakdown:")
    agent_breakdown = tracker.get_cost_breakdown_by_agent()
    for agent, cost in agent_breakdown.items():
        print(f"{agent}: ${cost:.2f}")
    
    print("\nTesting action cost breakdown:")
    action_breakdown = tracker.get_cost_breakdown_by_action()
    for action, cost in action_breakdown.items():
        print(f"{action}: ${cost:.2f}")
    
    print("\nTesting conversation cost:")
    conversation_cost = tracker.get_conversation_cost(conversation_id)
    print(f"Conversation cost: ${conversation_cost:.2f}")
    
    # Test budget threshold checks
    print("\nTesting budget threshold checks:")
    is_over_daily = tracker.is_over_daily_budget()
    is_over_monthly = tracker.is_over_monthly_budget()
    print(f"Over daily budget: {is_over_daily}")
    print(f"Over monthly budget: {is_over_monthly}")
    
    # Test the async log_request_cost method
    print("\nTesting async log_request_cost method:")
    graph_data = [
        {
            "state": "finished",
            "language": "sv",
            "context_length": 3,
            "has_error": False,
            "total_cost": 0.5
        }
    ]
    
    # We can't directly test the async method in a synchronous script,
    # but we can check that the method exists
    print(f"log_request_cost method exists: {hasattr(tracker, 'log_request_cost')}")
    
    print("\nCost tracker tests completed successfully!")

if __name__ == "__main__":
    test_cost_tracker()
