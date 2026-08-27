# 🚀 Knowledge-Loader: Enterprise Two-Stage Hybrid GraphRAG System

**Knowledge-Loader** là hệ thống Quản trị & Tra cứu Tri thức Doanh nghiệp thế hệ mới (Next-Generation Enterprise RAG System), kết hợp giữa **Search 2 Giai đoạn (Two-Stage Hybrid Retrieval)**, **Đồ thị Tri thức (Neo4j Graph Database)**, **Vector Search (PostgreSQL pgvector)**, **Bộ Lọc Từ vựng (BM25)** và **Re-ranking (Cohere Rerank API)**.

---

## 🌟 Tính năng & Kiến trúc Nổi bật (Key Technical Highlights)

### 1. Bộ Bóc tách & Cắt mảnh Tài liệu Chuyên sâu (Custom Parsers & Chunking)
Hệ thống tích hợp sẵn các bộ Parser tùy chỉnh tối ưu cho doanh nghiệp:
- **DOCX:** Tự động chuyển đổi Bảng Word phức tạp thành mảng **Markdown Table**, bóc tách Hình ảnh nhúng và cắt mảnh bảo toàn ngữ cảnh.
- **XLSX:** Tự động nhận diện Bảng biểu Timeline/Action Plan, cắt mảnh theo từng nhóm cột và ô chủ đạo, giới hạn ngân sách ký tự để ngăn chặn vỡ token.
- **PDF, PPTX, Markdown, CSV:** Bóc tách tiêu chuẩn, lưu trữ thông tin số trang, sheet name, vị trí dòng/cột.

### 2. Đường ống Tra cứu 2 Giai đoạn (Two-Stage Hybrid Retrieval Pipeline)
- **Stage 1 (Document Routing):** Định tuyến danh sách tài liệu mục tiêu dựa trên **Fusion 50/50** giữa:
  - **Vector Similarity (50%):** So khớp Cosine Similarity của `query_vector` với `summary_embedding` của từng tài liệu.
  - **Rule-based Matching (50%):** Overlap câu hỏi giả định (HyDE Questions), Domain, Sub-domain, Keywords và Entities.
- **Stage 2 (Scoped In-Document Chunk Search):** Tìm kiếm chi tiết mảnh tri thức (Chunk) trong phạm vi các tài liệu đã chọn ở Stage 1:
  - Tối ưu song song **Hybrid Vector (pgvector)** + **BM25 Lexical Keyword Search**.
  - Dung hợp thứ hạng bằng thuật toán **Reciprocal Rank Fusion (RRF)**.
  - Tái xếp hạng chính xác bằng **Cohere Rerank API v2** trước khi gửi tới LLM.

### 3. Bộ Bộ nhớ đệm Vectơ Lai (Hybrid Semantic Vector Cache)
- **Fast-Path Cache Hit:** Nhận diện câu hỏi có cùng ý nghĩa bằng **Cosine Similarity $\ge 0.95$**.
- **Bộ Quy tắc Bảo vệ (Strict Guard Rules):**
  - **Strict Number & Year Match:** Yêu cầu trùng khớp 100% con số và năm (`2024` $\neq$ `2026`, `Chương 1` $\neq$ `Chương 2`) để tránh bẫy Cache HIT nhầm.
  - **Strict Entity Code Match:** Yêu cầu trùng khớp 100% mã thực thể/dự án (`P4` $\neq$ `P5`, `VF8` $\neq$ `VF9`).
- **Hủy Cache Theo Đúng Tài liệu (Document-Scoped Cache Invalidation):** Tự động phát hiện và vô hiệu hóa các bản ghi Cache phụ thuộc vào tài liệu vừa được tải lên/cập nhật phiên bản mới, trong khi vẫn **bảo tồn Cache của các tài liệu khác**.
- **Tối ưu 1 Lần Embedding Duy nhất:** Sinh `query_vector` **đúng 1 lần per request** và tái sử dụng cho Cache Check, Stage 1 Routing, Stage 2 Chunk Search và Chat Log.

