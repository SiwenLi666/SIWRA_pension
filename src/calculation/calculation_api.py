"""
Pension Calculation API module.

This module provides API endpoints for the pension calculation functionality.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Depends

from src.calculation.calculation_agent import CalculationAgent
from src.calculation.calculation_manager import CalculationManager
from src.calculation.data_extractor import PensionDataExtractor

logger = logging.getLogger('calculation_api')

# Create router
calculation_router = APIRouter(
    prefix="/api/calculation",
    tags=["calculation"],
    responses={404: {"description": "Not found"}},
)

# Create calculation agent
calculation_agent = CalculationAgent()


# Define models
class CalculationRequest(BaseModel):
    """Request model for pension calculations."""
    agreement: str = Field(..., description="Pension agreement type (ITP1, ITP2, SAF-LO, PA16)")
    calculation_type: str = Field(..., description="Type of calculation (retirement_estimate, contribution_calculation)")
    parameters: Dict[str, Any] = Field(..., description="Parameters for the calculation")


class CalculationResponse(BaseModel):
    """Response model for pension calculations."""
    success: bool = Field(..., description="Whether the calculation was successful")
    result: Dict[str, Any] = Field(..., description="Calculation results")
    message: str = Field(..., description="Human-readable message")


class CalculationQueryResponse(BaseModel):
    """Response model for handling calculation queries."""
    is_calculation: bool = Field(..., description="Whether the query is a calculation query")
    calculation_type: Optional[str] = Field(None, description="Type of calculation detected")
    success: Optional[bool] = Field(None, description="Whether the calculation was successful")
    requires_more_info: Optional[bool] = Field(None, description="Whether more information is required")
    missing_parameters: Optional[List[str]] = Field(None, description="Missing parameters")
    current_parameters: Optional[Dict[str, Any]] = Field(None, description="Currently extracted parameters")
    result: Optional[Dict[str, Any]] = Field(None, description="Calculation results")
    message: str = Field(..., description="Human-readable message")


class ParameterUpdateResponse(BaseModel):
    """Response model for parameter updates."""
    success: bool = Field(..., description="Whether the update was successful")
    changes: Dict[str, Any] = Field(..., description="Changes made to parameters")
    message: str = Field(..., description="Human-readable message")


class CalculationHistoryResponse(BaseModel):
    """Response model for calculation history."""
    success: bool = Field(..., description="Whether the request was successful")
    history: List[Dict[str, Any]] = Field(..., description="Calculation history")


# Define API endpoints
@calculation_router.post("/calculate", response_model=CalculationResponse)
async def calculate(request: CalculationRequest):
    """
    Perform a pension calculation.
    
    Args:
        request: Calculation request containing agreement, calculation_type, and parameters.
        
    Returns:
        CalculationResponse: Calculation results.
    """
    try:
        # Validate agreement
        if request.agreement not in ["ITP1", "ITP2", "SAF-LO", "PA16"]:
            raise HTTPException(status_code=400, detail=f"Invalid agreement: {request.agreement}")
        
        # Validate calculation type
        if request.calculation_type not in ["retirement_estimate", "contribution_calculation"]:
            raise HTTPException(status_code=400, detail=f"Invalid calculation type: {request.calculation_type}")
        
        # Perform calculation
        result = calculation_agent.calculation_manager.calculate(
            request.agreement,
            request.calculation_type,
            request.parameters
        )
        
        if "error" in result:
            return CalculationResponse(
                success=False,
                result={"error": result["error"]},
                message=f"Error performing calculation: {result['error']}"
            )
        
        # Format response message
        if request.calculation_type == "retirement_estimate":
            message = calculation_agent._format_retirement_estimate(result, request.agreement)
        elif request.calculation_type == "contribution_calculation":
            message = calculation_agent._format_contribution_calculation(result, request.agreement)
        else:
            message = f"Calculation completed successfully for {request.agreement}."
        
        return CalculationResponse(
            success=True,
            result=result,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Error performing calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@calculation_router.post("/query", response_model=CalculationQueryResponse)
async def handle_calculation_query(query: str = Query(...), agreement: str = Query(...)):
    """
    Handle a calculation query.
    
    Args:
        query: User query.
        agreement: Pension agreement type.
        
    Returns:
        CalculationQueryResponse: Response with calculation results or follow-up questions.
    """
    try:
        # Validate agreement
        if agreement not in ["ITP1", "ITP2", "SAF-LO", "PA16"]:
            raise HTTPException(status_code=400, detail=f"Invalid agreement: {agreement}")
        
        # Handle query
        response = calculation_agent.handle_calculation_query(query, agreement)
        
        return CalculationQueryResponse(**response)
    
    except Exception as e:
        logger.error(f"Error handling calculation query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@calculation_router.post("/update-parameters", response_model=ParameterUpdateResponse)
async def update_parameters():
    """
    Update calculation parameters from pension agreement documents.
    
    Returns:
        ParameterUpdateResponse: Response with changes made to parameters.
    """
    try:
        # Update parameters
        changes = calculation_agent.update_parameters_from_documents()
        
        if not changes:
            return ParameterUpdateResponse(
                success=True,
                changes={},
                message="No changes were made to parameters."
            )
        
        # Format message
        agreements_updated = list(changes.keys())
        message = f"Updated parameters for {', '.join(agreements_updated)}."
        
        return ParameterUpdateResponse(
            success=True,
            changes=changes,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Error updating parameters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@calculation_router.get("/detect-changes", response_model=ParameterUpdateResponse)
async def detect_parameter_changes():
    """
    Detect changes in calculation parameters from pension agreement documents.
    
    Returns:
        ParameterUpdateResponse: Response with detected changes.
    """
    try:
        # Detect changes
        changes = calculation_agent.detect_parameter_changes()
        
        if not changes:
            return ParameterUpdateResponse(
                success=True,
                changes={},
                message="No changes detected in parameters."
            )
        
        # Format message
        agreements_changed = list(changes.keys())
        message = f"Detected changes in parameters for {', '.join(agreements_changed)}."
        
        return ParameterUpdateResponse(
            success=True,
            changes=changes,
            message=message
        )
    
    except Exception as e:
        logger.error(f"Error detecting parameter changes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@calculation_router.get("/history", response_model=CalculationHistoryResponse)
async def get_calculation_history(limit: int = Query(10, ge=1, le=100)):
    """
    Get calculation history.
    
    Args:
        limit: Maximum number of history items to return.
        
    Returns:
        CalculationHistoryResponse: Response with calculation history.
    """
    try:
        # Get history
        history = calculation_agent.calculation_manager.get_calculation_history(limit)
        
        return CalculationHistoryResponse(
            success=True,
            history=history
        )
    
    except Exception as e:
        logger.error(f"Error getting calculation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@calculation_router.get("/parameters/{agreement}", response_model=Dict[str, Any])
async def get_calculation_parameters(agreement: str):
    """
    Get calculation parameters for a specific agreement.
    
    Args:
        agreement: Pension agreement type.
        
    Returns:
        Dict[str, Any]: Calculation parameters.
    """
    try:
        # Validate agreement
        if agreement not in ["ITP1", "ITP2", "SAF-LO", "PA16"]:
            raise HTTPException(status_code=400, detail=f"Invalid agreement: {agreement}")
        
        # Get parameters
        parameters = calculation_agent.calculation_manager.get_calculation_parameters(agreement)
        
        if not parameters:
            return {}
        
        return parameters
    
    except Exception as e:
        logger.error(f"Error getting calculation parameters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
