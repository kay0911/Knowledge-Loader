import time
import threading
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.db.postgres import SessionLocal
from app.models.document import ProcessingJob, Document, DocumentVersion, DocumentChunk
from app.services.parser_service import ParserService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.graph_extraction_service import GraphExtractionService
from app.services.graph_service import GraphService
from app.services.bm25_service import BM25Service
from app.services.delta_ingestion_service import DeltaIngestionService
from app.core.logging import logger

def process_job(db: Session, job: ProcessingJob):
    logger.info(f"Processing job {job.id} for document {job.document_id}")
    try:
        # Update statuses to PROCESSING
        job.status = "PROCESSING"
        job.started_at = func.now()
        
        doc = db.query(Document).filter(Document.id == job.document_id).first()
        version = db.query(DocumentVersion).filter(DocumentVersion.id == job.document_version_id).first()
        if not version and doc:
            version = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id, DocumentVersion.is_active == True).first()
        
        if doc:
            doc.status = "PROCESSING"
        if version:
            version.status = "PROCESSING"
            
        db.commit()
        
        # Parse file from disk into NormalizedBlocks
        normalized_blocks = ParserService.parse(doc.file_path, doc.file_type)
        
        # Chunk normalized blocks using Dual Chunker Pipeline
        chunks_data = ChunkingService.chunk_normalized_blocks(normalized_blocks)
        
        # Calculate Chunk Hashes and run Delta Processing
        reused_chunks_data, delta_new_chunks_data = DeltaIngestionService.filter_existing_chunks(db, chunks_data)
        
        # Save chunks to PostgreSQL
        chunks = []
        for item in chunks_data:
            ch_hash = item.get("chunk_hash") or DeltaIngestionService.compute_chunk_hash(item["content"])
            chunk = DocumentChunk(
                document_id=doc.id,
                document_version_id=version.id,
                content=item["content"],
                page_number=item.get("page_number"),
                page_start=item.get("page_start"),
                page_end=item.get("page_end"),
                heading=item.get("heading"),
                heading_path=item.get("heading_path"),
                sheet_name=item.get("sheet_name"),
                row_start=item.get("row_start"),
                row_end=item.get("row_end"),
                chunk_order=item["chunk_order"],
                chunk_hash=ch_hash,
                is_active=True
            )
            
            # Check if embedding can be reused ($0 cost) or generated
            if item in reused_chunks_data and item.get("embedding"):
                logger.info(f"Reusing existing embedding for chunk {chunk.chunk_order} (Hash: {ch_hash[:8]}...) - Skip AI cost ($0)")
                chunk.embedding = item["embedding"]
            else:
                try:
                    chunk.embedding = EmbeddingService.get_embedding(chunk.content)
                except Exception as emb_err:
                    logger.error(f"Failed to generate embedding for chunk {chunk.chunk_order}: {str(emb_err)}")
                    chunk.embedding = None
                
            db.add(chunk)
            chunks.append((chunk, item in delta_new_chunks_data))
            
        db.flush() # Populate chunk IDs to link in Neo4j evidence
        
        # Smart Delta Re-summary Algorithm (<20% changed chunks reuses existing metadata, >=20% triggers LLM summary)
        total_chunks_count = len(chunks_data)
        changed_chunks_count = len(delta_new_chunks_data)
        change_ratio = changed_chunks_count / max(total_chunks_count, 1)

        should_resummarize = True
        if doc.metadata_summary and change_ratio < 0.20:
            should_resummarize = False
            logger.info(
                f"Minor delta update for {doc.original_file_name}: "
                f"{changed_chunks_count}/{total_chunks_count} changed chunks ({change_ratio*100:.1f}% < 20%). "
                f"Reusing existing Document Metadata Summary ($0 LLM Cost)."
            )
        else:
            logger.info(
                f"Generating/Updating Document Metadata Summary for {doc.original_file_name}: "
                f"{changed_chunks_count}/{total_chunks_count} changed chunks ({change_ratio*100:.1f}% >= 20% or missing metadata)."
            )

        if should_resummarize:
            try:
                from app.services.document_summary_service import DocumentSummaryService
                doc_meta = DocumentSummaryService.generate_document_metadata(doc.original_file_name, chunks_data, db=db)
                doc.metadata_summary = doc_meta
                logger.info(f"Successfully generated & saved Document Metadata Summary for {doc.original_file_name}")
            except Exception as meta_err:
                logger.error(f"Failed to generate Document Metadata Summary for {doc.original_file_name}: {str(meta_err)}")

        # MANDATORY EMBEDDING VERIFICATION & AUTO-RETRY PASS
        # Ensure 100% of chunks for this version have valid vector embeddings before marking READY
        unembedded_chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == version.id,
            DocumentChunk.embedding.is_(None)
        ).all()

        if unembedded_chunks:
            logger.warning(
                f"Embedding Verification Warning: Found {len(unembedded_chunks)}/{total_chunks_count} chunks "
                f"with missing embeddings for {doc.original_file_name}. Initiating automatic retry backfill..."
            )
            for retry_attempt in range(1, 4):
                if not unembedded_chunks:
                    break
                logger.info(f"Retrying embedding backfill attempt {retry_attempt}/3 for {len(unembedded_chunks)} chunks...")
                still_missing = []
                for chunk in unembedded_chunks:
                    try:
                        emb = EmbeddingService.get_embedding(chunk.content, db=db)
                        if emb and any(v != 0.0 for v in emb):
                            chunk.embedding = emb
                        else:
                            still_missing.append(chunk)
                    except Exception as backfill_err:
                        logger.warning(f"Backfill retry failed for chunk {chunk.id}: {str(backfill_err)}")
                        still_missing.append(chunk)
                
                db.commit()
                unembedded_chunks = still_missing
                if unembedded_chunks:
                    time.sleep(2)  # Wait 2s for rate limit key cooldown before retry

        # Final Strict Verification Assertion
        final_unembedded_count = db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == version.id,
            DocumentChunk.embedding.is_(None)
        ).count()

        if final_unembedded_count > 0:
            err_msg = f"Processing failed: {final_unembedded_count}/{total_chunks_count} chunks failed vector embedding generation due to API rate limit."
            logger.error(f"STRICT EMBEDDING CHECK FAILED for '{doc.original_file_name}': {err_msg}")
            version.status = "FAILED"
            version.error_message = err_msg
            doc.status = "FAILED"
            doc.error_message = err_msg
            job.status = "FAILED"
            job.error_message = err_msg
            db.commit()
            return

        # Deactivate old versions and their chunks if processing succeeded
        if version:
            db.query(DocumentVersion).filter(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.id != version.id
            ).update({"is_active": False})
            
            invalidated_chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.document_version_id != version.id,
                DocumentChunk.is_active == True
            ).all()
            
            invalidated_ids = [str(c.id) for c in invalidated_chunks]
            
            db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id,
                DocumentChunk.document_version_id != version.id
            ).update({"is_active": False})
            
            version.is_active = True
            version.status = "READY"
            
            # Clean up old Neo4j graph version evidence & orphan entities
            try:
                GraphService.remove_invalidated_chunk_evidence(invalidated_ids)
                GraphService.remove_old_versions_evidence(str(doc.id), str(version.id))
            except Exception as graph_clean_err:
                logger.error(f"Failed to clear old versions Neo4j evidence for document {doc.id}: {str(graph_clean_err)}")
            
        if doc:
            doc.active_version_id = version.id
            doc.status = "READY"
            doc.error_message = None
            
        job.status = "READY"
        job.completed_at = func.now()
        db.commit()
        
        # Rebuild BM25 index after document is successfully READY
        BM25Service.rebuild_index()
        
        logger.info(f"Successfully processed document '{doc.original_file_name}' (Job: {job.id}) - 100% Chunks Verified Embedded")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing job {job.id}: {str(e)}", exc_info=True)
        try:
            job.status = "FAILED"
            job.error_message = str(e)
            job.completed_at = func.now()
            
            doc = db.query(Document).filter(Document.id == job.document_id).first()
            version = db.query(DocumentVersion).filter(DocumentVersion.id == job.document_version_id).first()
            if doc:
                doc.status = "FAILED"
                doc.error_message = str(e)
            if version:
                version.status = "FAILED"
                
            db.commit()
        except Exception as inner_e:
            logger.error(f"Error setting job status to FAILED: {str(inner_e)}")

