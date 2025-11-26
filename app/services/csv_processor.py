import csv
import io
import asyncio
from typing import Iterator, Dict, List, Tuple, Optional, Union
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.product import Product


class CSVProcessor:
    """Service for processing CSV files and importing products."""
    
    # Required columns for product import
    REQUIRED_COLUMNS = ['sku', 'name', 'description']
    BATCH_SIZE = 10000  # Process in batches for scalability
    
    # Common header aliases we may receive from vendors
    HEADER_ALIASES = {
        'sku': ['sku', 'product_sku', 'product id', 'id', 'productid'],
        'name': ['name', 'product_name', 'title'],
        'description': ['description', 'desc', 'details']
    }
    
    @staticmethod
    def validate_csv_format(file_input: Union[bytes, str, Path]) -> Tuple[bool, str]:
        """Validate that CSV has required columns."""
        try:
            if isinstance(file_input, (str, Path)):
                # File path - read first part for validation
                with open(file_input, 'r', encoding='utf-8') as f:
                    sample = f.read(8192)
                    f.seek(0)
                    text_content = f.read()
            else:
                # Bytes content
                text_content = file_input.decode('utf-8')
                sample = text_content[:8192]

            # Try to sniff the dialect so quoted multiline fields are parsed correctly
            dialect = None
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = None

            reader = csv.DictReader(io.StringIO(text_content), dialect=dialect) if dialect else csv.DictReader(io.StringIO(text_content))

            # Check if all required columns are present (allow aliases)
            headers = reader.fieldnames
            if not headers:
                return False, "CSV file is empty or has no headers"

            headers_lower = [h.lower().strip() for h in headers]

            # Check each required canonical name against aliases present in headers
            missing = []
            for req in CSVProcessor.REQUIRED_COLUMNS:
                aliases = [a.lower().strip() for a in CSVProcessor.HEADER_ALIASES.get(req, [req])]
                if not any(h in aliases for h in headers_lower):
                    if req.lower() not in headers_lower:
                        missing.append(req)

            if missing:
                return False, f"Missing required columns: {', '.join(missing)}"

            return True, "Valid"
        except Exception as e:
            return False, f"Error validating CSV: {str(e)}"
    
    @staticmethod
    def parse_csv_rows(file_input: Union[bytes, str, Path]) -> Iterator[Dict[str, str]]:
        """Parse CSV file and yield rows as dictionaries."""
        if isinstance(file_input, (str, Path)):
            # File path - stream from file
            with open(file_input, 'r', encoding='utf-8') as f:
                # Sniff dialect from sample
                sample = f.read(8192)
                f.seek(0)
                dialect = None
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except Exception:
                    dialect = None

                reader = csv.DictReader(f, dialect=dialect) if dialect else csv.DictReader(f)

                # Create header mapping
                header_map = {}
                for src in (reader.fieldnames or []):
                    key = src.lower().strip()
                    mapped = None
                    for canon, aliases in CSVProcessor.HEADER_ALIASES.items():
                        if key in [a.lower().strip() for a in aliases] or key == canon:
                            mapped = canon
                            break
                    header_map[src] = mapped or key

                for row in reader:
                    # Normalize and map column names
                    normalized_row: Dict[str, Optional[str]] = {}
                    for key, value in row.items():
                        src_key = key
                        canon_key = header_map.get(src_key, src_key).lower().strip()
                        normalized_row[canon_key] = value.strip() if isinstance(value, str) and value is not None else (None if value == '' else value)

                    yield normalized_row
        else:
            # Bytes content - use existing logic
            text_content = file_input.decode('utf-8')

            # Sniff dialect from a sample to handle quoted newlines and different quoting rules
            sample = text_content[:8192]
            dialect = None
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = None

            stream = io.StringIO(text_content)
            reader = csv.DictReader(stream, dialect=dialect) if dialect else csv.DictReader(stream)

            # Create a mapping from source header -> canonical header (sku/name/description)
            header_map = {}
            for src in (reader.fieldnames or []):
                key = src.lower().strip()
                mapped = None
                for canon, aliases in CSVProcessor.HEADER_ALIASES.items():
                    if key in [a.lower().strip() for a in aliases] or key == canon:
                        mapped = canon
                        break
                header_map[src] = mapped or key

            for row in reader:
                # Normalize and map column names (case-insensitive)
                normalized_row: Dict[str, Optional[str]] = {}
                for key, value in row.items():
                    src_key = key
                    canon_key = header_map.get(src_key, src_key).lower().strip()
                    # strip only when it's a string
                    normalized_row[canon_key] = value.strip() if isinstance(value, str) and value is not None else (None if value == '' else value)

                yield normalized_row

    @staticmethod
    def count_rows(file_input: Union[bytes, str, Path]) -> int:
        """Count data rows in the CSV (excluding header).

        This is a lightweight pass that uses csv.reader and does not build
        dictionaries for every row, so it's cheaper than materializing all
        parsed rows.
        """
        if isinstance(file_input, (str, Path)):
            # File path - stream from file
            with open(file_input, 'r', encoding='utf-8') as f:
                sample = f.read(8192)
                f.seek(0)
                dialect = None
                try:
                    dialect = csv.Sniffer().sniff(sample)
                except Exception:
                    dialect = None

                reader = csv.DictReader(f, dialect=dialect) if dialect else csv.DictReader(f)
                count = 0
                for _ in reader:
                    count += 1
                return count
        else:
            # Bytes content - use existing logic
            # Count logical rows using DictReader so quoted multiline fields count as one
            text_content = file_input.decode('utf-8')
            sample = text_content[:8192]
            dialect = None
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = None

            stream = io.StringIO(text_content)
            reader = csv.DictReader(stream, dialect=dialect) if dialect else csv.DictReader(stream)
            count = 0
            for _ in reader:
                count += 1
            return count

    @staticmethod
    def iter_batches(file_input: Union[bytes, str, Path], batch_size: int) -> Iterator[List[Dict[str, str]]]:
        """Yield lists of parsed rows of size up to batch_size.

        This streams rows without materializing the full file into memory.
        """
        batch: List[Dict[str, str]] = []
        for row in CSVProcessor.parse_csv_rows(file_input):
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

                # Validate required fields
                if not sku:
                    errors.append({"row": idx, "error": "SKU is required"})
                    continue

                if not name:
                    errors.append({"row": idx, "error": "Name is required"})
                    continue

                existing_product = existing_map.get(sku.lower()) if sku else None

                if existing_product:
                    existing_product.name = name
                    existing_product.description = description
                    success_count += 1
                else:
                    new_product = Product(
                        sku=sku,
                        name=name,
                        description=description
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

    @staticmethod
    async def process_batch_async(
        session: AsyncSession,
        batch: List[Dict[str, str]],
        task_id: str
    ) -> Tuple[int, List[Dict]]:
        """
        Process a batch of products asynchronously without waiting for commit.
        Returns (success_count, errors_list) immediately after adding to session.
        The actual commit happens in the background.
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
                
                # Get actual CSV row number (passed from import task)
                actual_row = row.get('_actual_row', idx + 1)

                # Validate required fields
                if not sku:
                    errors.append({"row": actual_row, "error": "SKU is required"})
                    continue

                if not name:
                    errors.append({"row": actual_row, "error": "Name is required"})
                    continue

                existing_product = existing_map.get(sku.lower()) if sku else None

                if existing_product:
                    # Automatically overwrite existing product based on case-insensitive SKU
                    existing_product.name = name
                    existing_product.description = description
                    success_count += 1
                else:
                    # Check if this SKU is already in the current batch (case-insensitive)
                    sku_lower = sku.lower()
                    batch_sku_found = False
                    for existing_new_product in new_products:
                        if existing_new_product.sku.lower() == sku_lower:
                            # Overwrite the product in current batch
                            existing_new_product.name = name
                            existing_new_product.description = description
                            batch_sku_found = True
                            break
                    
                    if not batch_sku_found:
                        # Create new product
                        new_product = Product(
                            sku=sku,
                            name=name,
                            description=description
                        )
                        new_products.append(new_product)
                    
                    success_count += 1

            except Exception as e:
                actual_row = row.get('_actual_row', idx + 1) if isinstance(row, dict) else idx + 1
                errors.append({"row": actual_row, "error": str(e)})

        # Add to session - use simple add_all for reliability
        if new_products:
            try:
                session.add_all(new_products)
                print(f"📝 Added {len(new_products)} products to session")
            except Exception as e:
                error_msg = f"Failed to add products to session: {str(e)}"
                print(f"❌ {error_msg}")
                errors.append({"batch_error": error_msg})
                success_count = 0
        
        return success_count, errors

