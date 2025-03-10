"""
CLI tool for viewing cost reports and usage statistics.
"""
import argparse
from datetime import datetime
import json
from src.cost_tracker import cost_tracker

def format_cost(cost: float) -> str:
    """Format cost in dollars"""
    return f"${cost:.2f}"

def print_report(report: dict, period: str):
    """Print a formatted cost report"""
    print(f"\n=== Cost Report for {period.title()} ===\n")
    
    # Print agent costs
    print("Agent Usage:")
    print("-" * 80)
    print(f"{'Agent Type':<20} {'Calls':<8} {'Tokens':<10} {'Cost':<10}")
    print("-" * 80)
    for agent in report['agent_costs']:
        print(
            f"{agent['agent_type']:<20} "
            f"{agent['total_calls']:<8} "
            f"{agent['total_tokens']:<10} "
            f"{format_cost(agent['total_cost']):<10}"
        )
    
    # Print action costs
    print("\nAction Usage:")
    print("-" * 80)
    print(f"{'Action':<30} {'Calls':<8} {'Tokens':<10} {'Cost':<10}")
    print("-" * 80)
    for action in report['action_costs']:
        print(
            f"{action['action']:<30} "
            f"{action['total_calls']:<8} "
            f"{action['total_tokens']:<10} "
            f"{format_cost(action['total_cost']):<10}"
        )
    
    # Print totals
    total_cost = sum(agent['total_cost'] for agent in report['agent_costs'])
    total_tokens = sum(agent['total_tokens'] for agent in report['agent_costs'])
    total_calls = sum(agent['total_calls'] for agent in report['agent_costs'])
    
    print("\nSummary:")
    print("-" * 80)
    print(f"Total Cost: {format_cost(total_cost)}")
    print(f"Total Tokens: {total_tokens:,}")
    print(f"Total API Calls: {total_calls}")
    
    # Check budget status
    if period == "today":
        daily_budget = 5.0
        remaining = daily_budget - total_cost
        print(f"\nDaily Budget Remaining: {format_cost(remaining)}")
        if remaining < 1.0:
            print("⚠️  Warning: Daily budget is running low!")
    elif period == "month":
        monthly_budget = 100.0
        remaining = monthly_budget - total_cost
        print(f"\nMonthly Budget Remaining: {format_cost(remaining)}")
        if remaining < 20.0:
            print("⚠️  Warning: Monthly budget is running low!")

def main():
    parser = argparse.ArgumentParser(description="View cost reports for the pension advisor")
    parser.add_argument(
        "--period",
        choices=["today", "month", "all"],
        default="today",
        help="Time period for the report"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format"
    )
    
    args = parser.parse_args()
    
    # Get the report
    report = cost_tracker.get_usage_report(args.period)
    
    # Output based on format
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args.period)

if __name__ == "__main__":
    main()
