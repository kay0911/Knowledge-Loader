import os
import ssl
import urllib3
import requests

# Bypass corporate SSL inspection certificate verification for Gemini / LLM HTTP requests
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PYTHONHTTPSVERIFY'] = '0'

old_merge_environment_settings = requests.Session.merge_environment_settings
def merge_environment_settings(self, url, proxies, stream, verify, cert):
    return old_merge_environment_settings(self, url, proxies, stream, False, cert)
requests.Session.merge_environment_settings = merge_environment_settings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.postgres import engine, Base
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.keys import router as keys_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.workers.document_worker import start_worker
from app.core.logging import logger
from app.core.config import settings
from app.core.security import hash_password

from sqlalchemy import text
from app.models.document import Document, DocumentVersion, DocumentChunk, ProcessingJob
from app.models.chat import ChatLog
from app.models.llm_key import LLMKey
from app.models.user import User
from app.db.postgres import SessionLocal

# Ensure vector extension exists before table creation
try:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
except Exception as ext_err:
    logger.warning(f"Could not create vector extension: {ext_err}")

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
        # Add session_id & user_id columns to chat_logs if they don't exist, and assign existing logs to Admin
        logger.info("Running database migrations for ChatLog session_id & user_id...")
        conn.execute(text("ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS session_id UUID;"))
        conn.execute(text("ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS user_id UUID;"))
        conn.execute(text("UPDATE chat_logs SET session_id = id WHERE session_id IS NULL;"))
        conn.execute(text("""
            UPDATE chat_logs 
            SET user_id = (SELECT id FROM users WHERE role = 'ADMIN' ORDER BY created_at ASC LIMIT 1)
            WHERE user_id IS NULL AND EXISTS (SELECT 1 FROM users WHERE role = 'ADMIN');
        """))
        logger.info("Running database migrations for Document metadata_summary...")
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata_summary JSON;"))
        conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary_embedding vector(768);"))
        conn.execute(text("ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS question_embedding vector(768);"))
        logger.info("Running database migrations for DocumentChunk metadata columns...")
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS heading_path JSON;"))
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_start INTEGER;"))
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS page_end INTEGER;"))
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS chunk_hash VARCHAR(64);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_document_chunks_chunk_hash ON document_chunks(chunk_hash);"))
    logger.info("Migrations completed successfully.")
except Exception as migration_err:
    logger.error(f"Migration failed: {str(migration_err)}")

def ensure_initial_admin():
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.role == "ADMIN").first()
        if not admin_user:
            logger.info("No ADMIN user found. Seeding initial default Admin account...")
            initial_admin = User(
                username=settings.INITIAL_ADMIN_USERNAME,
                email="admin@knowledge.loader",
                full_name="Quản trị viên Hệ thống",
                hashed_password=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                role="ADMIN",
                is_active=True
            )
            db.add(initial_admin)
            db.commit()
            logger.info(f"Initial Admin created: Username='{settings.INITIAL_ADMIN_USERNAME}', Password='{settings.INITIAL_ADMIN_PASSWORD}'")
    except Exception as e:
        logger.error(f"Error seeding initial admin account: {str(e)}")
    finally:
        db.close()

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
    ensure_initial_admin()
    start_worker()

@app.get("/")
def read_root():
    return {"message": "Welcome to the GraphRAG Knowledge Loader API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(documents_router, prefix="/api")
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(keys_router, prefix="/api")
