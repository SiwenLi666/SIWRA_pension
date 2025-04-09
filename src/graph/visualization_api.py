"""
API endpoints for LangGraph visualization.

This module provides FastAPI endpoints for accessing the LangGraph visualization dashboard
and related visualization artifacts.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.utils.config import BASE_DIR

logger = logging.getLogger('visualization_api')

# Create router
visualization_router = APIRouter(
    prefix="/api/visualization",
    tags=["visualization"],
)

class VisualizationRequest(BaseModel):
    """Request model for generating a visualization."""
    message: str
    generate_static_graph: bool = True
    generate_state_flow: bool = True
    
class VisualizationResponse(BaseModel):
    """Response model for visualization requests."""
    dashboard_url: str
    static_graph_url: Optional[str] = None
    state_flow_url: Optional[str] = None
    message: str

@visualization_router.post("/generate", response_model=VisualizationResponse)
async def generate_visualization(request: VisualizationRequest):
    """
    Generate a visualization for a LangGraph run with the given message.
    
    Args:
        request: The visualization request
        
    Returns:
        VisualizationResponse with URLs to the generated visualizations
    """
    from main import PensionAdvisorGraph
    
    try:
        # Create a new graph instance
        graph = PensionAdvisorGraph()
        
        # Run the graph with visualization enabled
        _, final_state = graph.run_with_visualization(request.message, generate_viz=True)
        
        # Get the visualization path from the final state
        if "visualization_path" not in final_state:
            raise HTTPException(status_code=500, detail="Visualization generation failed")
        
        # Convert file paths to URLs
        dashboard_path = Path(final_state["visualization_path"])
        dashboard_url = f"/visualizations/{dashboard_path.name}"
        
        # Get static graph and state flow URLs if available
        static_graph_url = "/visualizations/agent_graph.html" if request.generate_static_graph else None
        state_flow_url = "/visualizations/state_flow.html" if request.generate_state_flow else None
        
        return VisualizationResponse(
            dashboard_url=dashboard_url,
            static_graph_url=static_graph_url,
            state_flow_url=state_flow_url,
            message="Visualization generated successfully"
        )
    except Exception as e:
        logger.error(f"Error generating visualization: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Visualization generation failed: {str(e)}")

@visualization_router.get("/dashboard")
async def get_visualization_dashboard(request: Request):
    """
    Redirect to the latest generated visualization dashboard.
    
    Args:
        request: The HTTP request
        
    Returns:
        Redirect to the visualization dashboard
    """
    from fastapi.responses import RedirectResponse
    
    # Default dashboard path
    dashboard_path = Path(BASE_DIR) / "static" / "visualizations" / "langgraph_dashboard.html"
    
    if not dashboard_path.exists():
        raise HTTPException(status_code=404, detail="No visualization dashboard found")
    
    return RedirectResponse(url=f"/visualizations/langgraph_dashboard.html")
