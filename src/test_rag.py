"""
Test script for the pension advisor RAG system.
"""
from agent import PensionAdvisor

def test_basic_questions():
    """Test basic questions about pension agreements."""
    advisor = PensionAdvisor()
    
    questions = [
        "What is AKAP-KR and when did it come into effect?",
        "What are the main benefits provided under AKAP-KR?",
        "How is the pension calculated and what factors affect it?",
        "What happens to the pension if someone changes employers?",
        "What are the requirements for receiving pension benefits?"
    ]
    
    print("Testing basic pension agreement questions:")
    print("----------------------------------------")
    
    for question in questions:
        print(f"\nQ: {question}")
        print("A:", advisor.ask(question))
        print("----------------------------------------")

def test_specific_scenarios():
    """Test more specific scenarios and edge cases."""
    advisor = PensionAdvisor()
    
    scenarios = [
        "If someone works part-time, how does that affect their pension under AKAP-KR?",
        "What happens to the pension if someone takes parental leave?",
        "Can you explain the process for early retirement under AKAP-KR?",
        "What options are available for managing pension investments?",
        "How are survivor benefits handled under AKAP-KR?"
    ]
    
    print("\nTesting specific scenarios:")
    print("----------------------------------------")
    
    for scenario in scenarios:
        print(f"\nQ: {scenario}")
        print("A:", advisor.ask(scenario))
        print("----------------------------------------")

if __name__ == "__main__":
    print("Starting RAG system tests...")
    test_basic_questions()
    test_specific_scenarios() 