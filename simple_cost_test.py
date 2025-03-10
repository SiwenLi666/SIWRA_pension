"""
Simple test for the cost tracker functionality
"""
import os
import sys
from datetime import datetime

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from cost_tracker import cost_tracker, AgentCostLog, TokenUsage

# Use the global cost_tracker instance
print("Testing the global cost tracker instance...")

# Create a test log entry
test_log = AgentCostLog(
    timestamp=datetime.now().isoformat(),
    agent_type="TestAgent",
    action="test_action",
    conversation_id="test-conversation-123",
    token_usage=TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.0045
    )
)

# Log the cost
print("Logging a test cost entry...")
cost_tracker.log_cost(test_log)
print("Cost entry logged successfully!")

# Get daily cost
print("\nDaily cost report:")
daily_cost = cost_tracker.get_cost_for_period("today")
print(f"Total cost today: ${daily_cost:.4f}")

# Get monthly cost
print("\nMonthly cost report:")
monthly_cost = cost_tracker.get_cost_for_period("month")
print(f"Total cost this month: ${monthly_cost:.4f}")

# Get usage report
print("\nUsage report:")
usage_report = cost_tracker.get_usage_report("today")
print(f"Usage report: {usage_report}")

print("\nTest completed successfully!")
