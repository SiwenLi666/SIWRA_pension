"""
Generate a static visualization of the LangGraph structure.
This script creates a visual representation of the pension advisor graph
without requiring the full web application to be running.
"""

import os
from pathlib import Path
import networkx as nx
from pyvis.network import Network

# Import BASE_DIR from config
try:
    from src.utils.config import BASE_DIR
except ImportError:
    # Fallback if import fails
    BASE_DIR = Path(__file__).parent

def generate_graph_visualization(output_file="pension_graph.html"):
    """
    Generate a static visualization of the LangGraph structure.
    
    Args:
        output_file: Name of the output HTML file
    
    Returns:
        Path to the generated visualization file
    """
    print("Creating visualization of the LangGraph structure...")
    
    # Create output directory if it doesn't exist
    output_dir = Path(BASE_DIR) / "static" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a network graph
    net = Network(height="800px", width="100%", directed=True, notebook=False, heading="Pension Advisor LangGraph")
    net.set_options("""
    {
      "nodes": {
        "font": {
          "size": 20,
          "face": "Tahoma"
        },
        "shape": "box",
        "shadow": true
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 1
          }
        },
        "color": {
          "inherit": false
        },
        "smooth": {
          "type": "curvedCW",
          "forceDirection": "none"
        }
      },
      "physics": {
        "barnesHut": {
          "springLength": 250,
          "avoidOverlap": 0.5
        },
        "minVelocity": 0.75
      }
    }
    """)
    
    # Define node colors
    node_colors = {
        "generate_answer": "#4CAF50",  # Green
        "refine_answer": "#2196F3",    # Blue
        "ask_for_missing_fields": "#FFC107",  # Amber
        "END": "#E91E63"  # Pink
    }
    
    # Add nodes based on the actual structure in pension_graph.py
    print("Adding nodes for LangGraph visualization...")
    nodes = ["generate_answer", "refine_answer", "ask_for_missing_fields", "END"]
    
    for node_name in nodes:
        color = node_colors.get(node_name, "#9C27B0")  # Default purple
        title = f"Node: {node_name}"
        
        if node_name == "generate_answer":
            title = "Generates initial answer using AnswerAgent"
        elif node_name == "refine_answer":
            title = "Refines answer using RefinerAgent"
        elif node_name == "ask_for_missing_fields":
            title = "Checks for missing information using MissingFieldsAgent"
        
        net.add_node(node_name, label=node_name, color=color, title=title)
    
    # Add edges based on the actual structure in pension_graph.py
    print("Adding edges for LangGraph visualization...")
    
    # Conditional edges from generate_answer
    net.add_edge("generate_answer", "refine_answer", label="needs refinement", color="#FF5722")
    net.add_edge("generate_answer", "ask_for_missing_fields", label="final answer", color="#009688")
    
    # Direct edge from refine_answer to ask_for_missing_fields
    net.add_edge("refine_answer", "ask_for_missing_fields", color="#3F51B5")
    
    # Final edge to END
    net.add_edge("ask_for_missing_fields", "END", color="#9C27B0")
    
    # Save the visualization
    output_path = output_dir / output_file
    net.save_graph(str(output_path))
    print(f"LangGraph visualization saved to: {output_path}")
    
    # Create a visualization for the calculation agent
    print("Creating calculation agent visualization...")
    calc_net = Network(height="800px", width="100%", directed=True, notebook=False, heading="Pension Calculation Agent")
    calc_net.set_options("""
    {
      "nodes": {
        "font": {
          "size": 18,
          "face": "Tahoma"
        },
        "shape": "box",
        "shadow": true
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true
          }
        },
        "smooth": true
      }
    }
    """)
    
    # Define calculation agent components based on memory
    calc_components = [
        ("Intent Detection", "Core Calculation Engine"),
        ("Core Calculation Engine", "Formula Implementation"),
        ("Core Calculation Engine", "Parameter Validation"),
        ("Data Extraction System", "Core Calculation Engine"),
        ("Parameter Validation", "Calculation Results"),
        ("Formula Implementation", "Calculation Results"),
        ("Calculation Results", "User Interface")
    ]
    
    # Add nodes with descriptions
    calc_descriptions = {
        "Intent Detection": "Detects calculation-related questions",
        "Core Calculation Engine": "Implements pension calculation formulas",
        "Formula Implementation": "Formulas for different pension agreements (ITP1, ITP2, SAF-LO, PA16)",
        "Parameter Validation": "Validates input parameters and handles errors",
        "Data Extraction System": "Extracts calculation parameters from documents",
        "Calculation Results": "Processes and formats calculation results",
        "User Interface": "Visualizes calculation results and scenarios"
    }
    
    # Add nodes
    calc_nodes = set([node for edge in calc_components for node in edge])
    for node in calc_nodes:
        calc_net.add_node(node, label=node, title=calc_descriptions.get(node, ""), color="#009688")
        
    # Add edges
    for source, target in calc_components:
        calc_net.add_edge(source, target, arrows="to")
    
    # Save the calculation visualization
    calc_path = output_dir / "calculation_agent.html"
    calc_net.save_graph(str(calc_path))
    print(f"Calculation agent visualization saved to: {calc_path}")
    
    # Also create a visualization based on the workflow diagram from memory
    print("Creating workflow visualization...")
    workflow_net = Network(height="800px", width="100%", directed=True, notebook=False, heading="Pension Advisor Workflow")
    workflow_net.set_options("""
    {
      "nodes": {
        "font": {
          "size": 18,
          "face": "Tahoma"
        },
        "shape": "box",
        "shadow": true
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true
          }
        },
        "smooth": true
      },
      "physics": {
        "barnesHut": {
          "springLength": 200,
          "avoidOverlap": 0.5
        }
      }
    }
    """)
    
    # Define the workflow based on the memory
    workflow = [
        ("User Interaction", "Document Loading"),
        ("Document Loading", "Embeddings Creation"),
        ("Embeddings Creation", "Querying Process"),
        ("User Query", "Querying Process"),
        ("Querying Process", "Response Generation"),
        ("Response Generation", "Feedback Loop"),
        ("Feedback Loop", "User Interaction")
    ]
    
    # Add nodes with descriptions
    workflow_descriptions = {
        "User Interaction": "User selects an agreement type",
        "Document Loading": "DocumentProcessor loads documents from the selected agreement folder",
        "Embeddings Creation": "System creates embeddings from the loaded documents",
        "User Query": "User asks a question related to the agreement",
        "Querying Process": "System queries the embeddings related to the selected agreement",
        "Response Generation": "Agent generates a response based on the relevant documents",
        "Feedback Loop": "Agent retains the selected agreement in memory for ongoing conversation"
    }
    
    # Add nodes
    workflow_nodes = set([node for edge in workflow for node in edge])
    for node in workflow_nodes:
        workflow_net.add_node(node, label=node, title=workflow_descriptions.get(node, ""), color="#2196F3")
        
    # Add edges
    for source, target in workflow:
        workflow_net.add_edge(source, target, arrows="to")
    
    # Save the workflow visualization
    workflow_path = output_dir / "pension_workflow.html"
    workflow_net.save_graph(str(workflow_path))
    print(f"Workflow visualization saved to: {workflow_path}")
    
    print(f"\nAll visualizations saved to:\n- {output_path}\n- {calc_path}\n- {workflow_path}")
    return str(output_path)
    
    # Save the visualization
    output_path = output_dir / output_file
    net.save_graph(str(output_path))
    
    print(f"Visualization saved to: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    # Remove dependency on create_pension_graph
    try:
        output_path = generate_graph_visualization()
        print(f"\nTo view the visualizations, open these files in your browser:")
        print(f"1. LangGraph Structure: {output_path}")
        print(f"2. Calculation Agent: {Path(output_path).parent / 'calculation_agent.html'}")
        print(f"3. Workflow Diagram: {Path(output_path).parent / 'pension_workflow.html'}")
    except Exception as e:
        print(f"Error generating visualizations: {e}")
        print("Please check that all required libraries are installed.")
