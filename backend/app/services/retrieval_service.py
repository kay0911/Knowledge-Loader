import concurrent.futures
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from app.db.neo4j import neo4j_client
from app.models.document import DocumentChunk, Document
from app.services.embedding_service import EmbeddingService
from app.services.bm25_service import BM25Service
from app.services.rerank_service import RerankService
from app.core.logging import logger

class RetrievalService:
    @classmethod
    def retrieve_hybrid(
        cls,
        db: Session,
        query: str,
        query_vector: Optional[List[float]] = None
    ) -> Tuple[List[DocumentChunk], List[Dict[str, Any]]]:
        """
        Retrieves context chunks using a Two-Stage Retrieval Pipeline:
        STAGE 1: Document Metadata Matching (Routes query to top candidate documents via Document Metadata Summaries).
        STAGE 2: In-Document Scoped Chunk Retrieval (Dense pgvector + BM25 limited ONLY to selected candidate document IDs) + Reranking.
        Reuses pre-computed query_vector to eliminate redundant embedding API calls.
        """
        logger.info(f"Starting Two-Stage Retrieval Pipeline for query: '{query}'")
        
        # --- STAGE 1: DOCUMENT METADATA ROUTING ---
        active_docs = db.query(Document).filter(
            Document.status.in_(["READY", "SKIPPED"]),
            Document.is_enabled == True
        ).all()

        if not active_docs:
            logger.warning("No active/ready documents found in Database for retrieval.")
            return [], []

        doc_meta_list = []
        doc_map_by_id = {}
        for d in active_docs:
            doc_map_by_id[str(d.id)] = d
            meta = d.metadata_summary if d.metadata_summary else {
                "filename": d.original_file_name,
                "document_summary": f"Tài liệu {d.original_file_name}",
                "domain": "GENERAL",
                "keywords": [d.original_file_name],
                "hypothetical_questions": [f"Nội dung của {d.original_file_name}"]
            }
            meta["doc_id"] = str(d.id)
            meta["filename"] = d.original_file_name
            if hasattr(d, "summary_embedding") and d.summary_embedding is not None:
                meta["summary_embedding"] = list(d.summary_embedding)
            doc_meta_list.append(meta)

        from app.services.two_stage_retrieval_service import TwoStageRetrievalService
        stage_1_candidates = TwoStageRetrievalService.stage_1_route_documents(
            query=query,
            document_metadata_list=doc_meta_list,
            top_k_docs=3,
            db=db,
            query_vec=query_vector
        )

        target_doc_ids = [c["metadata"]["doc_id"] for c in stage_1_candidates if "doc_id" in c.get("metadata", {})]
        if not target_doc_ids:
            target_doc_ids = [str(d.id) for d in active_docs[:3]]

        selected_filenames = [doc_map_by_id[did].original_file_name for did in target_doc_ids if did in doc_map_by_id]
        logger.info(f"Stage 1 Document Routing selected target doc IDs: {target_doc_ids} ({selected_filenames})")

        # --- STAGE 2: IN-DOCUMENT SCOPED CHUNK RETRIEVAL ---
        semantic_chunks: List[DocumentChunk] = []
        bm25_chunks: List[DocumentChunk] = []

        def task_semantic():
            try:
                query_embedding = query_vector if query_vector is not None else EmbeddingService.get_embedding(query, db=db)
                return db.query(DocumentChunk).options(
                    joinedload(DocumentChunk.document)
                ).join(
                    Document, Document.id == DocumentChunk.document_id
                ).filter(
                    DocumentChunk.document_id.in_(target_doc_ids),
                    DocumentChunk.is_active == True,
                    Document.status.in_(["READY", "SKIPPED"]),
                    Document.is_enabled == True,
                    DocumentChunk.embedding.isnot(None)
                ).order_by(
                    DocumentChunk.embedding.cosine_distance(query_embedding)
                ).limit(10).all()
            except Exception as e:
                logger.error(f"Stage 2 Parallel Semantic search failed: {str(e)}", exc_info=True)
                return []

        def task_bm25():
            try:
                raw_bm25 = BM25Service.search(query, top_k=15)
                # Filter BM25 chunks strictly to target_doc_ids
                filtered_bm25 = [c for c in raw_bm25 if str(c.document_id) in target_doc_ids]
                return filtered_bm25[:10]
            except Exception as e:
                logger.error(f"Stage 2 Parallel BM25 search failed: {str(e)}", exc_info=True)
                return []

        # Execute Stage 2 Semantic & BM25 tasks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_sem = executor.submit(task_semantic)
            future_bm25 = executor.submit(task_bm25)

            semantic_chunks = future_sem.result()
            bm25_chunks = future_bm25.result()

        logger.info(f"Stage 2 Scoped In-Document Retrieval -> Semantic: {len(semantic_chunks)}, BM25: {len(bm25_chunks)}")

        # Merge & Rank candidates using Reciprocal Rank Fusion (RRF)
        fused_candidates = cls._apply_rrf_fusion(semantic_chunks, bm25_chunks, [])
        logger.info(f"Total unique RRF-fused candidate chunks: {len(fused_candidates)}")
        
        # Cohere Reranking (uses settings.RERANK_TOP_K from .env)
        reranked_chunks = RerankService.rerank(query, fused_candidates)
        logger.info(f"Final reranked search returned {len(reranked_chunks)} context chunks.")
        
        return reranked_chunks, []

    @staticmethod
    def _apply_rrf_fusion(
        semantic_chunks: List[DocumentChunk],
        bm25_chunks: List[DocumentChunk],
        graph_chunks: List[DocumentChunk],
        k: int = 60
    ) -> List[DocumentChunk]:
        """
        Applies Reciprocal Rank Fusion (RRF) algorithm to rank candidates from multiple retrievers.
        RRF_score(d) = sum(1 / (k + rank_m(d)))
        """
        scores: Dict[str, float] = {}
        chunk_map: Dict[str, DocumentChunk] = {}

        def add_ranks(chunks: List[DocumentChunk]):
            for rank, chunk in enumerate(chunks, start=1):
                c_id = str(chunk.id)
                chunk_map[c_id] = chunk
                scores[c_id] = scores.get(c_id, 0.0) + (1.0 / (k + rank))

        add_ranks(semantic_chunks)
        add_ranks(bm25_chunks)
        add_ranks(graph_chunks)

        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
        return [chunk_map[cid] for cid in sorted_ids]

    @staticmethod
    def _detect_entities_in_query(query: str) -> List[str]:
        """
        Query Neo4j for all entities, and perform substring match on the user query.
        Returns a list of matching normalized entity names.
        """
        normalized_query = query.lower()
        matched_entities = []
        
        try:
            with neo4j_client.get_session() as session:
                result = session.run("MATCH (e:Entity) RETURN e.normalized_name AS name, e.name AS raw_name")
                for record in result:
                    norm_name = record["name"]
                    raw_name = record["raw_name"]
                    # If entity is long enough and appears in query
                    if len(norm_name) > 1 and (norm_name in normalized_query or raw_name.lower() in normalized_query):
                        matched_entities.append(norm_name)
        except Exception as e:
            logger.error(f"Error listing entities from Neo4j: {str(e)}")
            
        return list(set(matched_entities))

    @staticmethod
    def _traverse_graph_for_entities(entities: List[str]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Query Neo4j to find relationships linked to these entities.
        Returns a list of chunk UUID strings (evidence) and details of graph relationships.
        """
        chunk_ids = []
        relationships = []
        
        query = """
        MATCH (s:Entity) WHERE s.normalized_name IN $entities
        MATCH (s)-[r:RELATED_TO]-(t:Entity)
        RETURN r.chunk_id AS chunk_id, 
               r.relation_name AS relation, 
               r.confidence AS confidence, 
               r.description AS description,
               s.name AS source_name, 
               t.name AS target_name
        LIMIT 10
        """
        
        try:
            with neo4j_client.get_session() as session:
                result = session.run(query, entities=entities)
                for record in result:
                    c_id = record["chunk_id"]
                    if c_id:
                        chunk_ids.append(c_id)
                        
                    relationships.append({
                        "source": record["source_name"],
                        "target": record["target_name"],
                        "relation": record["relation"],
                        "description": record["description"],
                        "confidence": record["confidence"]
                    })
        except Exception as e:
            logger.error(f"Error traversing Neo4j graph for entities: {str(e)}")
            
        return list(set(chunk_ids)), relationships
