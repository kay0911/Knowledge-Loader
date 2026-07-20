import hashlib
from sqlalchemy.orm import Session
from app.models.document import Document
from app.core.logging import logger

class RoutingService:
    @staticmethod
    def calculate_hash(file_content: bytes) -> str:
        """Calculate MD5 hash of file content."""
        return hashlib.md5(file_content).hexdigest()

    @staticmethod
    def determine_routing(db: Session, file_name: str, file_hash: str) -> str:
        """
        Determine document routing status: NEW, SKIP, UPDATED, or REPROCESS.
        """
        # Find document by original name (acting as the unique business identifier for simplicity in MVP)
        existing_doc = db.query(Document).filter(
            Document.original_file_name == file_name,
            Document.status != "DELETED"
        ).first()
        
        if not existing_doc:
            logger.info(f"Routing logic: Document '{file_name}' not found. Routing to NEW.")
            return "NEW"

        # If it exists, compare hashes
        if existing_doc.file_hash == file_hash:
            logger.info(f"Routing logic: Document '{file_name}' hash matches current active version. Routing to SKIP.")
            return "SKIP"
        else:
            logger.info(f"Routing logic: Document '{file_name}' hash differs. Routing to UPDATED.")
            return "UPDATED"
