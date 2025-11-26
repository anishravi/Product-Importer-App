import json
import asyncio
import os
import redis
from typing import Dict, List
from celery import Task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.config import settings
from app.models.product import Product
from app.services.csv_processor import CSVProcessor
# Import celery_app - must be imported here for the decorator
from celery_app import celery_app

# Batch size for CSV processing
BATCH_SIZE = 10000


def get_user_friendly_error(error_msg: str) -> str:
    """Convert technical errors to user-friendly messages."""
    error_lower = error_msg.lower()
    
    if any(keyword in error_lower for keyword in ['database', 'connection', 'postgresql', 'asyncpg']):
        return "Database connection error. Please try again later or contact support."
    elif any(keyword in error_lower for keyword in ['csv', 'header', 'format', 'column']):
        return "Invalid CSV format. Please check that your file has proper headers (sku, name, description) and is properly formatted."
    elif any(keyword in error_lower for keyword in ['memory', 'size', 'large']):
        return "File too large to process. Please try with a smaller file or contact support."
    elif any(keyword in error_lower for keyword in ['permission', 'access', 'file not found']):
        return "Unable to access the uploaded file. Please try uploading again."
    elif 'duplicate' in error_lower:
        return "Duplicate product found. Please check for duplicate SKU values in your CSV file."
    elif any(keyword in error_lower for keyword in ['encoding', 'utf', 'decode']):
        return "File encoding issue. Please save your CSV file with UTF-8 encoding and try again."
    else:
        return "An error occurred while processing your file. Please try again or contact support if the problem persists."

class ProgressTask(Task):
    """Custom task class that tracks progress."""
    
    _progress = 0
    
    def update_progress(self, progress: float, processed: int, total: int, errors: List[Dict] = None, task_id: str = None):
        """Update task progress and broadcast via WebSocket."""
        self._progress = progress
        self.update_state(
            state="PROCESSING",
            meta={
                "progress": progress,
                "processed": processed,
                "total": total,
                "errors": errors or []
            }
        )
        # Progress updates are available via Celery task state
        # Also publish to Redis so the API server can broadcast via WebSocket
        try:
            if task_id:
                r = redis.Redis.from_url(settings.redis_url)
                payload = json.dumps({
                    "type": "progress",
                    "task_id": task_id,
                    "progress": progress,
                    "processed": processed,
                    "total": total,
                    "errors": errors or []
                })
                # publish to channel used by API process
                r.publish('import_progress', payload)
        except Exception:
            # Don't fail the task if Redis publish fails
            pass