---

## 🏗️ Công nghệ Sử dụng (Tech Stack)

- **Backend:** Python 3.11, FastAPI, SQLAlchemy ORM, Uvicorn.
- **Frontend:** React.js, Vite, Vanilla CSS / Modern UI Design System.
- **Databases:**
  - **PostgreSQL 16** (với extension `pgvector` cho Vector Storage & Hybrid Search).
  - **Neo4j Graph Database** (Cho GraphRAG & Entity Relationship Traversal).
- **AI Models & External APIs:**
  - **Google Gemini API** (`gemini-2.5-flash` cho LLM & `text-embedding-004` cho Embedding).
  - **Cohere Rerank API** (`rerank-v3.5` / `rerank-english-v3.0`).
- **Containerization:** Docker & Docker Compose.

---

## 🛠️ Cấu trúc Thư mục Dự án (Project Structure)

```text
Knowledge-Loader/
├── backend/
│   ├── app/
│   │   ├── api/             # REST API Routes (Chat, Documents, Graph)
│   │   ├── core/            # Config, Logger, Security
│   │   ├── db/              # Postgres & Neo4j Database Connectors
│   │   ├── models/          # SQLAlchemy Models (Document, ChatLog, Chunk)
│   │   ├── services/        # Business Logic Services (Cache, Retrieval, Parser, LLM)
│   │   └── workers/         # Background Document Processing Workers
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/                 # React UI Pages & Components (Chat, Docs, Graph)
│   ├── Dockerfile
│   └── package.json
├── docs/                    # Tài liệu Thiết kế Kỹ thuật (Architecture Specs)
├── docker-compose.yml       # Docker Orchestration Configuration
└── README.md
```

---

## 🚀 Hướng dẫn Khởi chạy Hệ thống (How to Run)

### 1. Yêu cầu Tiền đề (Prerequisites)
- Cài đặt sẵn **Docker** và **Docker Compose**.
- Chuẩn bị Khóa API (API Keys):
  - **Google Gemini API Key**
  - **Cohere API Key**

### 2. Cấu hình Biến Môi trường (Environment Setup)
Tạo file `.env` tại thư mục gốc dự án `Knowledge-Loader/.env` (hoặc cấu hình trực tiếp trong `docker-compose.yml`):

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=knowledge_loader
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

GEMINI_API_KEY=your_gemini_api_key_here
COHERE_API_KEY=your_cohere_api_key_here
```

### 3. Khởi chạy toàn bộ Hệ thống bằng Docker Compose

Mở Terminal tại thư mục gốc dự án và chạy câu lệnh:

```bash
docker compose up -d --build
```

Lệnh này sẽ tự động:
1. Đóng gói và build Docker Image cho **Backend (FastAPI)** và **Frontend (React)**.
2. Khởi chạy container **PostgreSQL + pgvector** (Port `5432`).
3. Khởi chạy container **Neo4j Graph Database** (Port `7474`, `7687`).
4. Khởi chạy container **Backend API** (Port `8000`).
5. Khởi chạy container **Frontend Web UI** (Port `80` / `3000`).

---

## 🌐 Các Đường dẫn Truy cập (Access Endpoints)

| Dịch vụ | Đường dẫn Truy cập (URL) | Mô tả |
| :--- | :--- | :--- |
| **Frontend Web App** | `http://localhost:3000` (hoặc `http://localhost`) | Giao diện Chatbot, Tra cứu & Quản lý Tài liệu |
| **Backend Swagger API Docs** | `http://localhost:8000/docs` | Giao diện thử nghiệm API OpenAPI / Swagger |
| **Neo4j Browser Console** | `http://localhost:7474` | Giao diện Quản lý Đồ thị Neo4j |
| **PostgreSQL Database** | `localhost:5432` | Cơ sở Dữ liệu Tri thức & Vector Chunks |

---

## 📜 Giấy phép (License)
Dự án phát triển nội bộ bởi Team Data & AI Engineering. Bảo lưu mọi quyền.