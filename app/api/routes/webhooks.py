from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_db
from app.schemas.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookTestResponse
)
from app.services.webhook_service import WebhookService
from app.api.websocket import manager

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """List all webhooks."""
    webhooks = await WebhookService.list_webhooks(db)
    return [WebhookResponse.model_validate(wh) for wh in webhooks]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a webhook by ID."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse.model_validate(webhook)


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    webhook_data: WebhookCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new webhook."""
    webhook = await WebhookService.create_webhook(db, webhook_data)
    return WebhookResponse.model_validate(webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    webhook_data: WebhookUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a webhook."""
    webhook = await WebhookService.update_webhook(db, webhook_id, webhook_data)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return WebhookResponse.model_validate(webhook)


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a webhook."""
    deleted = await WebhookService.delete_webhook(db, webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return None


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Test a webhook by sending a test event."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Send test payload
    test_payload = {
        "test": True,
        "message": "This is a test webhook"
    }
    
    result = await WebhookService.trigger_webhook(
        webhook,
        "test",
        test_payload
    )
    
    # Broadcast result via WebSocket
    await manager.broadcast_webhook_test(webhook_id, result)
    
    return WebhookTestResponse(**result)

