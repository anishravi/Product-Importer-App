import json
import asyncio
from typing import Dict, List
from celery import Task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.config import settings
from app.models.product import Product
from app.services.csv_processor import CSVProcessor
# ImportTaskModel will be imported inside the async function to avoid closure issues

# Import celery_app - must be imported here for the decorator
from celery_app import celery_app


class ProgressTask(Task):
    """Custom task class that tracks progress."""
    
    _progress = 0
    
    def update_progress(self, progress: float, processed: int, total: int, errors: List[Dict] = None):
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
        # WebSocket clients can poll /api/upload/task/{task_id} for updates


@celery_app.task(bind=True, base=ProgressTask, name="app.tasks.import_task.import_csv_task")
def import_csv_task(self, file_content: str, task_id: str):
    """
    Celery task to import products from CSV file.
    Note: This is a synchronous task wrapper that runs async code.
    file_content: base64 encoded string of the CSV file content
    """
    import base64
    
    # Decode base64 content back to bytes
    try:
        file_content_bytes = base64.b64decode(file_content.encode('utf-8'))
    except Exception as e:
        print(f"Error decoding file content: {e}")
        raise
    
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
                pool_pre_ping=True
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
            
            try:
                # Validate CSV format
                is_valid, message = CSVProcessor.validate_csv_format(file_content_bytes)
                if not is_valid:
                    import_task.status = "failed"
                    import_task.errors = json.dumps([{"error": message}])
                    await session.commit()
                    self.update_state(
                        state="FAILURE",
                        meta={"error": message}
                    )
                    return
                
                # Count total rows (cheaper than building all parsed dicts)
                total_rows = CSVProcessor.count_rows(file_content_bytes)
                import_task.total_rows = total_rows
                await session.commit()

                # Process in batches using a streaming generator
                batch_size = CSVProcessor.BATCH_SIZE
                processed_rows = 0
                all_errors = []

                for batch in CSVProcessor.iter_batches(file_content_bytes, batch_size):
                    success_count, errors = await CSVProcessor.process_batch(
                        session,
                        batch,
                        task_id
                    )

                    processed_rows += len(batch)
                    all_errors.extend(errors)

                    # Update progress
                    progress = (processed_rows / total_rows) * 100.0 if total_rows > 0 else 0.0
                    import_task.progress = progress
                    import_task.processed_rows = processed_rows
                    import_task.errors = json.dumps(all_errors) if all_errors else None
                    await session.commit()

                    # Update Celery task state and broadcast
                    self.update_progress(
                        progress,
                        processed_rows,
                        total_rows,
                        all_errors
                    )
                
                # Mark as completed
                import_task.status = "completed"
                await session.commit()
                
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
                import_task.errors = json.dumps([{"error": error_msg}])
                await session.commit()
                
                self.update_state(
                    state="FAILURE",
                    meta={"error": error_msg}
                )
        
        # Dispose per-task engine if we created one as fallback
        if engine_to_dispose is not None:
            await engine_to_dispose.dispose()
    
    # Run the async function in event loop
    # Celery tasks run in a separate process, so we can create a new event loop
    print(f"Starting import task {task_id}")
    
    try:
        # Create a new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async function
        loop.run_until_complete(run_import())
        print(f"Completed import task {task_id}")
    except Exception as e:
        # Log the error and update task status
        error_msg = str(e)
        print(f"Error in import task {task_id}: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Try to update the task status in the database
        try:
            # Create a minimal sync connection to update status
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
            sync_engine = create_engine(sync_url)
            Session = sessionmaker(bind=sync_engine)
            with Session() as session:
                from app.models.import_task import ImportTask as ImportTaskModel
                task = session.query(ImportTaskModel).filter_by(task_id=task_id).first()
                if task:
                    task.status = "failed"
                    task.errors = json.dumps([{"error": error_msg}])
                    session.commit()
                    print(f"Updated task {task_id} status to failed")
        except Exception as db_error:
            print(f"Failed to update task status in database: {db_error}")
            import traceback
            traceback.print_exc()
        raise
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass

