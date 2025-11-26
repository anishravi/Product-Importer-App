# Product Importer Web Application

A scalable Python web application for importing products from CSV files, managing products, and configuring webhooks.

## Features

- **CSV Import**: Upload large CSV files (500K+ records) with real-time progress tracking
- **Product Management**: Full CRUD operations with filtering and pagination
- **Bulk Operations**: Bulk delete with confirmation
- **Webhook Configuration**: Manage webhooks with test functionality

## Tech Stack

- **FastAPI**: Modern, fast web framework
- **Celery**: Distributed task queue
- **PostgreSQL**: Relational database
- **Redis**: Message broker and cache
- **SQLAlchemy**: ORM
- **WebSockets**: Real-time updates

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create Environment File**
   Create a `.env` file in the root directory with the following content:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/product_importer
   REDIS_URL=redis://localhost:6379/0
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   SECRET_KEY=your-secret-key-here-change-in-production
   DEBUG=True
   ```

3. **Start Docker Services**
   ```bash
   docker-compose up -d
   ```

4. **Run Database Migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start FastAPI Server**
   ```bash
   python run.py
   # Or: uvicorn app.main:app --reload
   ```

6. **Start Celery Worker** (in separate terminal)
   ```bash
   celery -A celery_app worker --loglevel=info
   ```

7. **Access the Application**
   - Web UI: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Usage

1. Open `http://localhost:8000` in your browser
2. Upload CSV files via the upload interface
3. Manage products through the web interface
4. Configure webhooks for product events

## CSV Format

The CSV file should have the following columns:
- `sku`: Product SKU (unique, case-insensitive)
- `name`: Product name
- `description`: Product description
- `active`: Active status (true/false)

Example:
```csv
sku,name,description,active
ABC123,Product 1,Description 1,true
XYZ789,Product 2,Description 2,false
```

## API Documentation

FastAPI provides automatic API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

