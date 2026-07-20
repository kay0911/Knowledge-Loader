import sys
import os

# Add backend directory to sys.path so we can import app modules
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_path)

from app.services.parser_service import ParserService
from app.services.chunking_service import ChunkingService

def main():
    print("--- Starting Pipeline Verification Test ---")
    
    # 1. Test DOCX Parsing and Chunking
    docx_file = "scratch/sample_policy.docx"
    if not os.path.exists(docx_file):
        print(f"Error: {docx_file} not found. Run generate_mock_docs.py first.")
        return
        
    print(f"\n1. Testing Parser on {docx_file}:")
    docx_items = ParserService.parse(docx_file, "docx")
    print(f"Parsed {len(docx_items)} paragraphs/headings.")
    
    print("\nFirst 3 parsed elements:")
    for idx, item in enumerate(docx_items[:3]):
        print(f"[{idx}] Heading: {item['heading']} | Content preview: {item['content'][:100]}")
        
    print("\nTesting Chunking on DOCX items (chunk_size=200, overlap=40):")
    docx_chunks = ChunkingService.chunk_document(docx_items, chunk_size=200, overlap=40)
    print(f"Generated {len(docx_chunks)} chunks.")
    for c in docx_chunks[:3]:
        print(f" - Chunk #{c['chunk_order']} (Heading: {c['heading']}): {c['content'][:100]}...")

    # 2. Test XLSX Parsing and Chunking
    xlsx_file = "scratch/sample_models.xlsx"
    if not os.path.exists(xlsx_file):
        print(f"Error: {xlsx_file} not found.")
        return
        
    print(f"\n2. Testing Parser on {xlsx_file}:")
    xlsx_items = ParserService.parse(xlsx_file, "xlsx")
    print(f"Parsed {len(xlsx_items)} sheet rows.")
    
    print("\nFirst row contents:")
    if xlsx_items:
        print(xlsx_items[0]["content"])
        
    print("\nTesting Chunking on XLSX items:")
    xlsx_chunks = ChunkingService.chunk_document(xlsx_items)
    print(f"Generated {len(xlsx_chunks)} chunks from Excel rows.")
    if xlsx_chunks:
        print("Excel Chunk metadata example:")
        print(f"Order: {xlsx_chunks[0]['chunk_order']}, Sheet: {xlsx_chunks[0]['sheet_name']}, Rows: {xlsx_chunks[0]['row_start']}-{xlsx_chunks[0]['row_end']}")

    print("\n--- Pipeline Verification Test Complete ---")

if __name__ == "__main__":
    main()