def audit_and_repair_unembedded_chunks(db: Session):
    """
    Self-Healing Audit: Scans active chunks across all READY documents for any missing embeddings
    (e.g., from past rate limit interrupts) and automatically repairs them.
    """
    try:
        unembedded = db.query(DocumentChunk).join(Document, DocumentChunk.document_id == Document.id).filter(
            Document.status == "READY",
            DocumentChunk.is_active == True,
            DocumentChunk.embedding.is_(None)
        ).all()
        
        if unembedded:
            logger.info(f"Self-Healing Audit: Found {len(unembedded)} un-embedded active chunks in READY documents. Repairing...")
            repaired_count = 0
            for chunk in unembedded:
                try:
                    emb = EmbeddingService.get_embedding(chunk.content, db=db)
                    if emb and any(v != 0.0 for v in emb):
                        chunk.embedding = emb
                        repaired_count += 1
                        db.commit()
                        logger.info(f"Self-Healing Audit: Repaired embedding for Chunk {chunk.id}")
                except Exception as repair_err:
                    logger.error(f"Self-Healing Audit repair failed for Chunk {chunk.id}: {str(repair_err)}")
            if repaired_count > 0:
                logger.info(f"Self-Healing Audit: Successfully repaired {repaired_count}/{len(unembedded)} missing embeddings.")
    except Exception as audit_err:
        logger.error(f"Self-Healing Audit encountered error: {str(audit_err)}")

def worker_loop():
    logger.info("Background worker loop started.")
    loop_count = 0
    while True:
        db = SessionLocal()
        try:
            loop_count += 1
            # Run Self-Healing Audit every 30 loop iterations (~1 min)
            if loop_count % 30 == 1:
                audit_and_repair_unembedded_chunks(db)

            # Query oldest pending job
            job = db.query(ProcessingJob).filter(ProcessingJob.status == "PENDING").order_by(ProcessingJob.created_at.asc()).first()
            if job:
                process_job(db, job)
        except Exception as e:
            logger.error(f"Exception in worker loop: {str(e)}")
        finally:
            db.close()
        time.sleep(2)

def start_worker():
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()
    logger.info("Background worker thread launched with Self-Healing Audit enabled.")
