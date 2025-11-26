from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import products, upload, bulk, webhooks
from app.api.websocket_route import router as websocket_router
from app.database import engine, Base
import os
import asyncio
from app.api.redis_progress import redis_progress_subscriber

app = FastAPI(
    title="Product Importer API",
    description="A scalable product import and management system",
    version="1.0.0"
)

# Include routers
app.include_router(products.router)
app.include_router(upload.router)
app.include_router(bulk.router)
app.include_router(webhooks.router)
app.include_router(websocket_router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "Product Importer API", "docs": "/docs"}


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    async with engine.begin() as conn:
        # In production, use Alembic migrations instead
        # await conn.run_sync(Base.metadata.create_all)
        pass

    # Start Redis subscriber that forwards progress messages to WebSocket manager
    try:
        app.state._redis_progress_task = asyncio.create_task(redis_progress_subscriber())
    except Exception:
        pass


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    # Cancel background redis subscriber if running
    task = getattr(app.state, '_redis_progress_task', None)
    if task:
        task.cancel()
        try:
            await task
        except Exception:
            pass

    await engine.dispose()

