# Telegram Brain Agent: "Lord of Wisdom"

**Version**: 1.0.2  
**Architecture**: RAG + Agentic LangGraph + Multi-Modal  
**Deployment**: Google Cloud Run (Serverless)

---

## 📖 System Overview

This project is a high-performance **Cognitive Agent** designed to ingest complex Physics/Math content (mostly PDFs) and teach it to users with the persona of a charismatic Professor. It is not just a chatbot; it is a **State-Aware System** that knows what it is doing, remembers what you said, and visualizes what it means.

---

## ⚙️ Phase 1: Ingestion "The Senses"

The ingestion pipeline is designed for **Reliability** and **Scale**. It solves the "Silent Failure" problem common in serverless environments.

### 1.1 The Trigger (`bot.py`)
- User sends a PDF.
- The Bot **Acknowledges Immediately** ("⏳ Iniciando...") to prevent Telegram timeout.
- It spawns a **Background Async Task** (`process_document_background`) using `asyncio.create_task`. This decouples the processing from the webhook response.

### 1.2 The "X-Ray" Registry (`global_state.py`)
- Before starting work, the task registers itself in a **Thread-Safe Global Dictionary** (`task_registry`).
- Key: `chat_id`. Value: "Downloading...", "Extracting...", "Embedding Batch 5/50".
- **Benefit**: If the user asks *"What are you doing?"*, the Bot checks this registry. If a task exists, it **Short-Circuits** the brain (see Phase 2) and reports the exact status.

### 1.3 Optimized Ingestion (`storage.py`)
- **Chunking**: Splits text into semantic blocks (1000 chars).
- **Batch Processing**: Instead of calling OpenAI for every chunk (slow), it groups them into **Batches of 100**.
- **Vector Upsert**: Pushes vectors to **Qdrant** in parallel.
- **Resource Management**: The Cloud Run container is configured with **2GiB RAM** and **--no-cpu-throttling** to ensure this heavy process never crashes due to OOM (Out of Memory).

---

## 🧠 Phase 2: The Brain "The Agent"

The core logic is built on **LangGraph**, a directed cyclic graph that allows for reasoning loops.

### 2.1 Contextual Memory
- The Bot (`bot.py`) maintains a rolling window of the **Last 5 Messages** for each user.
- **Query Reformulation**: Before searching, the Agent looks at the history.
  - User: *"What about that chapter?"*
  - Agent sees history: *"Previous topic: Section 3.5"*
  - Reformulated Query: *"Summary of Section 3.5"*
  - **Result**: Perfect context maintenance.

### 2.2 The "Short-Circuit" Firewall (`graph.py`)
- **Problem**: RAG bots often hallucinate if you ask "Are you done?" while they are still working, because they search the DB and find nothing.
- **Solution**: The Router Node checks the `task_registry`.
- If `Busy`: **STOP**. Return `[SYSTEM_STATUS]` message. Do NOT query LLM.
- If `Free`: Proceed to Retrieval.

### 2.3 The "Charismatic Tutor" Persona (`nodes.py`)
- The Generator LLM is strictly prompted to:
  - **Internalize Knowledge**: "Treat the context as `YOUR OWN MEMORY`."
  - **Ban Robotic Language**: Never say "According to the context".
  - **Speak Directly**: "The definition of curl is..."
- This creates a seamless, human-like teaching experience.

---

## 🎨 Phase 3: The Presentation "Smart Rendering"

The bot intelligently decides how to display mathematical information to keep the chat clean.

### 3.1 The Heuristic Filter (`bot.py`)
- The LLM outputs LaTeX blocks (`$$ ... $$`).
- The Bot inspects every block:
  - **Simple?** (Short, no symbols like `\`, `=`, `^`): e.g., `x`, `K(r)`. -> **Render as Italic Text**.
  - **Complex?** (Integrals, Sums, Big Equations): -> **Render as Image**.

### 3.2 The Render Engine (`renderer.py`)
- Uses **Matplotlib (Agg Backend)** to draw the equation.
- **Optimization**:
  - DPI set to **200** (Retina quality but efficient).
  - Tight Bounding Box (`bbox_inches='tight'`) with minimal padding (0.05).
- **Result**: Crisp, perfectly sized physics equations that look native to the Telegram interface.

---

## 🚀 Deployment & Ops

We use a custom PowerShell script (`scripts/deploy.ps1`) to handle the complexity of Cloud Run.

### Critical Flags
- `--memory 2Gi`: Essential for PDF processing (PDF parsers are memory hungry).
- `--cpu 2`: Speeds up vector generation.
- `--no-cpu-throttling`: **MANDATORY**. Without this, Cloud Run freezes the CPU as soon as the HTTP request ends, killing the background ingestion. This flag keeps the CPU alive for the background thread.

### Environment Variables
- `TELEGRAM_BOT_TOKEN`: The interface.
- `OPENAI_API_KEY`: The Embeddings & Vision.
- `DEEPSEEK_API_KEY`: The Brain (High intelligence, low cost).
- `QDRANT_URL`: The Long-Term Memory.

---

## 🔧 Troubleshooting

| Symptom | Diagnosis | Fix |
| :--- | :--- | :--- |
| **"The document never finishes"** | Container OOM Crash | Increase Memory to 2GiB (Done). |
| **"Bot forgets context"** | Stateless `bot.py` | Verify `user_chat_history` is active. |
| **"Giant Image Spam"** | Renderer Misconfig | Check `renderer.py` is at 200 DPI. |
| **"Robotic Answers"** | Prompt Drift | Reset System Prompt in `nodes.py`. |

---

*Built with ❤️ by the Antigravity Team*
