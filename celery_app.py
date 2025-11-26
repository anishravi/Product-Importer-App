from celery import Celery
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

celery_app = Celery(
    "product_importer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
)

# Create a reusable async engine and async sessionmaker for worker processes
# so tasks can reuse the same engine instead of creating/disposing per task.
try:
    async_engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    # Attach to celery_app so tasks can import the sessionmaker
    celery_app.async_engine = async_engine
    celery_app.async_session = async_session
except Exception as e:
    # If engine creation fails at import time, print a warning and let tasks
    # create their own engines as a fallback.
    print(f"Warning: could not create async engine at import: {e}")

# Import tasks after celery_app is created to avoid circular imports
# This ensures celery_app is available when the task decorator is evaluated
try:
    import app.tasks.import_task  # noqa: F401
except ImportError as e:
    print(f"Warning: Could not import tasks: {e}")

