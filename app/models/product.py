from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Case-insensitive unique index on SKU
    __table_args__ = (
        Index('ix_products_sku_lower', func.lower(sku), unique=True),
    )

