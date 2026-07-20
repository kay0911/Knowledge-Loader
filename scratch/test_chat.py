import sys
import os

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_path)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_path, ".env"))

from app.db.postgres import SessionLocal
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievalService
from app.models.chat import ChatLog

def test_hybrid_retrieval(db):
    print("\n--- 1. Testing Hybrid Retrieval ---")
    query = "chính sách bảo hành pin xe VF5"
    print(f"Retrieving context for query: '{query}'")
    chunks, graph_rels = RetrievalService.retrieve_hybrid(db, query)
    
    print(f"Retrieved {len(chunks)} relevant chunks after deduplication and Reranking.")
    for i, c in enumerate(chunks[:3]):
        print(f" Chunk {i+1}:")
        print(f"  - Document: {c.document.original_file_name}")
        print(f"  - Position: Page {c.page_number} / Heading: {c.heading} / Sheet: {c.sheet_name}")
        print(f"  - Content snippet: {c.content[:100]}...")
        
    print(f"Retrieved {len(graph_rels)} Neo4j relations.")
    for rel in graph_rels[:3]:
        print(f"  - Relation: {rel['source']} -[{rel['relation']}]-> {rel['target']} ({rel['description']})")
        
    return query

def test_chat_generation(db, query):
    print("\n--- 2. Testing Q&A Answer and Citation Generation ---")
    chat_log, citations = ChatService.ask(db, query)
    
    print("\n--- AI Answer ---")
    print(chat_log.answer)
    
    print("\n--- Citations Generated ---")
    print(f"Total citations linked: {len(citations)}")
    for cit in citations:
        print(f" [{cit['source_id']}] File: {cit['file_name']} | Page: {cit['page_number']} | Heading: {cit['heading']}")
        print(f"   Snippet: {cit['snippet'][:150]}...")
        
    print(f"\nResponse latency: {chat_log.latency_ms} ms")
    return chat_log.id

def test_database_log(db, log_id):
    print("\n--- 3. Verifying Database ChatLog Record ---")
    log = db.query(ChatLog).filter(ChatLog.id == log_id).first()
    if log:
        print("Chat log found in PostgreSQL database!")
        print(f" ID: {log.id}")
        print(f" Question: {log.question}")
        print(f" Answer length: {len(log.answer)} characters")
        print(f" Latency logged: {log.latency_ms} ms")
        print(f" Created At: {log.created_at}")
    else:
        print("Error: Chat log NOT found in database!")

def main():
    print("=== Step 3 RAG Retrieval & Chatbot Verification ===")
    
    # Initialize DB Session
    db = SessionLocal()
    try:
        query = test_hybrid_retrieval(db)
        log_id = test_chat_generation(db, query)
        test_database_log(db, log_id)
    except Exception as e:
        print("Verification script failed:", str(e))
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        
    print("\n=== Verification End ===")

if __name__ == "__main__":
    main()
