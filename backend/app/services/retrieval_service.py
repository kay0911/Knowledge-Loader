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
        Retrieves context chunks using a Hybrid Search pipeline:
        1. Semantic Search (pgvector)
        2. Keyword Search (BM25)
        3. Graph-augmented Search (Neo4j entity traversal)
        Deduplicates, reranks via Cohere, and returns top chunks and graph context.
        """
        logger.info(f"Starting hybrid retrieval for query: '{query}'")
        
        # 1. Semantic Search (pgvector)
        semantic_chunks = []
        try:
            query_embedding = EmbeddingService.get_embedding(query)
            # Fetch top 15 chunks based on pgvector cosine distance
            semantic_chunks = db.query(DocumentChunk).options(
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
            ).limit(15).all()
            logger.info(f"Semantic search retrieved {len(semantic_chunks)} chunks.")
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}", exc_info=True)

        # 2. Keyword Search (BM25)
        bm25_chunks = []
        try:
            bm25_chunks = BM25Service.search(query, top_k=15)
            logger.info(f"BM25 search retrieved {len(bm25_chunks)} chunks.")
        except Exception as e:
            logger.error(f"BM25 search failed: {str(e)}", exc_info=True)

        # 3. Graph-augmented Search (Neo4j)
        graph_chunks = []
        graph_relationships = []
        try:
            detected_entities = cls._detect_entities_in_query(query)
            if detected_entities:
                logger.info(f"Detected entities in query: {detected_entities}")
                chunk_ids, graph_relationships = cls._traverse_graph_for_entities(detected_entities)
                if chunk_ids:
                    # Retrieve the actual chunk contents from PostgreSQL
                    graph_chunks = db.query(DocumentChunk).options(
                        joinedload(DocumentChunk.document)
                    ).join(
                        Document, Document.id == DocumentChunk.document_id
                    ).filter(
                        DocumentChunk.id.in_(chunk_ids),
                        DocumentChunk.is_active == True,
                        Document.status == "READY",
                        Document.is_enabled == True
                    ).all()
                    logger.info(f"Graph retrieval resolved {len(graph_chunks)} chunks from Neo4j evidence.")
        except Exception as e:
            logger.error(f"Graph-augmented search failed: {str(e)}", exc_info=True)

        # 4. Merge and Deduplicate candidates
        all_candidates = []
        seen_ids = set()
        
        # Priority order for initial inclusion: Graph, Semantic, Keyword
        for chunk in (graph_chunks + semantic_chunks + bm25_chunks):
            if chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                all_candidates.append(chunk)
                
        logger.info(f"Total unique candidate chunks gathered: {len(all_candidates)}")
        
        # 5. Cohere Reranking
        reranked_chunks = RerankService.rerank(query, all_candidates)
        logger.info(f"Final reranked search returned {len(reranked_chunks)} context chunks.")
        
        return reranked_chunks, graph_relationships

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
        LIMIT 15
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
