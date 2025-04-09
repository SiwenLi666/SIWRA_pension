"""
LangGraph Visualization Module

This module provides visualization capabilities for LangGraph agent workflows,
allowing real-time monitoring and debugging of agent states and transitions.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network
from langgraph.graph import StateGraph

from src.utils.config import BASE_DIR

logger = logging.getLogger('langgraph_visualization')

class LangGraphVisualizer:
    """
    A class to visualize LangGraph agent workflows and state transitions.
    """
    
    def __init__(self, graph: StateGraph, output_dir: Optional[str] = None):
        """
        Initialize the LangGraph visualizer.
        
        Args:
            graph: The compiled LangGraph StateGraph
            output_dir: Directory to save visualization files (defaults to static/visualizations)
        """
        self.graph = graph
        self.output_dir = output_dir or str(Path(BASE_DIR) / "static" / "visualizations")
        self.state_history = []
        self.node_colors = {
            "generate_answer": "#4CAF50",  # Green
            "refine_answer": "#2196F3",    # Blue
            "ask_for_missing_fields": "#FFC107"  # Amber
        }
        
        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def capture_state(self, state: Dict[str, Any]) -> None:
        """
        Capture a state snapshot for visualization.
        
        Args:
            state: The current state dictionary
        """
        self.state_history.append(state.copy())
        
    def generate_static_graph(self, filename: str = "agent_graph.html") -> str:
        """
        Generate a static visualization of the agent graph structure.
        
        Args:
            filename: Output filename for the visualization
            
        Returns:
            Path to the generated visualization file
        """
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
        
        # Define nodes and edges based on the pension graph structure
        # This is hardcoded based on the structure in pension_graph.py
        nodes = ["generate_answer", "refine_answer", "ask_for_missing_fields", "END"]
        
        # Add nodes
        for node_name in nodes:
            if node_name == "END":
                net.add_node(node_name, label="END", color="#E91E63")  # Pink
            else:
                color = self.node_colors.get(node_name, "#9C27B0")  # Default purple
                title = f"Node: {node_name}"
                
                if node_name == "generate_answer":
                    title = "Generates initial answer using AnswerAgent"
                elif node_name == "refine_answer":
                    title = "Refines answer using RefinerAgent"
                elif node_name == "ask_for_missing_fields":
                    title = "Checks for missing information using MissingFieldsAgent"
                
                net.add_node(node_name, label=node_name, color=color, title=title)
        
        # Add edges based on the pension_graph.py structure
        edges = [
            ("generate_answer", "refine_answer"),
            ("generate_answer", "ask_for_missing_fields"),
            ("refine_answer", "ask_for_missing_fields"),
            ("ask_for_missing_fields", "END")
        ]
        
        # Add edges
        for source, target in edges:
            if source == "generate_answer" and target == "refine_answer":
                net.add_edge(source, target, label="needs refinement", color="#FF5722")
            elif source == "generate_answer" and target == "ask_for_missing_fields":
                net.add_edge(source, target, label="final answer", color="#009688")
            else:
                net.add_edge(source, target, arrows="to")
        
        # Save the visualization
        output_path = Path(self.output_dir) / filename
        net.save_graph(str(output_path))
        
        return str(output_path)
    
    def generate_state_flow(self, filename: str = "state_flow.html") -> str:
        """
        Generate a visualization of the state flow during execution.
        
        Args:
            filename: Output filename for the visualization
            
        Returns:
            Path to the generated visualization file
        """
        if not self.state_history:
            logger.warning("No state history captured. Run the graph with capture_state first.")
            return ""
        
        # Create a network graph for state flow
        net = Network(height="800px", width="100%", directed=True, notebook=False)
        
        # Add nodes for each state transition
        for i, state in enumerate(self.state_history):
            node_id = f"state_{i}"
            label = f"State {i}"
            
            # Extract the current agent/node if available
            current_node = state.get("current_node", "unknown")
            if current_node in self.node_colors:
                color = self.node_colors[current_node]
            else:
                color = "#9E9E9E"  # Gray for unknown
                
            # Add node with state information
            state_info = {k: v for k, v in state.items() if k not in ['token_usage', 'conversation_history']}
            net.add_node(node_id, label=label, title=json.dumps(state_info, indent=2), color=color)
            
            # Add edge to previous state
            if i > 0:
                net.add_edge(f"state_{i-1}", node_id, arrows="to")
        
        # Save the visualization
        output_path = Path(self.output_dir) / filename
        net.save_graph(str(output_path))
        
        return str(output_path)
    
    def create_dashboard(self, filename: str = "langgraph_dashboard.html") -> str:
        """
        Create a comprehensive dashboard with both static graph and state flow.
        
        Args:
            filename: Output filename for the dashboard
            
        Returns:
            Path to the generated dashboard file
        """
        # Generate individual visualizations
        static_graph_path = self.generate_static_graph()
        state_flow_path = self.generate_state_flow()
        
        # Create dashboard HTML
        dashboard_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LangGraph Visualization Dashboard</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ padding: 20px; }}
                .viz-container {{ height: 800px; border: 1px solid #ddd; margin-bottom: 20px; }}
                .nav-tabs {{ margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container-fluid">
                <h1>LangGraph Visualization Dashboard</h1>
                
                <ul class="nav nav-tabs" id="vizTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="static-tab" data-bs-toggle="tab" 
                                data-bs-target="#static" type="button" role="tab">Agent Graph Structure</button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="flow-tab" data-bs-toggle="tab" 
                                data-bs-target="#flow" type="button" role="tab">State Flow</button>
                    </li>
                </ul>
                
                <div class="tab-content" id="vizTabContent">
                    <div class="tab-pane fade show active" id="static" role="tabpanel">
                        <div class="viz-container">
                            <iframe src="/visualizations/{Path(static_graph_path).name}" width="100%" height="100%"></iframe>
                        </div>
                    </div>
                    <div class="tab-pane fade" id="flow" role="tabpanel">
                        <div class="viz-container">
                            <iframe src="/visualizations/{Path(state_flow_path).name}" width="100%" height="100%"></iframe>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header bg-primary text-white">
                                <h5 class="mb-0">Agent Information</h5>
                            </div>
                            <div class="card-body">
                                <p><strong>Total States:</strong> <span id="total-states">{len(self.state_history)}</span></p>
                                <p><strong>Nodes:</strong> {', '.join(n for n in self.graph.nodes if n != "__end__")}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        """
        
        # Save dashboard
        output_path = Path(self.output_dir) / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_html)
        
        return str(output_path)
