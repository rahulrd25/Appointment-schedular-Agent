"""
Webhook API Endpoints - FastAPI implementation for external calendar updates.
This module provides REST API endpoints for processing webhooks from calendar providers.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.sync.webhook_handler import WebhookHandler
from app.schemas.calendar_schemas import ErrorResponse

# Initialize router with proper tags and prefix
router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["Webhooks"],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid webhook data"},
        401: {"model": ErrorResponse, "description": "Invalid signature"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)


@router.post("/google-calendar")
async def google_calendar_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Handle Google Calendar webhook.
    
    This endpoint processes webhooks from Google Calendar to keep our database
    in sync with external calendar changes.
    
    Args:
        request: FastAPI request object containing webhook data
        db: Database session (dependency injection)
        
    Returns:
        JSONResponse: Processing result
        
    Raises:
        HTTPException: If webhook processing fails
    """
    try:
        # Get webhook data from request body
        webhook_data = await request.json()
        
        # Get signature from headers (for future validation)
        signature = request.headers.get("X-Goog-Signature")
        
        # Initialize webhook handler
        webhook_handler = WebhookHandler(db)
        
        # Process the webhook
        result = webhook_handler.handle_webhook("google", webhook_data, signature)
        
        if result.get("success"):
            return JSONResponse(
                content=result,
                status_code=status.HTTP_200_OK
            )
        else:
            return JSONResponse(
                content=result,
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process Google Calendar webhook: {str(e)}"
        )


@router.post("/microsoft-calendar")
async def microsoft_calendar_webhook(
    request: Request,
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Handle Microsoft Calendar webhook (future implementation).
    
    This endpoint will process webhooks from Microsoft Calendar to keep our
    database in sync with external calendar changes.
    
    Args:
        request: FastAPI request object containing webhook data
        db: Database session (dependency injection)
        
    Returns:
        JSONResponse: Processing result
        
    Raises:
        HTTPException: If webhook processing fails
    """
    try:
        # Get webhook data from request body
        webhook_data = await request.json()
        
        # Get signature from headers (for future validation)
        signature = request.headers.get("X-Microsoft-Signature")
        
        # Initialize webhook handler
        webhook_handler = WebhookHandler(db)
        
        # Process the webhook
        result = webhook_handler.handle_webhook("microsoft", webhook_data, signature)
        
        if result.get("success"):
            return JSONResponse(
                content=result,
                status_code=status.HTTP_200_OK
            )
        else:
            return JSONResponse(
                content=result,
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process Microsoft Calendar webhook: {str(e)}"
        )


@router.get("/health")
async def webhook_health_check() -> JSONResponse:
    """
    Health check endpoint for webhook service.
    
    Returns:
        JSONResponse: Health status
    """
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "webhook-handler",
            "supported_providers": ["google", "microsoft"]
        },
        status_code=status.HTTP_200_OK
    ) 