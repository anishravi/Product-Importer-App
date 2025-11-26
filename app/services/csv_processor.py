import csv
import io
from typing import Iterator, Dict, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.product import Product


class CSVProcessor:
    """Service for processing CSV files and importing products."""
    
    REQUIRED_COLUMNS = ['sku', 'name', 'description', 'active']
    BATCH_SIZE = 1000  # Process in batches for scalability
    
    @staticmethod
    def validate_csv_format(file_content: bytes) -> Tuple[bool, str]:
        """Validate that CSV has required columns."""
        try:
            text_content = file_content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(text_content))
            
            # Check if all required columns are present
            headers = reader.fieldnames
            if not headers:
                return False, "CSV file is empty or has no headers"
            
            headers_lower = [h.lower().strip() for h in headers]
            missing = [col for col in CSVProcessor.REQUIRED_COLUMNS if col.lower() not in headers_lower]
            
            if missing:
                return False, f"Missing required columns: {', '.join(missing)}"
            
            return True, "Valid"
        except Exception as e:
            return False, f"Error validating CSV: {str(e)}"
    
    @staticmethod
    def parse_csv_rows(file_content: bytes) -> Iterator[Dict[str, str]]:
        """Parse CSV file and yield rows as dictionaries."""
        text_content = file_content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text_content))
        
        for row in reader:
            # Normalize column names (case-insensitive)
            normalized_row = {}
            for key, value in row.items():
                normalized_key = key.lower().strip()
                normalized_row[normalized_key] = value.strip() if value else None
            
            yield normalized_row

    @staticmethod
    def count_rows(file_content: bytes) -> int:
        """Count data rows in the CSV (excluding header).

        This is a lightweight pass that uses csv.reader and does not build
        dictionaries for every row, so it's cheaper than materializing all
        parsed rows.
        """
        text_content = file_content.decode('utf-8')
        reader = csv.reader(io.StringIO(text_content))
        # Count all rows then subtract 1 for header if present
        total = 0
        for _ in reader:
            total += 1
        # If file has at least one row, assume first row is header
        return max(0, total - 1)

    @staticmethod
    def iter_batches(file_content: bytes, batch_size: int) -> Iterator[List[Dict[str, str]]]:
        """Yield lists of parsed rows of size up to batch_size.

        This streams rows without materializing the full file into memory.
        """
        batch: List[Dict[str, str]] = []
        for row in CSVProcessor.parse_csv_rows(file_content):
            batch.append(row)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
    
    @staticmethod
    async def process_batch(
        session: AsyncSession,
        batch: List[Dict[str, str]],
        task_id: str
    ) -> Tuple[int, List[Dict]]:
        """
        Process a batch of products.
        Returns (success_count, errors_list)
        """
        success_count = 0
        errors = []
        
        # Collect SKUs for batch lookup (case-insensitive)
        skus: List[str] = []
        for row in batch:
            sku = (row.get('sku') or '').strip()
            if sku:
                skus.append(sku)

        lower_skus = [s.lower() for s in skus]

        existing_map = {}
        if lower_skus:
            try:
                # Query existing products for all SKUs in this batch
                result = await session.execute(
                    select(Product).where(func.lower(Product.sku).in_(lower_skus))
                )
                existing_products = result.scalars().all()
                existing_map = {p.sku.lower(): p for p in existing_products}
            except Exception as e:
                # If the lookup failed, return a batch error
                errors.append({"batch_error": f"Lookup failed: {str(e)}"})
                return 0, errors

        new_products: List[Product] = []
        for idx, row in enumerate(batch):
            try:
                sku = (row.get('sku') or '').strip()
                name = (row.get('name') or '').strip()
                description = (row.get('description') or '').strip() or None
                active_str = (row.get('active') or 'true').strip().lower()

                # Validate required fields
                if not sku:
                    errors.append({"row": idx, "error": "SKU is required"})
                    continue

                if not name:
                    errors.append({"row": idx, "error": "Name is required"})
                    continue

                active = active_str in ('true', '1', 'yes', 'y', 'on')

                existing_product = existing_map.get(sku.lower()) if sku else None

                if existing_product:
                    existing_product.name = name
                    existing_product.description = description
                    existing_product.active = active
                    success_count += 1
                else:
                    new_product = Product(
                        sku=sku,
                        name=name,
                        description=description,
                        active=active
                    )
                    new_products.append(new_product)
                    success_count += 1

            except Exception as e:
                errors.append({"row": idx, "error": str(e)})

        # Bulk add new products (if any)
        if new_products:
            try:
                session.add_all(new_products)
            except Exception as e:
                errors.append({"batch_error": f"Add failed: {str(e)}"})
                # don't return yet; attempt commit which may fail
        
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            errors.append({"batch_error": str(e)})
            success_count = 0  # If commit fails, consider batch failed
        
        return success_count, errors

