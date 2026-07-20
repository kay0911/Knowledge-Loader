import sys
import os

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from app.db.neo4j import neo4j_client
from app.services.embedding_service import EmbeddingService
from app.services.graph_extraction_service import GraphExtractionService
from app.services.graph_service import GraphService
from app.services.bm25_service import BM25Service
from app.db.postgres import SessionLocal, engine
from app.models.document import DocumentChunk
from sqlalchemy import text

# Run migrations before testing DB operations
try:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding VECTOR(768);"))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops);
        """))
except Exception as e:
    print("Database migration failed:", str(e))

def test_neo4j():
    print("\n1. Testing Neo4j Connection...")
    try:
        neo4j_client.connect()
        with neo4j_client.get_session() as session:
            result = session.run("RETURN 'Neo4j connection works!' as msg")
            record = result.single()
            print("Neo4j Response:", record["msg"])
        neo4j_client.close()
    except Exception as e:
        print("Neo4j Connection Failed:", str(e))

def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY", "")
    print(f"\n2. Testing Gemini Integration (API Key: {'configured' if api_key and api_key != 'YOUR_GEMINI_API_KEY_HERE' else 'NOT configured'})")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        print("Skipping Gemini tests because GEMINI_API_KEY is not set.")
        return

    # Test Embedding
    try:
        print("Generating embedding for text 'VinFast electric vehicle VF5'...")
        vec = EmbeddingService.get_embedding("VinFast electric vehicle VF5")
        print(f"Generated embedding vector successfully. Dimension: {len(vec)}")
    except Exception as e:
        print("Gemini Embedding Failed:", str(e))

    # Test Graph Extraction
    try:
        print("Extracting graph for test sentence 'VinFast has a car model called VF5 which belongs to the domain of Aftersales.'...")
        text_content = "VinFast has a car model called VF5 which belongs to the domain of Aftersales."
        entities, relationships = GraphExtractionService.extract_graph(text_content)
        print("Extracted Entities:")
        for e in entities:
            print(f" - {e['name']} ({e['type']}): {e['description']}")
        print("Extracted Relationships:")
        for r in relationships:
            print(f" - {r['source']} -[{r['relation']}]-> {r['target']} ({r['description']})")
    except Exception as e:
        print("Gemini Graph Extraction Failed:", str(e))

def test_bm25():
    print("\n3. Testing BM25 Keyword Search...")
    try:
        BM25Service.rebuild_index()
        # Search for something
        res = BM25Service.search("VF5")
        print(f"BM25 Search found {len(res)} chunks.")
    except Exception as e:
        print("BM25 test failed:", str(e))

def main():
    print("=== Step 2 Indexing & Graph Verification ===")
    test_neo4j()
    test_bm25()
    test_gemini()
    print("\n=== Verification End ===")

if __name__ == "__main__":
    main()
