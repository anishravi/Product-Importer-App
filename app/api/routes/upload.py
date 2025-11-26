import uuid
import json
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.import_task import ImportTask
from app.schemas.import_task import ImportTaskResponse
from app.tasks.import_task import import_csv_task
from sqlalchemy import select

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("", response_model=ImportTaskResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload and process a CSV file."""
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    # Read file content
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Create import task record
    import_task = ImportTask(
        task_id=task_id,
        status="pending",
        progress=0.0,
        total_rows=0,
        processed_rows=0
    )
    db.add(import_task)
    await db.commit()
    await db.refresh(import_task)
    
    # Start Celery task
    try:
        # For large files, we might need to encode the content
        # Celery with JSON serializer can handle bytes, but let's be safe
        import base64
        content_b64 = base64.b64encode(content).decode('utf-8')
        
        # Start the Celery task
        celery_result = import_csv_task.delay(content_b64, task_id)
        print(f"Started Celery task {celery_result.id} for import task {task_id}")
    except Exception as e:
        import_task.status = "failed"
        import_task.errors = f"Failed to start task: {str(e)}"
        await db.commit()
        print(f"Error starting Celery task: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start import: {str(e)}")
    
    return ImportTaskResponse.model_validate(import_task)


@router.get("/task/{task_id}", response_model=ImportTaskResponse)
async def get_upload_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get the status of an upload task."""
    result = await db.execute(
        select(ImportTask).where(ImportTask.task_id == task_id)
    )
    import_task = result.scalar_one_or_none()
    
    if not import_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Also check Celery task status for real-time updates
    # Note: We need to find the Celery task by searching for tasks with our task_id in the result
    # For now, we rely on the database updates from the Celery task itself
    # The Celery task updates the ImportTask record directly, so we don't need to query Celery
    
    return ImportTaskResponse.model_validate(import_task)

