import concurrent.futures
from typing import List, Tuple, Dict, Any
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
        query: str
    ) -> Tuple[List[DocumentChunk], List[Dict[str, Any]]]:
        """
        Retrieves context chunks using a Parallel Hybrid Search & RRF Fusion pipeline:
        1. Parallel Execution of Semantic Search, BM25, and Neo4j Graph Search via ThreadPoolExecutor.
        2. Reciprocal Rank Fusion (RRF) to score & rank candidates.
        3. Reranking via Cohere Cross-Encoder.
        """
        logger.info(f"Starting parallel hybrid retrieval for query: '{query}'")
        
        semantic_chunks: List[DocumentChunk] = []
        bm25_chunks: List[DocumentChunk] = []
        graph_chunks: List[DocumentChunk] = []
        graph_relationships: List[Dict[str, Any]] = []

        def task_semantic():
            try:
                query_embedding = EmbeddingService.get_embedding(query)
                return db.query(DocumentChunk).options(
                    joinedload(DocumentChunk.document)
                ).join(
                    Document, Document.id == DocumentChunk.document_id
                ).filter(
                    DocumentChunk.is_active == True,
                    Document.status == "READY",
                    Document.is_enabled == True,
                    DocumentChunk.embedding.isnot(None)
                ).order_by(
                    DocumentChunk.embedding.cosine_distance(query_embedding)
                ).limit(10).all()
            except Exception as e:
                logger.error(f"Parallel Semantic search failed: {str(e)}", exc_info=True)
                return []

        def task_bm25():
            try:
                return BM25Service.search(query, top_k=10)
            except Exception as e:
                logger.error(f"Parallel BM25 search failed: {str(e)}", exc_info=True)
                return []

        def task_graph():
            try:
                detected_entities = cls._detect_entities_in_query(query)
                if not detected_entities:
                    return [], []
                logger.info(f"Detected entities in query: {detected_entities}")
                chunk_ids, rels = cls._traverse_graph_for_entities(detected_entities)
                if not chunk_ids:
                    return [], rels
                chunks = db.query(DocumentChunk).options(
                    joinedload(DocumentChunk.document)
                ).join(
                    Document, Document.id == DocumentChunk.document_id
                ).filter(
                    DocumentChunk.id.in_(chunk_ids),
                    DocumentChunk.is_active == True,
                    Document.status == "READY",
                    Document.is_enabled == True
                ).all()
                return chunks, rels
            except Exception as e:
                logger.error(f"Parallel Graph search failed: {str(e)}", exc_info=True)
                return [], []

        # Execute 3 retrieval tasks in parallel threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_sem = executor.submit(task_semantic)
            future_bm25 = executor.submit(task_bm25)
            future_graph = executor.submit(task_graph)

            semantic_chunks = future_sem.result()
            bm25_chunks = future_bm25.result()
            graph_chunks, graph_relationships = future_graph.result()

        logger.info(f"Parallel retrieval results -> Semantic: {len(semantic_chunks)}, BM25: {len(bm25_chunks)}, Graph: {len(graph_chunks)}")

        # Merge & Rank candidates using Reciprocal Rank Fusion (RRF)
        fused_candidates = cls._apply_rrf_fusion(semantic_chunks, bm25_chunks, graph_chunks)
        logger.info(f"Total unique RRF-fused candidate chunks: {len(fused_candidates)}")
        
        # Cohere Reranking
        reranked_chunks = RerankService.rerank(query, fused_candidates)
        logger.info(f"Final reranked search returned {len(reranked_chunks)} context chunks.")
        
        return reranked_chunks, graph_relationships

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
