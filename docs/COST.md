# TruthLens Cost & Deployment Analysis

**TruthLens is designed with a strict Zero-Cost Deployment Philosophy.**
The primary goal is to allow students, researchers, and developers to run a full fact-checking pipeline on their local hardware without needing to pay for APIs, cloud services, or external subscriptions.

## Zero-Cost Core Components

The following components are free, open-source, and run entirely locally (or within your own infrastructure):

| Component | Technology | Cost / API Requirement |
| :--- | :--- | :--- |
| **Frontend** | React, Vite, Tailwind CSS | $0 (Open Source) |
| **Backend** | Python, FastAPI | $0 (Open Source) |
| **Database** | PostgreSQL + pgvector | $0 (Open Source) |
| **Background Jobs** | Celery + Redis | $0 (Open Source) |
| **LLM Inference** | Ollama (Llama 3, Qwen) | $0 (Local execution) |
| **Embeddings** | Ollama (e.g. `nomic-embed-text`) | $0 (Local execution) |
| **Web Search** | SearXNG | $0 (Local execution) |
| **OCR** | Tesseract OCR | $0 (Local execution) |
| **Web Scraping** | httpx, BeautifulSoup, trafilatura | $0 (Open Source libraries) |

### No Hidden Paid Dependencies
There are **no mandatory paid services** required to run the application. The system does not depend on OpenAI, AWS S3, Google Cloud, or Tavily for its default operation.

## Hardware Fallback & Recommendations

Because local LLM inference depends heavily on your computer's hardware, TruthLens supports configuration via environment variables to select the appropriate models for your system.

### Recommended Models by Hardware Tier

1. **Lower-RAM Machines (8GB - 16GB, CPU only or integrated graphics)**
   - LLM: `qwen2:0.5b` or `phi3:mini` (Very small, quantized models)
   - Embeddings: `nomic-embed-text`
   - *Note: Inference will be slower on CPU, but the application will function.*

2. **Medium Systems (16GB - 32GB, Dedicated GPU like RTX 3060/4060)**
   - LLM: `llama3:8b` or `gemma:7b` (Good balance of speed and capability)
   - Embeddings: `nomic-embed-text`

3. **High-Performance Systems (32GB+ RAM, High-VRAM GPUs like RTX 3090/4090/Mac M-Series Unified Memory)**
   - LLM: `llama3:70b` (quantized) or `command-r`
   - Embeddings: `nomic-embed-text`

*Configure these in your `.env` file:*
```env
OLLAMA_MODEL=llama3:8b
EMBEDDING_MODEL=nomic-embed-text
```

## Optional Paid Alternatives (For Production Scaling)

While the core project is zero-cost, the system architecture uses a **Provider Abstraction** pattern. This means that if you later decide to deploy this to production at scale, you can easily plug in paid services without rewriting the core business logic.

- **AIProvider**: Can be extended to support `OpenAIProvider`, `AnthropicProvider`, or `GeminiProvider`.
- **SearchProvider**: Can be extended to support `TavilyProvider`, `SerperProvider`, or `BingSearchProvider`.
- **StorageProvider**: Can be extended to support `S3StorageProvider`.

**These are strictly optional and not required to run the core TruthLens application.**
