from typing import Optional, List, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from sqlalchemy import delete


class ProductService:
    """Service for product CRUD operations."""
    
    @staticmethod
    async def create_product(
        session: AsyncSession,
        product_data: ProductCreate
    ) -> Product:
        """Create a new product."""
        # Check if SKU already exists (case-insensitive)
        result = await session.execute(
            select(Product).where(func.lower(Product.sku) == func.lower(product_data.sku))
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise ValueError(f"Product with SKU '{product_data.sku}' already exists")
        
        product = Product(**product_data.model_dump())
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product
    
    @staticmethod
    async def get_product(session: AsyncSession, product_id: int) -> Optional[Product]:
        """Get a product by ID."""
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_product_by_sku(session: AsyncSession, sku: str) -> Optional[Product]:
        """Get a product by SKU (case-insensitive)."""
        result = await session.execute(
            select(Product).where(func.lower(Product.sku) == func.lower(sku))
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def list_products(
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        sku_filter: Optional[str] = None,
        name_filter: Optional[str] = None,
        description_filter: Optional[str] = None,
        active_filter: Optional[bool] = None
    ) -> Tuple[List[Product], int]:
        """List products with pagination and filtering."""
        query = select(Product)
        
        # Apply filters
        conditions = []
        if sku_filter:
            conditions.append(Product.sku.ilike(f"%{sku_filter}%"))
        if name_filter:
            conditions.append(Product.name.ilike(f"%{name_filter}%"))
        if description_filter:
            conditions.append(Product.description.ilike(f"%{description_filter}%"))
        if active_filter is not None:
            conditions.append(Product.active == active_filter)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Get total count
        count_query = select(func.count()).select_from(Product)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.order_by(Product.id.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await session.execute(query)
        products = result.scalars().all()
        
        return list(products), total
    
    @staticmethod
    async def update_product(
        session: AsyncSession,
        product_id: int,
        product_data: ProductUpdate
    ) -> Optional[Product]:
        """Update a product."""
        product = await ProductService.get_product(session, product_id)
        if not product:
            return None
        
        update_data = product_data.model_dump(exclude_unset=True)
        
        # If SKU is being updated, check for duplicates (case-insensitive)
        if 'sku' in update_data:
            existing = await ProductService.get_product_by_sku(session, update_data['sku'])
            if existing and existing.id != product_id:
                raise ValueError(f"Product with SKU '{update_data['sku']}' already exists")
        
        for key, value in update_data.items():
            setattr(product, key, value)
        
        await session.commit()
        await session.refresh(product)
        return product
    
    @staticmethod
    async def delete_product(session: AsyncSession, product_id: int) -> bool:
        """Delete a product."""
        product = await ProductService.get_product(session, product_id)
        if not product:
            return False
        
        await session.delete(product)
        await session.commit()
        return True
    
    @staticmethod
    async def bulk_delete_products(
        session: AsyncSession,
        product_ids: List[int]
    ) -> Tuple[int, List[Dict]]:
        """Bulk delete products. Returns (success_count, errors)."""
        success_count = 0
        errors = []
        
        for product_id in product_ids:
            try:
                product = await ProductService.get_product(session, product_id)
                if product:
                    await session.delete(product)
                    success_count += 1
                else:
                    errors.append({"id": product_id, "error": "Product not found"})
            except Exception as e:
                errors.append({"id": product_id, "error": str(e)})
        
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            errors.append({"error": f"Transaction failed: {str(e)}"})
            success_count = 0
        
        return success_count, errors

    @staticmethod
    async def delete_all_products(session: AsyncSession) -> int:
        """Delete all products and return the number deleted."""
        try:
            # Use core delete for efficiency
            result = await session.execute(delete(Product))
            deleted_count = result.rowcount if result is not None else 0
            await session.commit()
            return deleted_count or 0
        except Exception:
            await session.rollback()
            raise

