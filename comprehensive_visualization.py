"""
Comprehensive Pension Advisor System Visualization

This script generates an interactive, detailed visualization of the entire
Pension Advisor System, including all components, workflows, and relationships.
"""

import os
import json
from pathlib import Path
from pyvis.network import Network
import networkx as nx
import matplotlib.pyplot as plt

# Define the output directory
OUTPUT_DIR = Path("static/visualizations")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def create_comprehensive_visualization():
    """
    Creates a comprehensive visualization of the entire pension advisor system
    with all components, workflows, and relationships.
    """
    # Create a network graph with custom options for better visualization
    net = Network(
        height="900px", 
        width="100%", 
        directed=True, 
        notebook=False,
        heading="" # Remove the heading as we'll add a custom one in HTML
    )
    
    # Set advanced options for better visualization
    net.set_options("""
    {
      "nodes": {
        "font": {
          "size": 16,
          "face": "Tahoma"
        },
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
        "stabilization": {
          "iterations": 200,
          "fit": true
        },
        "barnesHut": {
          "springLength": 200,
          "springConstant": 0.04,
          "avoidOverlap": 0.5,
          "damping": 0.09
        },
        "minVelocity": 0.75
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "zoomView": true,
        "dragView": true,
        "navigationButtons": true,
        "keyboard": {
          "enabled": true,
          "speed": {
            "x": 10,
            "y": 10,
            "zoom": 0.1
          }
        }
      }
    }
    """)
    
    # Define system components with detailed information
    # 1. Main Agent Components
    main_agent_nodes = [
        {
            "id": "start", 
            "label": "Start", 
            "shape": "circle",
            "color": "#9E9E9E",
            "title": "Entry point for user queries",
            "group": "flow"
        },
        {
            "id": "pension_advisor", 
            "label": "Pension Advisor Agent", 
            "shape": "box",
            "color": "#4CAF50",
            "title": "Main agent that orchestrates the pension advice workflow",
            "group": "agent"
        },
        {
            "id": "generate_advice", 
            "label": "Generate Advice", 
            "shape": "box",
            "color": "#8BC34A",
            "title": "Generates initial pension advice based on user query",
            "group": "process"
        },
        {
            "id": "analyze_needs", 
            "label": "Analyze Needs", 
            "shape": "box",
            "color": "#8BC34A",
            "title": "Analyzes user's pension needs and requirements",
            "group": "process"
        },
        {
            "id": "end", 
            "label": "End", 
            "shape": "circle",
            "color": "#9E9E9E",
            "title": "Final response delivered to user",
            "group": "flow"
        }
    ]
    
    # 2. Error Handling Components
    error_nodes = [
        {
            "id": "error_analyzer", 
            "label": "Error Analyzer", 
            "shape": "box",
            "color": "#F44336",
            "title": "Analyzes and classifies errors in the system",
            "group": "error"
        },
        {
            "id": "analyze_error", 
            "label": "Analyze Error", 
            "shape": "ellipse",
            "color": "#EF9A9A",
            "title": "Processes and categorizes errors for appropriate handling",
            "group": "error"
        },
        {
            "id": "error_type", 
            "label": "Error Type?", 
            "shape": "diamond",
            "color": "#EF5350",
            "title": "Decision point for error classification",
            "group": "decision"
        }
    ]
    
    # 3. Calculation Components
    calculation_nodes = [
        {
            "id": "calculation_agent", 
            "label": "Calculation Agent", 
            "shape": "box",
            "color": "#FFC107",
            "title": "Agent responsible for pension calculations",
            "group": "agent"
        },
        {
            "id": "needs_recalculation", 
            "label": "Needs Recalculation?", 
            "shape": "diamond",
            "color": "#FFD54F",
            "title": "Decision point to determine if recalculation is needed",
            "group": "decision"
        },
        {
            "id": "adjust_numbers", 
            "label": "Adjust Numbers", 
            "shape": "box",
            "color": "#FFE082",
            "title": "Adjusts calculation parameters based on user input",
            "group": "process"
        },
        {
            "id": "calculate_pension", 
            "label": "Calculate Pension", 
            "shape": "box",
            "color": "#FFCA28",
            "title": "Performs the actual pension calculation using formulas",
            "group": "process"
        },
        {
            "id": "prepare_report", 
            "label": "Prepare Report", 
            "shape": "box",
            "color": "#FFB300",
            "title": "Formats calculation results into a readable report",
            "group": "process"
        },
        {
            "id": "process_numbers", 
            "label": "Process Numbers", 
            "shape": "box",
            "color": "#FFA000",
            "title": "Processes numerical inputs for calculation",
            "group": "process"
        }
    ]
    
    # 4. Conversation Components
    conversation_nodes = [
        {
            "id": "conversational_agent", 
            "label": "Conversational Agent", 
            "shape": "box",
            "color": "#2196F3",
            "title": "Agent that handles natural language conversation with users",
            "group": "agent"
        },
        {
            "id": "gather_information", 
            "label": "Gather Information", 
            "shape": "box",
            "color": "#90CAF9",
            "title": "Collects necessary information from the user",
            "group": "process"
        },
        {
            "id": "needs_more_info", 
            "label": "Needs More Info?", 
            "shape": "diamond",
            "color": "#64B5F6",
            "title": "Decision point to determine if more information is needed",
            "group": "decision"
        },
        {
            "id": "check_info", 
            "label": "Check Info", 
            "shape": "box",
            "color": "#42A5F5",
            "title": "Validates the information provided by the user",
            "group": "process"
        }
    ]
    
    # 5. Data Components
    data_nodes = [
        {
            "id": "presentation_db", 
            "label": "Presentation Database", 
            "shape": "database",
            "color": "#E91E63",
            "title": "Stores presentation data for user interaction",
            "group": "data"
        }
    ]
    
    # Add all nodes to the network
    all_nodes = main_agent_nodes + error_nodes + calculation_nodes + conversation_nodes + data_nodes
    for node in all_nodes:
        net.add_node(
            node["id"], 
            label=node["label"], 
            shape=node["shape"], 
            color=node["color"], 
            title=node["title"],
            group=node["group"]
        )
    
    # Define edges with descriptions
    edges = [
        # Main flow
        {"from": "start", "to": "pension_advisor", "label": "Begin Conversation", "color": "#000000"},
        {"from": "pension_advisor", "to": "generate_advice", "label": "", "color": "#4CAF50"},
        {"from": "pension_advisor", "to": "analyze_needs", "label": "", "color": "#4CAF50"},
        {"from": "generate_advice", "to": "analyze_needs", "label": "Check if Updates Needed", "color": "#4CAF50"},
        {"from": "analyze_needs", "to": "end", "label": "Advice Complete", "color": "#4CAF50", "dashes": False},
        
        # Error handling
        {"from": "start", "to": "error_analyzer", "label": "Error", "color": "#F44336", "dashes": True},
        {"from": "generate_advice", "to": "error_analyzer", "label": "Error", "color": "#F44336", "dashes": True},
        {"from": "analyze_needs", "to": "error_analyzer", "label": "Error", "color": "#F44336", "dashes": True},
        {"from": "error_analyzer", "to": "analyze_error", "label": "", "color": "#F44336"},
        {"from": "analyze_error", "to": "error_type", "label": "Classify Error", "color": "#F44336"},
        
        # Calculation flow
        {"from": "analyze_needs", "to": "calculation_agent", "label": "", "color": "#FFC107"},
        {"from": "calculation_agent", "to": "needs_recalculation", "label": "", "color": "#FFC107"},
        {"from": "needs_recalculation", "to": "adjust_numbers", "label": "Yes", "color": "#0000FF"},
        {"from": "needs_recalculation", "to": "calculate_pension", "label": "No", "color": "#FFC107"},
        {"from": "adjust_numbers", "to": "calculate_pension", "label": "", "color": "#FFC107"},
        {"from": "generate_advice", "to": "prepare_report", "label": "", "color": "#FFC107"},
        {"from": "prepare_report", "to": "calculate_pension", "label": "", "color": "#FFC107"},
        {"from": "analyze_needs", "to": "process_numbers", "label": "", "color": "#FFC107"},
        {"from": "process_numbers", "to": "calculate_pension", "label": "", "color": "#FFC107"},
        {"from": "calculate_pension", "to": "end", "label": "No", "color": "#FFC107"},
        
        # Error types
        {"from": "error_type", "to": "calculate_pension", "label": "Calculation Error", "color": "#F44336"},
        {"from": "error_type", "to": "end", "label": "System Error", "color": "#F44336"},
        
        # Conversation flow
        {"from": "start", "to": "conversational_agent", "label": "Begin Conversation", "color": "#2196F3"},
        {"from": "conversational_agent", "to": "gather_information", "label": "", "color": "#2196F3"},
        {"from": "gather_information", "to": "check_info", "label": "", "color": "#2196F3"},
        {"from": "check_info", "to": "needs_more_info", "label": "Yes", "color": "#2196F3"},
        {"from": "needs_more_info", "to": "gather_information", "label": "Yes", "color": "#0000FF"},
        {"from": "needs_more_info", "to": "end", "label": "No", "color": "#2196F3"},
        
        # Data connections
        {"from": "presentation_db", "to": "gather_information", "label": "Guide Questions", "color": "#E91E63", "dashes": True},
        {"from": "error_type", "to": "presentation_db", "label": "Update Factors", "color": "#E91E63"},
        
        # Cross-component connections
        {"from": "error_type", "to": "conversational_agent", "label": "Missing Info", "color": "#0000FF"},
        {"from": "analyze_needs", "to": "needs_more_info", "label": "", "color": "#00FF00", "dashes": True},
        {"from": "calculate_pension", "to": "analyze_error", "label": "Calculation Error", "color": "#F44336", "dashes": True},
    ]
    
    # Add all edges to the network
    for edge in edges:
        net.add_edge(
            edge["from"], 
            edge["to"], 
            label=edge["label"], 
            color=edge["color"],
            dashes=edge.get("dashes", False)
        )
    
    # Add legend nodes
    legend_y = -350
    legend_nodes = [
        {"id": "legend_agent", "label": "Agent", "shape": "box", "color": "#4CAF50", "x": -600, "y": legend_y},
        {"id": "legend_process", "label": "Process", "shape": "box", "color": "#8BC34A", "x": -500, "y": legend_y},
        {"id": "legend_decision", "label": "Decision", "shape": "diamond", "color": "#FFD54F", "x": -400, "y": legend_y},
        {"id": "legend_error", "label": "Error Handling", "shape": "box", "color": "#F44336", "x": -300, "y": legend_y},
        {"id": "legend_data", "label": "Data Store", "shape": "database", "color": "#E91E63", "x": -200, "y": legend_y},
        {"id": "legend_flow", "label": "Flow Control", "shape": "circle", "color": "#9E9E9E", "x": -100, "y": legend_y}
    ]
    
    for node in legend_nodes:
        net.add_node(
            node["id"], 
            label=node["label"], 
            shape=node["shape"], 
            color=node["color"],
            x=node["x"],
            y=node["y"],
            physics=False
        )
    
    # Save the visualization to a temporary file
    temp_path = OUTPUT_DIR / "temp_graph.html"
    net.save_graph(str(temp_path))
    
    # Read the generated HTML
    with open(temp_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Add custom controls and fix the title
    modified_html = html_content.replace(
        '<body>',
        '''
        <body>
        <div style="padding: 20px; background-color: #f8f9fa; border-bottom: 1px solid #ddd;">
            <h1 style="margin: 0; color: #333; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">Comprehensive Pension Advisor System</h1>
            <div style="margin-top: 10px;">
                <button id="physics-toggle" class="btn btn-primary" style="padding: 5px 10px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Stop Animation</button>
                <button id="reset-view" class="btn btn-secondary" style="padding: 5px 10px; background-color: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer; margin-left: 10px;">Reset View</button>
            </div>
        </div>
        ''')
    
    # Add the JavaScript for the physics toggle button
    modified_html = modified_html.replace(
        '</script>\n</head>',
        '''
        </script>
        <script type="text/javascript">
            document.addEventListener("DOMContentLoaded", function() {
                // Physics toggle button
                const physicsToggle = document.getElementById("physics-toggle");
                let physicsEnabled = true;
                
                physicsToggle.addEventListener("click", function() {
                    physicsEnabled = !physicsEnabled;
                    network.physics.enabled = physicsEnabled;
                    physicsToggle.textContent = physicsEnabled ? "Stop Animation" : "Start Animation";
                });
                
                // Reset view button
                const resetView = document.getElementById("reset-view");
                resetView.addEventListener("click", function() {
                    network.fit();
                });
            });
        </script>
        </head>''')
    
    # Write the modified HTML to the final file
    output_path = OUTPUT_DIR / "comprehensive_pension_system.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(modified_html)
    
    # Remove the temporary file
    temp_path.unlink()
    
    print(f"Comprehensive visualization saved to: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    visualization_path = create_comprehensive_visualization()
    print(f"\nTo view the visualization, open this file in your browser:\n{visualization_path}")
