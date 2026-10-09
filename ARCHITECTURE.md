# TruthLens Architecture

TruthLens is a production-quality, zero-cost, full-stack web application designed for AI-powered misinformation detection and fact-checking. 

## High-Level Architecture

```
                ┌─────────────────────┐
                │      React UI       │
                │ (Vite, TailwindCSS) │
                └──────────┬──────────┘
                           │ HTTP/REST
                           ▼
                ┌─────────────────────┐
                │    FastAPI API      │
                │  (Python, Pydantic) │
                └──────────┬──────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   Authentication     Analysis Engine    User Data
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
     Claim Engine    Evidence Engine    AI Engine
          │               │                │
          ▼               ▼                ▼
    Claim Extraction  SearXNG Search    Ollama (LLM)
          │               │                │
          └───────────────┼────────────────┘
                          ▼
                   Verdict Engine
                          │
                          ▼
                   Explanation Engine
                          │
                          ▼
                  PostgreSQL + pgvector
```

## Technology Stack (Zero-Cost Focus)

### Frontend
- **Framework**: React + TypeScript + Vite
- **Styling**: Tailwind CSS + shadcn/ui
- **State Management**: TanStack Query
- **Routing**: React Router

### Backend
- **Framework**: FastAPI (Python)
- **Validation**: Pydantic
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Background Jobs**: Celery + Redis

### AI & Data
- **Database**: PostgreSQL with `pgvector`
- **Search Provider**: SearXNG (Local, Open-Source Search Engine)
- **AI/LLM Provider**: Ollama (Running open-source models like Llama 3 or Qwen locally)
- **OCR Provider**: Tesseract OCR
- **Web Extraction**: `httpx`, `BeautifulSoup`, `trafilatura`

## System Modules

1. **API Layer**: Handles HTTP requests, authentication (JWT), and routes.
2. **Analysis Engine**: Orchestrates the fact-checking pipeline.
3. **AI Abstraction Layer**: Interfaces with Ollama for text generation, embeddings, and structured JSON outputs.
4. **Search Abstraction Layer**: Interfaces with SearXNG to fetch real-world web data.
5. **Verdict Engine**: Deterministically scores and classifies claims based on synthesized evidence.
6. **Background Workers**: Celery tasks for heavy processing (scraping, LLM inference, embedding generation).

## Fact-Checking Pipeline

1. **Input Normalization**: Clean user text/URL/image.
2. **Claim Extraction**: Local LLM identifies specific factual claims.
3. **Search Query Generation**: Local LLM generates optimal search queries.
4. **Web Search**: SearXNG fetches relevant URLs.
5. **Content Extraction**: System scrapes and cleans web page content.
6. **Embeddings & RAG**: Content is embedded and stored in pgvector for semantic retrieval.
7. **Evidence Synthesis**: Local LLM compares claims against retrieved evidence.
8. **Verdict Calculation**: Deterministic logic calculates a confidence score and verdict based on synthesized evidence.
9. **Explainability Generation**: Local LLM formats the results into an explainable response.
10. **Storage & UI Update**: Results stored in PostgreSQL and served to the React frontend.
