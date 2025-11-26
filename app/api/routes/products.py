from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database import get_db
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse
)
from app.services.product_service import ProductService
from app.services.webhook_service import WebhookService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sku: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """List products with pagination and filtering."""
    products, total = await ProductService.list_products(
        db,
        page=page,
        page_size=page_size,
        sku_filter=sku,
        name_filter=name,
        description_filter=description,
        active_filter=active
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a single product by ID."""
    product = await ProductService.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.delete("/delete-all")
async def delete_all_products(
    db: AsyncSession = Depends(get_db)
):
    """Delete all products. Returns number deleted."""
    deleted_count = await ProductService.delete_all_products(db)

    # Trigger bulk deleted webhook
    try:
        await WebhookService.trigger_webhooks_for_event(
            db,
            "product.bulk_deleted",
            {"deleted_count": deleted_count}
        )
    except Exception:
        # Don't fail the request if webhooks fail
        pass

    return {"deleted_count": deleted_count}


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new product."""
    try:
        product = await ProductService.create_product(db, product_data)
        # Trigger webhooks (log before/after to aid debugging)
        payload = ProductResponse.model_validate(product).model_dump()
        logger.info("Triggering webhooks for product.created payload=%s", payload)
        results = await WebhookService.trigger_webhooks_for_event(
            db,
            "product.created",
            payload
        )
        logger.info("Webhook trigger results for product.created: %s", results)
        return ProductResponse.model_validate(product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a product."""
    try:
        product = await ProductService.update_product(db, product_id, product_data)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        # Trigger webhooks (log before/after)
        payload = ProductResponse.model_validate(product).model_dump()
        logger.info("Triggering webhooks for product.updated payload=%s", payload)
        results = await WebhookService.trigger_webhooks_for_event(
            db,
            "product.updated",
            payload
        )
        logger.info("Webhook trigger results for product.updated: %s", results)
        return ProductResponse.model_validate(product)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a product."""
    product = await ProductService.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    deleted = await ProductService.delete_product(db, product_id)
    if deleted:
        # Trigger webhooks (log)
        payload = {"id": product_id}
        logger.info("Triggering webhooks for product.deleted payload=%s", payload)
        results = await WebhookService.trigger_webhooks_for_event(
            db,
            "product.deleted",
            payload
        )
        logger.info("Webhook trigger results for product.deleted: %s", results)
    return None


