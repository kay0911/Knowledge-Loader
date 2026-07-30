import sys
import os
import json

# Ensure app path is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.postgres import SessionLocal
from app.services.retrieval_service import RetrievalService
from app.models.document import DocumentChunk, Document
from sqlalchemy.orm import joinedload

def test_neo4j_retrieval(query: str):
    print("=" * 80)
    print(f"🔍 TESTING NEO4J GRAPH RETRIEVAL FOR QUERY: '{query}'")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        # Step 1: Detect entities in query
        detected_entities = RetrievalService._detect_entities_in_query(query)
        print(f"\n📌 1. DETECTED ENTITIES IN QUERY ({len(detected_entities)} found):")
        if detected_entities:
            for ent in detected_entities:
                print(f"   • {ent}")
        else:
            print("   (No matching entities found in Neo4j graph for this query)")

        if not detected_entities:
            print("\n❌ Skipping graph traversal because no entities were detected.")
            return

        # Step 2: Traverse Neo4j Graph for Relationships & Chunk IDs
        chunk_ids, relationships = RetrievalService._traverse_graph_for_entities(detected_entities)
        print(f"\n🕸️ 2. NEO4J GRAPH TRAVERSAL RESULTS ({len(relationships)} relationships, {len(chunk_ids)} unique chunk IDs):")
        for idx, rel in enumerate(relationships, 1):
            print(f"   {idx}. ({rel['source']}) --[{rel['relation']}]--> ({rel['target']})")
            if rel.get('description'):
                print(f"      Description: {rel['description']}")
            print(f"      Confidence: {rel.get('confidence')}")

        if not chunk_ids:
            print("\n❌ No linked chunk_ids found in graph evidence.")
            return

        # Step 3: Resolve Chunks from PostgreSQL
        graph_chunks = db.query(DocumentChunk).options(
            joinedload(DocumentChunk.document)
        ).join(
            Document, Document.id == DocumentChunk.document_id
        ).filter(
            DocumentChunk.id.in_(chunk_ids),
            DocumentChunk.is_active == True,
            Document.status == "READY",
            Document.is_enabled == True
        ).limit(10).all()

        print(f"\n📄 3. RESOLVED TOP {len(graph_chunks)} POSTGRESQL CHUNKS FROM GRAPH EVIDENCE:")
        print("-" * 80)
        for idx, chunk in enumerate(graph_chunks, 1):
            print(f"\n--- [CHUNK #{idx}] ---")
            print(f"ID: {chunk.id}")
            print(f"Document: {chunk.document.original_file_name if chunk.document else 'N/A'}")
            print(f"Heading Path: {chunk.heading_path or chunk.heading}")
            print(f"Page Range: {chunk.page_start} - {chunk.page_end}" if chunk.page_start else f"Page: {chunk.page_number}")
            print(f"Sheet: {chunk.sheet_name} (Rows: {chunk.row_start}-{chunk.row_end})" if chunk.sheet_name else "")
            snippet = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
            print(f"Content Snippet:\n{snippet}")
            print("-" * 80)

    finally:
        db.close()

if __name__ == "__main__":
    test_query = sys.argv[1] if len(sys.argv) > 1 else "VinFast Hải Phòng vi phạm kỷ luật mã nguồn"
    test_neo4j_retrieval(test_query)
