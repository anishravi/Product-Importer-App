import json
import asyncio
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from app.models.webhook import Webhook
from app.schemas.webhook import WebhookCreate, WebhookUpdate
import logging

logger = logging.getLogger(__name__)
if not logger.handlers:
    # basic configuration if not already configured by the app
    logging.basicConfig(level=logging.INFO)


def _make_serializable(obj):
    """Recursively convert non-JSON-native types (datetimes) to serializable forms."""
    from datetime import datetime, date

    if obj is None:
        return None
    if isinstance(obj, (str, bool, int, float)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_serializable(v) for v in obj]
    # Fallback to string representation
    try:
        return str(obj)
    except Exception:
        return None


class WebhookService:
    """Service for webhook management and triggering."""
    
    @staticmethod
    async def create_webhook(
        session: AsyncSession,
        webhook_data: WebhookCreate
    ) -> Webhook:
        """Create a new webhook."""
        webhook = Webhook(**webhook_data.model_dump())
        session.add(webhook)
        await session.commit()
        await session.refresh(webhook)
        return webhook
    
    @staticmethod
    async def get_webhook(session: AsyncSession, webhook_id: int) -> Optional[Webhook]:
        """Get a webhook by ID."""
        result = await session.execute(
            select(Webhook).where(Webhook.id == webhook_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_webhooks(session: AsyncSession) -> List[Webhook]:
        """List all webhooks."""
        result = await session.execute(select(Webhook).order_by(Webhook.id.desc()))
        return list(result.scalars().all())
    
    @staticmethod
    async def update_webhook(
        session: AsyncSession,
        webhook_id: int,
        webhook_data: WebhookUpdate
    ) -> Optional[Webhook]:
        """Update a webhook."""
        webhook = await WebhookService.get_webhook(session, webhook_id)
        if not webhook:
            return None
        
        update_data = webhook_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(webhook, key, value)
        
        await session.commit()
        await session.refresh(webhook)
        return webhook
    
    @staticmethod
    async def delete_webhook(session: AsyncSession, webhook_id: int) -> bool:
        """Delete a webhook."""
        webhook = await WebhookService.get_webhook(session, webhook_id)
        if not webhook:
            return False
        
        await session.delete(webhook)
        await session.commit()
        return True
    
    @staticmethod
    async def get_active_webhooks_for_event(
        session: AsyncSession,
        event_type: str
    ) -> List[Webhook]:
        """Get all active webhooks subscribed to a specific event type."""
        result = await session.execute(
            select(Webhook).where(
                Webhook.enabled == True
            )
        )
        webhooks = result.scalars().all()
        
        # Filter webhooks that subscribe to this event type
        filtered = [
            wh for wh in webhooks
            if event_type in wh.event_types
        ]
        
        return filtered
    
    @staticmethod
    async def trigger_webhook(
        webhook: Webhook,
        event_type: str,
        payload: dict
    ) -> dict:
        """
        Trigger a webhook with the given payload.
        Returns dict with success, status_code, response_time_ms, error.
        """
        start_time = datetime.utcnow()

        # Make sure payload is JSON serializable (convert datetimes to isoformat etc.)
        serializable_payload = _make_serializable(payload)

        body = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": serializable_payload
        }

        logger.info(f"Sending webhook to %s for event %s", webhook.url, event_type)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook.url,
                    json=body,
                    headers={"Content-Type": "application/json"}
                )

            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000

            success = 200 <= response.status_code < 300
            if success:
                logger.info(
                    "Webhook sent successfully to %s (event=%s) status=%s time=%.2fms",
                    webhook.url,
                    event_type,
                    response.status_code,
                    response_time_ms
                )
            else:
                logger.warning(
                    "Webhook to %s returned status %s (event=%s)",
                    webhook.url,
                    response.status_code,
                    event_type
                )

            return {
                "success": success,
                "status_code": response.status_code,
                "response_time_ms": round(response_time_ms, 2),
                "error": None if success else f"HTTP {response.status_code}"
            }

        except httpx.TimeoutException as te:
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            logger.error("Webhook to %s timed out (event=%s)", webhook.url, event_type)
            return {"success": False, "status_code": None, "response_time_ms": round(response_time_ms, 2), "error": "Request timeout"}

        except Exception as e:
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            logger.exception("Failed to send webhook to %s (event=%s): %s", webhook.url, event_type, str(e))
            return {"success": False, "status_code": None, "response_time_ms": round(response_time_ms, 2), "error": str(e)}
    
    @staticmethod
    async def trigger_webhooks_for_event(
        session: AsyncSession,
        event_type: str,
        payload: dict
    ) -> List[dict]:
        """
        Trigger all active webhooks subscribed to an event type.
        Returns list of results.
        """
        webhooks = await WebhookService.get_active_webhooks_for_event(session, event_type)

        logger.info("Found %d active webhooks for event %s", len(webhooks), event_type)

        if not webhooks:
            return []

        # Trigger all webhooks concurrently
        tasks = [
            WebhookService.trigger_webhook(webhook, event_type, payload)
            for webhook in webhooks
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error dicts
        formatted_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.exception("Exception while delivering webhook (id=%s event=%s): %s", webhooks[i].id, event_type, str(result))
                formatted_results.append({
                    "webhook_id": webhooks[i].id,
                    "success": False,
                    "status_code": None,
                    "response_time_ms": None,
                    "error": str(result)
                })
            else:
                result["webhook_id"] = webhooks[i].id
                formatted_results.append(result)

        return formatted_results

