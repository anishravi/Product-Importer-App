from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.product import BulkDeleteRequest, BulkDeleteResponse
from app.services.product_service import ProductService
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_products(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db)
):
    """Bulk delete products."""
    if not request.product_ids:
        raise HTTPException(status_code=400, detail="No product IDs provided")
    
    success_count, errors = await ProductService.bulk_delete_products(
        db,
        request.product_ids
    )
    
    failure_count = len(errors)
    
    # Trigger webhooks
    await WebhookService.trigger_webhooks_for_event(
        db,
        "product.bulk_deleted",
        {
            "deleted_ids": request.product_ids[:success_count],
            "success_count": success_count,
            "failure_count": failure_count
        }
    )
    
    return BulkDeleteResponse(
        success_count=success_count,
        failure_count=failure_count,
        errors=errors
    )

