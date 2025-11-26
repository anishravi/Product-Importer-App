from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from app.database import Base


class ImportTask(Base):
    __tablename__ = "import_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, default="pending", nullable=False)  # pending, processing, completed, failed
    progress = Column(Float, default=0.0, nullable=False)  # 0.0 to 100.0
    total_rows = Column(Integer, default=0, nullable=False)
    processed_rows = Column(Integer, default=0, nullable=False)
    errors = Column(Text, nullable=True)  # JSON string of errors
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

