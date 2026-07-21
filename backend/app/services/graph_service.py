import uuid
from typing import List, Dict, Any
from app.db.neo4j import neo4j_client
from app.core.logging import logger

class GraphService:
    @classmethod
    def save_extracted_graph(
        cls,
        document_id: str,
        version_id: str,
        chunk_id: str,
        document_title: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ):
        """
        Write entities and relationships for a specific chunk to Neo4j.
        """
        logger.info(f"Writing extracted graph for chunk {chunk_id} to Neo4j...")
        with neo4j_client.get_session() as session:
            try:
                session.execute_write(
                    cls._save_graph_tx,
                    document_id,
                    version_id,
                    chunk_id,
                    document_title,
                    entities,
                    relationships
                )
                logger.info(f"Successfully saved graph for chunk {chunk_id} in Neo4j.")
            except Exception as e:
                logger.error(f"Error saving graph for chunk {chunk_id} to Neo4j: {str(e)}")
                raise e

    @staticmethod
    def _save_graph_tx(
        tx,
        document_id: str,
        version_id: str,
        chunk_id: str,
        document_title: str,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ):
        # 1. Merge Document Node
        tx.run(
            """
            MERGE (d:Document {document_id: $document_id})
            SET d.title = $title, d.active_version_id = $version_id
            """,
            document_id=document_id,
            title=document_title,
            version_id=version_id
        )

        # 2. Merge Entity Nodes
        for ent in entities:
            name = ent["name"].strip()
            ent_type = ent["type"].strip()
            desc = ent.get("description", "").strip()
            norm_name = name.lower()
            ent_id = str(uuid.uuid4())
            
            tx.run(
                """
                MERGE (e:Entity {normalized_name: $norm_name})
                ON CREATE SET e.entity_id = $ent_id, e.name = $name, e.type = $type, e.description = $desc
                ON MATCH SET e.type = coalesce(e.type, $type), e.description = coalesce(e.description, $desc)
                """,
                norm_name=norm_name,
                ent_id=ent_id,
                name=name,
                type=ent_type,
                desc=desc
            )

        # 3. Connect Document to Entities (MENTIONS relation with evidence chunk_id)
        for ent in entities:
            norm_name = ent["name"].strip().lower()
            tx.run(
                """
                MATCH (d:Document {document_id: $document_id})
                MATCH (e:Entity {normalized_name: $norm_name})
                MERGE (d)-[r:MENTIONS {chunk_id: $chunk_id}]->(e)
                SET r.document_version_id = $version_id
                """,
                document_id=document_id,
                norm_name=norm_name,
                chunk_id=chunk_id,
                version_id=version_id
            )

        # 4. Create Entity-Entity Relationships
        for rel in relationships:
            src_name = rel["source"].strip()
            src_norm = src_name.lower()
            tgt_name = rel["target"].strip()
            tgt_norm = tgt_name.lower()
            
            relation_name = rel["relation"].strip().upper().replace(" ", "_")
            desc = rel.get("description", "").strip()
            conf = float(rel.get("confidence", 1.0))
            
            # Ensure source and target entities exist (could happen if LLM mentions relationships of non-listed entities)
            tx.run(
                """
                MERGE (s:Entity {normalized_name: $src_norm})
                ON CREATE SET s.entity_id = $ent_id, s.name = $src_name, s.type = $src_type
                """,
                src_norm=src_norm,
                ent_id=str(uuid.uuid4()),
                src_name=src_name,
                src_type=rel.get("source_type", "Entity")
            )
            tx.run(
                """
                MERGE (t:Entity {normalized_name: $tgt_norm})
                ON CREATE SET t.entity_id = $ent_id, t.name = $tgt_name, t.type = $tgt_type
                """,
                tgt_norm=tgt_norm,
                ent_id=str(uuid.uuid4()),
                tgt_name=tgt_name,
                tgt_type=rel.get("target_type", "Entity")
            )
            
            tx.run(
                """
                MATCH (s:Entity {normalized_name: $src_norm})
                MATCH (t:Entity {normalized_name: $tgt_norm})
                MERGE (s)-[r:RELATED_TO {chunk_id: $chunk_id}]->(t)
                SET r.relation_name = $relation_name,
                    r.document_id = $document_id,
                    r.document_version_id = $version_id,
                    r.confidence = $confidence,
                    r.description = $description
                """,
                src_norm=src_norm,
                tgt_norm=tgt_norm,
                chunk_id=chunk_id,
                document_id=document_id,
                version_id=version_id,
                relation_name=relation_name,
                confidence=conf,
                description=desc
            )

    @classmethod
    def remove_document_evidence(cls, document_id: str):
        """
        Delete all relationships (mentions, RELATED_TO) associated with a document,
        then clean up any entities left without any connections.
        """
        logger.info(f"Removing all Neo4j graph evidence for document {document_id}...")
        with neo4j_client.get_session() as session:
            try:
                session.execute_write(cls._remove_document_evidence_tx, document_id)
                logger.info(f"Successfully cleaned up graph evidence for document {document_id}.")
            except Exception as e:
                logger.error(f"Error removing Neo4j graph evidence for document {document_id}: {str(e)}")
                raise e

    @staticmethod
    def _remove_document_evidence_tx(tx, document_id: str):
        # 1. Delete RELATED_TO relationships associated with document_id
        tx.run(
            """
            MATCH ()-[r:RELATED_TO {document_id: $document_id}]->()
            DELETE r
            """,
            document_id=document_id
        )

        # 2. Delete MENTIONS relationships connected to Document node
        tx.run(
            """
            MATCH (d:Document {document_id: $document_id})-[r:MENTIONS]->()
            DELETE r
            """,
            document_id=document_id
        )

        # 3. Delete Document node
        tx.run(
            """
            MATCH (d:Document {document_id: $document_id})
            DELETE d
            """,
            document_id=document_id
        )

        # 4. Clean up isolated Entity nodes
        tx.run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)-[:RELATED_TO]-() AND NOT ()-[:MENTIONS]->(e)
            DELETE e
            """
        )

    @classmethod
    def remove_old_versions_evidence(cls, document_id: str, active_version_id: str):
        """
        Delete all relationships (mentions, RELATED_TO) associated with old versions of a document,
        keeping only the active version's relationships. Then clean up isolated entities.
        """
        logger.info(f"Removing old Neo4j graph evidence for document {document_id} keeping active version {active_version_id}...")
        with neo4j_client.get_session() as session:
            try:
                session.execute_write(cls._remove_old_versions_evidence_tx, document_id, active_version_id)
                logger.info(f"Successfully cleaned up old version evidence for document {document_id}.")
            except Exception as e:
                logger.error(f"Error removing old version evidence for document {document_id}: {str(e)}")
                raise e

    @staticmethod
    def _remove_old_versions_evidence_tx(tx, document_id: str, active_version_id: str):
        # 1. Delete RELATED_TO relationships where document_id matches and document_version_id is NOT active_version_id
        tx.run(
            """
            MATCH ()-[r:RELATED_TO {document_id: $document_id}]->()
            WHERE r.document_version_id <> $active_version_id
            DELETE r
            """,
            document_id=document_id,
            active_version_id=active_version_id
        )

        # 2. Delete MENTIONS relationships connected to Document node where document_version_id is NOT active_version_id
        tx.run(
            """
            MATCH (d:Document {document_id: $document_id})-[r:MENTIONS]->()
            WHERE r.document_version_id <> $active_version_id
            DELETE r
            """,
            document_id=document_id,
            active_version_id=active_version_id
        )

        # 3. Clean up isolated Entity nodes
        tx.run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)-[:RELATED_TO]-() AND NOT ()-[:MENTIONS]->(e)
            DELETE e
            """
        )

