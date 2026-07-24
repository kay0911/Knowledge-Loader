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
        from sqlalchemy.orm import selectinload
        return db.query(Document).options(selectinload(Document.versions)).filter(Document.status != "DELETED").order_by(Document.created_at.desc()).all()

    @staticmethod
    def get_document_by_id(db: Session, document_id: str) -> Document:
        from sqlalchemy.orm import selectinload
        return db.query(Document).options(selectinload(Document.versions)).filter(Document.id == document_id).first()

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

    @staticmethod
    def delete_document(db: Session, document_id: str) -> bool:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return False
            
        # 1. Update Document status to DELETED
        doc.status = "DELETED"
        doc.active_version_id = None
        
        # 2. Delete all related chunks, versions, and processing jobs in PostgreSQL
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.query(DocumentVersion).filter(DocumentVersion.document_id == document_id).delete()
        db.query(ProcessingJob).filter(ProcessingJob.document_id == document_id).delete()
        
        db.commit()
        
        # 3. Remove from Neo4j
        try:
            from app.services.graph_service import GraphService
            GraphService.remove_document_evidence(document_id)
        except Exception as neo_err:
            logger.error(f"Failed to clear Neo4j evidence for deleted document {document_id}: {str(neo_err)}")
            
        # 4. Rebuild BM25 index
        try:
            from app.services.bm25_service import BM25Service
            BM25Service.rebuild_index()
        except Exception as bm_err:
            logger.error(f"Failed to rebuild BM25 index after deleting document {document_id}: {str(bm_err)}")
            
        return True

    @staticmethod
    def reprocess_document(db: Session, document_id: str) -> Document:
        doc = db.query(Document).filter(Document.id == document_id, Document.status != "DELETED").first()
        if not doc:
            raise ValueError("Document not found or has been deleted.")
            
        # Resolve file path dynamically to support old Windows paths inside Linux container
        filename = os.path.basename(doc.file_path.replace("\\", "/"))
        resolved_path = os.path.join(settings.UPLOAD_DIR, filename)
        
        if not os.path.exists(resolved_path):
            if os.path.exists(doc.file_path):
                resolved_path = doc.file_path
            else:
                raise ValueError(f"Original source file not found at {resolved_path}")
            
        with open(resolved_path, "rb") as f:
            file_content = f.read()
            
        # Update path to resolved container path
        doc.file_path = resolved_path
        file_hash = doc.file_hash
        
        # Mark document status as PENDING
        doc.status = "PENDING"
        doc.routing_result = "REPROCESS"
        
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
            job_type="REPROCESS",
            status="PENDING"
        )
        db.add(job)
        
        db.commit()
        db.refresh(doc)
        logger.info(f"Triggered reprocessing for document {doc.original_file_name}. New version: v{new_version_num}. Created job ID: {job.id}")
        return doc

    @staticmethod
    def activate_version(db: Session, document_id: str, version_id: str) -> Document:
        doc = db.query(Document).filter(Document.id == document_id, Document.status != "DELETED").first()
        if not doc:
            raise ValueError("Document not found or has been deleted.")
            
        target_version = db.query(DocumentVersion).filter(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id
        ).first()
        
        if not target_version:
            raise ValueError("Document version not found.")
            
        if target_version.status != "READY":
            raise ValueError("Only versions with status READY can be activated.")
            
        # 1. Update doc active_version_id
        doc.active_version_id = target_version.id
        doc.status = "READY"
        
        # 2. Deactivate all versions of this document, activate target_version
        db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document_id
        ).update({"is_active": False})
        target_version.is_active = True
        
        # 3. Deactivate all chunks of this document, activate target_version chunks
        db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).update({"is_active": False})
        
        db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == target_version.id
        ).update({"is_active": True})
        
        db.commit()
        db.refresh(doc)
        logger.info(f"Activated version v{target_version.version_number} (ID: {version_id}) for document {doc.original_file_name}")
        
        # 4. Rebuild BM25 index to reflect new active chunks
        try:
            from app.services.bm25_service import BM25Service
            BM25Service.rebuild_index()
        except Exception as bm_err:
            logger.error(f"Failed to rebuild BM25 index after activating version: {str(bm_err)}")
            
        return doc



