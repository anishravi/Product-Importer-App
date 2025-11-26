from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProductBase(BaseModel):
    sku: str = Field(..., description="Product SKU (unique, case-insensitive)")
    name: str = Field(..., description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    active: bool = Field(True, description="Active status")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BulkDeleteRequest(BaseModel):
    product_ids: list[int] = Field(..., description="List of product IDs to delete")


class BulkDeleteResponse(BaseModel):
    success_count: int
    failure_count: int
    errors: list[dict] = Field(default_factory=list)

