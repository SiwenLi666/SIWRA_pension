"""
Script to visualize the pension advisor workflow using Graphviz.
"""
import os
import sys
from graphviz import Digraph
from src.multi_agent_graph import AgentState

# Set console to UTF-8 mode
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def create_workflow_visualization(filename="workflow"):
    """Create a visual representation of the workflow."""
    dot = Digraph(comment='Multi-Agent Pension Advisor Workflow')
    dot.attr(rankdir='TB')  # Top to bottom layout
    
    # Node styling
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
    
    # Define agent clusters
    with dot.subgraph(name='cluster_0') as c:
        c.attr(label='Conversational Agent', style='rounded', color='lightblue')
        c.node('gather_info', 'Gather Information', fillcolor='#E3F2FD')
        c.node('needs_more_info', 'Needs More Info?', shape='diamond', fillcolor='#BBDEFB')
    
    with dot.subgraph(name='cluster_1') as c:
        c.attr(label='Pension Analyst Agent', style='rounded', color='lightgreen')
        c.node('analyze_needs', 'Analyze Needs', fillcolor='#E8F5E9')
        c.node('generate_advice', 'Generate Advice', fillcolor='#C8E6C9')
    
    with dot.subgraph(name='cluster_2') as c:
        c.attr(label='Calculation Agent', style='rounded', color='lightyellow')
        c.node('calculate', 'Calculate Pension', fillcolor='#FFF9C4')
        c.node('needs_recalc', 'Needs Recalculation?', shape='diamond', fillcolor='#FFF59D')
    
    with dot.subgraph(name='cluster_3') as c:
        c.attr(label='Error Analyzer', style='rounded', color='lightpink')
        c.node('analyze_error', 'Analyze Error', fillcolor='#FFCDD2')
        c.node('error_type', 'Error Type?', shape='diamond', fillcolor='#EF9A9A')
        c.node('presentation_db', 'Presentation\nDatabase', shape='cylinder', fillcolor='#F8BBD0')
    
    # Add start and end nodes
    dot.node('start', 'Start', shape='circle', fillcolor='#E0E0E0')
    dot.node('end', 'End', shape='circle', fillcolor='#E0E0E0')
    
    # Add edges
    # Starting flow
    dot.edge('start', 'gather_info', 'Begin Conversation')
    
    # Conversational loop
    dot.edge('gather_info', 'needs_more_info', 'Check Info')
    dot.edge('needs_more_info', 'gather_info', 'Yes', color='blue')
    dot.edge('needs_more_info', 'analyze_needs', 'No\nInfo Complete', color='green')
    
    # Analysis and calculation flow
    dot.edge('analyze_needs', 'calculate', 'Process Numbers')
    dot.edge('calculate', 'generate_advice', 'Prepare Report')
    dot.edge('generate_advice', 'needs_recalc', 'Check if Updates Needed')
    
    # Feedback loop
    dot.edge('needs_recalc', 'calculate', 'Yes\nAdjust Numbers', color='blue')
    dot.edge('needs_recalc', 'end', 'No\nAdvice Complete', color='green')
    
    # Error handling flow
    dot.edge('gather_info', 'analyze_error', 'Error', color='red', style='dashed')
    dot.edge('analyze_needs', 'analyze_error', 'Error', color='red', style='dashed')
    dot.edge('calculate', 'analyze_error', 'Error', color='red', style='dashed')
    dot.edge('generate_advice', 'analyze_error', 'Error', color='red', style='dashed')
    
    # Error analysis flow
    dot.edge('analyze_error', 'error_type', 'Classify Error')
    dot.edge('error_type', 'gather_info', 'Missing Info', color='blue')
    dot.edge('error_type', 'calculate', 'Calculation Error', color='orange')
    dot.edge('error_type', 'end', 'System Error', color='red')
    
    # Presentation database interaction
    dot.edge('error_type', 'presentation_db', 'Update Factors', style='dotted')
    dot.edge('presentation_db', 'gather_info', 'Guide Questions', style='dotted')
    
    # Cost tracking note
    dot.attr(label='Cost tracking and error analysis active for all operations', labelloc='t', fontsize='14')
    
    # Save the visualization
    dot.render(filename, format='png', cleanup=True)
    print(f"Workflow visualization saved as {filename}.png")

def main():
    """Create the workflow visualization."""
    create_workflow_visualization("multi_agent_workflow")
    print("\nVisualization created! The workflow shows:")
    print("1. Conversational Agent: Gathers user information through natural dialogue")
    print("2. Pension Analyst Agent: Analyzes needs and generates professional advice")
    print("3. Calculation Agent: Handles numerical computations and adjustments")
    print("4. Error Analyzer: Analyzes errors and updates presentation database")
    print("5. Cost tracking is active across all operations")
    print("\nKey features:")
    print("- Information gathering loop until all required data is collected")
    print("- Calculation feedback loop for adjusting numbers")
    print("- Error handling for all agent operations")
    print("- Error analysis and presentation database interaction")
    print("- Cost tracking and budget monitoring")

if __name__ == "__main__":
    main()
