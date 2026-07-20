from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.postgres import get_db
from app.schemas.document import DocumentResponse, DocumentDetailResponse, DocumentChunkResponse
from app.services.document_service import DocumentService
from app.models.document import DocumentVersion, DocumentChunk
from app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["documents"])

def map_to_detail(db: Session, doc) -> dict:
    versions = doc.versions
    chunks_count = 0
    if doc.active_version_id:
        chunks_count = db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == doc.active_version_id
        ).count()
    elif versions:
        # Find latest version chunk count
        latest_version = sorted(versions, key=lambda v: v.version_number, reverse=True)[0]
        chunks_count = db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == latest_version.id
        ).count()
        
    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "original_file_name": doc.original_file_name,
        "file_path": doc.file_path,
        "file_type": doc.file_type,
        "file_hash": doc.file_hash,
        "status": doc.status,
        "routing_result": doc.routing_result,
        "active_version_id": doc.active_version_id,
        "error_message": doc.error_message,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "versions": versions,
        "chunks_count": chunks_count
    }

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
        
    # Check extension
    _, ext = os_ext = file.filename.split(".")[-1], f".{file.filename.split('.')[-1]}"
    if ext.lower().replace(".", "") not in ["pdf", "docx", "xlsx"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF, DOCX, XLSX are allowed.")
        
    try:
        content = await file.read()
        logger.info(f"Received upload request for file: {file.filename} ({len(content)} bytes)")
        doc = DocumentService.ingest_document(db, file.filename, content)
        return doc
    except Exception as e:
        logger.error(f"Failed to upload document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")

@router.get("", response_model=List[DocumentDetailResponse])
def list_documents(db: Session = Depends(get_db)):
    docs = DocumentService.get_documents(db)
    return [map_to_detail(db, doc) for doc in docs]

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = DocumentService.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return map_to_detail(db, doc)

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
def get_document_chunks(document_id: str, db: Session = Depends(get_db)):
    doc = DocumentService.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = DocumentService.get_document_chunks(db, document_id)
    return chunks
