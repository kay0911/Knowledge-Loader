import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.postgres import engine, Base
from app.api.documents import router as documents_router
from app.workers.document_worker import start_worker
from app.core.logging import logger

from sqlalchemy import text

# Initialize database tables
logger.info("Initializing database tables...")
Base.metadata.create_all(bind=engine)

# Running migrations to support vector column and HNSW index if they don't exist
try:
    logger.info("Running database migrations for Step 2 (pgvector HNSW index)...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding VECTOR(768);"))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops);
        """))
    logger.info("Migrations completed successfully.")
except Exception as migration_err:
    logger.error(f"Migration failed: {str(migration_err)}")

app = FastAPI(
    title="GraphRAG Knowledge Loader MVP API",
    description="Backend service for loading and processing documents for Knowledge Retrieval.",
    version="1.0.0"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In MVP we allow all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    logger.info("Application starting up...")
    start_worker()

@app.get("/")
def read_root():
    return {"message": "Welcome to the GraphRAG Knowledge Loader API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Include routers
app.include_router(documents_router, prefix="/api")