@celery_app.task(bind=True, base=ProgressTask, name="app.tasks.import_task.import_csv_task")
def import_csv_task(self, file_path: str, task_id: str):
    """
    Celery task to import products from CSV file.
    Note: This is a synchronous task wrapper that runs async code.
    file_path: Absolute path to the CSV file on disk
    """
    import os
    
    async def run_import():
        # Import inside the function to avoid closure issues
        from app.models.import_task import ImportTask as ImportTaskModel
        # Prefer a shared async_session created at worker start (in celery_app).
        # Fallback to creating a per-task engine/session if not available.
        async_session = getattr(celery_app, 'async_session', None)
        engine_to_dispose = None
        if async_session is None:
            engine = create_async_engine(
                settings.database_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=3600,
                connect_args={
                    "server_settings": {
                        "application_name": f"celery_import_{task_id[:8]}",
                    }
                }
            )
            async_session = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            engine_to_dispose = engine
        
        async with async_session() as session:
            # Create or update import task record
            result = await session.execute(
                select(ImportTaskModel).where(ImportTaskModel.task_id == task_id)
            )
            import_task = result.scalar_one_or_none()
            
            if not import_task:
                import_task = ImportTaskModel(
                    task_id=task_id,
                    status="processing",
                    progress=0.0,
                    total_rows=0,
                    processed_rows=0
                )
                session.add(import_task)
                await session.commit()
                await session.refresh(import_task)
            
            try:
                # Validate CSV format using file path
                is_valid, message = CSVProcessor.validate_csv_format(file_path)
                if not is_valid:
                    user_friendly_error = get_user_friendly_error(message)
                    import_task.status = "failed"
                    import_task.errors = json.dumps([{"error": user_friendly_error}])
                    await session.commit()
                    self.update_state(
                        state="FAILURE",
                        meta={"error": user_friendly_error}
                    )
                    return
                
                # Count total rows (streaming from file)
                total_rows = CSVProcessor.count_rows(file_path)
                import_task.total_rows = total_rows
                await session.commit()

                # Process in batches with optimized commit frequency for performance
                batch_size = CSVProcessor.BATCH_SIZE
                commit_every = 1  # Commit every batch for faster saves
                processed_rows = 0
                all_errors = []
                batch_count = 0

                for batch in CSVProcessor.iter_batches(file_path, batch_size):
                    # Add actual row numbers to each item in batch
                    batch_with_row_numbers = []
                    for i, row_data in enumerate(batch):
                        row_data['_actual_row'] = processed_rows + i + 2  # +2 because CSV row 1 is headers
                        batch_with_row_numbers.append(row_data)
                    
                    # Process batch with immediate commit
                    success_count, errors = await CSVProcessor.process_batch_async(
                        session,
                        batch_with_row_numbers,
                        task_id
                    )

                    processed_rows += len(batch)
                    all_errors.extend(errors)
                    batch_count += 1

                    # Update progress immediately
                    progress = (processed_rows / total_rows) * 100.0 if total_rows > 0 else 0.0
                    import_task.progress = progress
                    import_task.processed_rows = processed_rows
                    import_task.errors = json.dumps(all_errors) if all_errors else None
                    
                    # Commit after every batch for immediate saves
                    try:
                        await session.commit()
                        print(f"✅ Committed batch {batch_count} - {len(batch)} products saved")
                    except Exception as e:
                        await session.rollback()
                        error_msg = f"❌ Commit failed for batch {batch_count}: {str(e)}"
                        print(error_msg)
                        all_errors.append({"batch_error": error_msg})

                    # Update Celery task state and broadcast (also publish to Redis)
                    self.update_progress(
                        progress,
                        processed_rows,
                        total_rows,
                        all_errors,
                        task_id=task_id
                    )

                # All batches processed and committed individually
                print(f"🎉 Import completed! Processed {processed_rows} rows in {batch_count} batches")
                
                # Update final status
                import_task.errors = json.dumps(all_errors) if all_errors else None
                await session.commit()
                
                # Mark as completed
                import_task.status = "completed"
                await session.commit()
                # Publish final success to Redis (so WebSocket clients get complete notification)
                try:
                    r = redis.Redis.from_url(settings.redis_url)
                    payload = json.dumps({
                        "type": "complete",
                        "task_id": task_id,
                        "success": True,
                        "message": "Import completed",
                        "progress": 100.0,
                        "processed": processed_rows,
                        "total": total_rows,
                        "success_count": processed_rows - len(all_errors),
                        "error_count": len(all_errors)
                    })
                    r.publish('import_progress', payload)
                except Exception:
                    pass

                self.update_state(
                    state="SUCCESS",
                    meta={
                        "progress": 100.0,
                        "processed": processed_rows,
                        "total": total_rows,
                        "success_count": processed_rows - len(all_errors),
                        "error_count": len(all_errors)
                    }
                )
                # Task completed successfully
                
            except Exception as e:
                import_task.status = "failed"
                error_msg = str(e)
                user_friendly_error = get_user_friendly_error(error_msg)
                import_task.errors = json.dumps([{"error": user_friendly_error}])
                await session.commit()
                # Publish failure to Redis
                try:
                    r = redis.Redis.from_url(settings.redis_url)
                    payload = json.dumps({
                        "type": "complete",
                        "task_id": task_id,
                        "success": False,
                        "message": user_friendly_error
                    })
                    r.publish('import_progress', payload)
                except Exception:
                    pass
                
                self.update_state(
                    state="FAILURE",
                    meta={"error": user_friendly_error}
                )
                raise
        
        # Dispose of engine if we created one locally
        if engine_to_dispose:
            await engine_to_dispose.dispose()
    
    # Run the async function
    try:
        # Create new event loop for this task
        import asyncio
        
        # Set up new event loop for this worker process
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Run the async import function
        loop.run_until_complete(run_import())
        
    except Exception as e:
        error_msg = get_user_friendly_error(str(e))
        self.update_state(
            state="FAILURE",
            meta={"error": error_msg}
        )
        raise
    finally:
        try:
            # Clean up uploaded file
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass  # Non-critical cleanup failure


# Export the task function for import
__all__ = ['import_csv_task']