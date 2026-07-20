import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, Index
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.postgres import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String, nullable=False)
    original_file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    status = Column(String, nullable=False) # e.g. UPLOADED, PENDING, PROCESSING, READY, FAILED, SKIPPED, DELETED
    routing_result = Column(String, nullable=True) # e.g. NEW, SKIP, UPDATED, REPROCESS
    active_version_id = Column(UUID(as_uuid=True), nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_hash = Column(String, nullable=False)
    parser_version = Column(String, nullable=True)
    chunking_version = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)
    extraction_prompt_version = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False) # e.g. PENDING, PROCESSING, READY, FAILED
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    document = relationship("Document", back_populates="versions")
    chunks = relationship("DocumentChunk", back_populates="version", cascade="all, delete-orphan")
    jobs = relationship("ProcessingJob", back_populates="version")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String, nullable=True)
    sheet_name = Column(String, nullable=True)
    row_start = Column(Integer, nullable=True)
    row_end = Column(Integer, nullable=True)
    chunk_order = Column(Integer, nullable=False)
    embedding = Column(Vector(768), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "idx_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )

    document = relationship("Document", back_populates="chunks")
    version = relationship("DocumentVersion", back_populates="chunks")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id = Column(UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True)
    job_type = Column(String, nullable=False) # e.g. INGEST, REPROCESS
    status = Column(String, nullable=False) # e.g. PENDING, PROCESSING, READY, FAILED
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    document = relationship("Document", back_populates="jobs")
    version = relationship("DocumentVersion", back_populates="jobs")
