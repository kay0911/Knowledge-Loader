import os
import uuid
from sqlalchemy.orm import Session
from app.models.document import Document, DocumentVersion, ProcessingJob, DocumentChunk
from app.services.routing_service import RoutingService
from app.core.config import settings
from app.core.logging import logger

class DocumentService:
    @staticmethod
    def ingest_document(db: Session, file_name: str, file_content: bytes) -> Document:
        file_hash = RoutingService.calculate_hash(file_content)
        routing = RoutingService.determine_routing(db, file_name, file_hash)
        
        # Split file name and extension
        name, ext = os.path.splitext(file_name)
        file_type = ext.lower().replace(".", "")
        
        if routing == "SKIP":
            # Get existing document and update routing/status to represent SKIP
            existing_doc = db.query(Document).filter(
                Document.original_file_name == file_name,
                Document.status != "DELETED"
            ).first()
            if existing_doc:
                existing_doc.routing_result = "SKIP"
                existing_doc.status = "SKIPPED"
                db.commit()
                db.refresh(existing_doc)
                return existing_doc
        
        # Save file to disk
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        unique_file_name = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_file_name)
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        # Determine document details based on routing
        if routing == "NEW":
            doc = Document(
                file_name=unique_file_name,
                original_file_name=file_name,
                file_path=file_path,
                file_type=file_type,
                file_hash=file_hash,
                status="PENDING",
                routing_result="NEW"
            )
            db.add(doc)
            db.flush() # Generate ID
            
            version = DocumentVersion(
                document_id=doc.id,
                version_number=1,
                file_hash=file_hash,
                parser_version="v1",
                chunking_version="v1",
                is_active=False,
                status="PENDING"
            )
            db.add(version)
            db.flush()
            
            doc.active_version_id = None # Set active version to None until processed
            
        else: # UPDATED
            doc = db.query(Document).filter(
                Document.original_file_name == file_name,
                Document.status != "DELETED"
            ).first()
            
            # Update main doc record
            doc.file_name = unique_file_name
            doc.file_path = file_path
            doc.file_hash = file_hash
            doc.status = "PENDING"
            doc.routing_result = "UPDATED"
            
            # Find last version number
            last_version = db.query(DocumentVersion).filter(
                DocumentVersion.document_id == doc.id
            ).order_by(DocumentVersion.version_number.desc()).first()
            new_version_num = (last_version.version_number + 1) if last_version else 1
            
            version = DocumentVersion(
                document_id=doc.id,
                version_number=new_version_num,
                file_hash=file_hash,
                parser_version="v1",
                chunking_version="v1",
                is_active=False,
                status="PENDING"
            )
            db.add(version)
            db.flush()

        # Create processing job
        job = ProcessingJob(
            document_id=doc.id,
            document_version_id=version.id,
            job_type="INGEST",
            status="PENDING"
        )
        db.add(job)
        
        db.commit()
        db.refresh(doc)
        logger.info(f"Ingested document {file_name}. Routing: {routing}. Created job ID: {job.id}")
        return doc

    @staticmethod
    def get_documents(db: Session):
        return db.query(Document).filter(Document.status != "DELETED").order_by(Document.created_at.desc()).all()

    @staticmethod
    def get_document_by_id(db: Session, document_id: str) -> Document:
        return db.query(Document).filter(Document.id == document_id).first()

    @staticmethod
    def get_document_chunks(db: Session, document_id: str) -> list:
        # Get chunks for the active version of the document
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc or not doc.active_version_id:
            # If no active version, return empty or return all chunks of the latest version
            latest_version = db.query(DocumentVersion).filter(
                DocumentVersion.document_id == document_id
            ).order_by(DocumentVersion.version_number.desc()).first()
            if latest_version:
                return db.query(DocumentChunk).filter(
                    DocumentChunk.document_version_id == latest_version.id
                ).order_by(DocumentChunk.chunk_order).all()
            return []
        return db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == doc.active_version_id,
            DocumentChunk.is_active == True
        ).order_by(DocumentChunk.chunk_order).all()
