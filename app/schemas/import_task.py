from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ImportTaskResponse(BaseModel):
    id: int
    task_id: str
    status: str
    progress: float
    total_rows: int
    processed_rows: int
    errors: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

