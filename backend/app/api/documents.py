from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.postgres import get_db
from app.schemas.document import DocumentResponse, DocumentDetailResponse, DocumentChunkResponse
from app.services.document_service import DocumentService
from app.models.document import DocumentVersion, DocumentChunk
from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/documents", tags=["documents"])

def map_to_detail(doc, chunk_counts: dict) -> dict:
    versions = doc.versions
    chunks_count = 0
    target_version_id = doc.active_version_id
    if not target_version_id and versions:
        # Find latest version chunk count
        latest_version = sorted(versions, key=lambda v: v.version_number, reverse=True)[0]
        target_version_id = latest_version.id
        
    if target_version_id:
        chunks_count = chunk_counts.get(target_version_id, 0)
        
    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "original_file_name": doc.original_file_name,
        "file_path": doc.file_path,
        "file_type": doc.file_type,
        "file_hash": doc.file_hash,
        "status": doc.status,
        "is_enabled": doc.is_enabled,
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
    _, ext = file.filename.split(".")[-1], f".{file.filename.split('.')[-1]}"
    if ext.lower().replace(".", "") not in ["pdf", "docx", "doc", "xlsx", "xls", "csv", "pptx", "ppt", "md", "markdown"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Allowed formats: PDF, DOCX, XLSX, PPTX, MD.")
        
    try:
        content = await file.read()
        
        # Validate File Size Limit
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Dung lượng file vượt quá giới hạn tối đa cho phép ({settings.MAX_UPLOAD_SIZE_MB}MB)."
            )

        logger.info(f"Received upload request for file: {file.filename} ({len(content)} bytes)")
        doc = DocumentService.ingest_document(db, file.filename, content)
        return doc
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Failed to upload document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")

@router.get("", response_model=List[DocumentDetailResponse])
def list_documents(db: Session = Depends(get_db)):
    docs = DocumentService.get_documents(db)
    
    # Pre-calculate target version IDs for batch count querying
    version_ids = []
    for doc in docs:
        if doc.active_version_id:
            version_ids.append(doc.active_version_id)
        elif doc.versions:
            latest_version = sorted(doc.versions, key=lambda v: v.version_number, reverse=True)[0]
            version_ids.append(latest_version.id)
            
    chunk_counts = {}
    if version_ids:
        from sqlalchemy import func
        counts_res = db.query(
            DocumentChunk.document_version_id,
            func.count(DocumentChunk.id)
        ).filter(
            DocumentChunk.document_version_id.in_(version_ids)
        ).group_by(
            DocumentChunk.document_version_id
        ).all()
        chunk_counts = {r[0]: r[1] for r in counts_res}
        
    return [map_to_detail(doc, chunk_counts) for doc in docs]

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = DocumentService.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    version_ids = []
    if doc.active_version_id:
        version_ids.append(doc.active_version_id)
    elif doc.versions:
        latest_version = sorted(doc.versions, key=lambda v: v.version_number, reverse=True)[0]
        version_ids.append(latest_version.id)
        
    chunk_counts = {}
    if version_ids:
        from sqlalchemy import func
        counts_res = db.query(
            DocumentChunk.document_version_id,
            func.count(DocumentChunk.id)
        ).filter(
            DocumentChunk.document_version_id.in_(version_ids)
        ).group_by(
            DocumentChunk.document_version_id
        ).all()
        chunk_counts = {r[0]: r[1] for r in counts_res}
        
    return map_to_detail(doc, chunk_counts)

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
def get_document_chunks(document_id: str, db: Session = Depends(get_db)):
    doc = DocumentService.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = DocumentService.get_document_chunks(db, document_id)
    return chunks

@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    success = DocumentService.delete_document(db, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}

@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(document_id: str, db: Session = Depends(get_db)):
    try:
        doc = DocumentService.reprocess_document(db, document_id)
        return doc
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Failed to reprocess document {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reprocess document: {str(e)}")

@router.post("/{document_id}/versions/{version_id}/activate", response_model=DocumentDetailResponse)
def activate_document_version(document_id: str, version_id: str, db: Session = Depends(get_db)):
    try:
        doc = DocumentService.activate_version(db, document_id, version_id)
        
        version_ids = [doc.active_version_id] if doc.active_version_id else []
        chunk_counts = {}
        if version_ids:
            from sqlalchemy import func
            counts_res = db.query(
                DocumentChunk.document_version_id,
                func.count(DocumentChunk.id)
            ).filter(
                DocumentChunk.document_version_id.in_(version_ids)
            ).group_by(
                DocumentChunk.document_version_id
            ).all()
            chunk_counts = {r[0]: r[1] for r in counts_res}
            
        return map_to_detail(doc, chunk_counts)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Failed to activate version {version_id} for doc {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to activate version: {str(e)}")

@router.post("/{document_id}/toggle", response_model=DocumentDetailResponse)
def toggle_document_enablement(document_id: str, db: Session = Depends(get_db)):
    try:
        doc = DocumentService.toggle_enablement(db, document_id)
        version_ids = [doc.active_version_id] if doc.active_version_id else []
        chunk_counts = {}
        if version_ids:
            from sqlalchemy import func
            counts_res = db.query(
                DocumentChunk.document_version_id,
                func.count(DocumentChunk.id)
            ).filter(
                DocumentChunk.document_version_id.in_(version_ids)
            ).group_by(
                DocumentChunk.document_version_id
            ).all()
            chunk_counts = {r[0]: r[1] for r in counts_res}
            
        return map_to_detail(doc, chunk_counts)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Failed to toggle enablement for doc {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to toggle document enablement: {str(e)}")



