
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from app.core.config import settings
from app.interface.bot import create_bot_application

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ptb_application = create_bot_application()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the Telegram Bot alongside FastAPI.
    Registers webhook dynamically if TELEGRAM_WEBHOOK_URL is present.
    """
    logger.info("Starting up Telegram Brain Agent...")
    
    await ptb_application.initialize()
    await ptb_application.start()
    
    # Dynamic Webhook Registration for Cloud Run
    try:
        if settings.TELEGRAM_WEBHOOK_URL:
            webhook_url = f"{settings.TELEGRAM_WEBHOOK_URL}/webhook"
            logger.info(f"Setting webhook to: {webhook_url}")
            await ptb_application.bot.set_webhook(url=webhook_url)
        else:
            logger.warning("TELEGRAM_WEBHOOK_URL not set. Webhook will not be registered automatically.")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

    yield
    
    logger.info("Shutting down Telegram Brain Agent...")
    await ptb_application.stop()
    await ptb_application.shutdown()

app = FastAPI(title="Telegram Brain Agent", lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_application.bot)
        await ptb_application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"status": "error"}

@app.get("/")
def health_check():
    return {"status": "running", "service": "Telegram Brain Agent", "version": "1.0.0"}

@app.post("/admin/populate-kb")
async def populate_knowledge_base():
    """
    Admin endpoint to populate the knowledge base with sample documents.
    Call this once after deployment to initialize the database.
    """
    from app.mcp_server.storage import storage
    
    sample_documents = [
        "El Telegram Brain Agent es un asistente de IA multimodal que puede procesar texto, audio y imágenes. Utiliza GPT-4o para análisis visual y Whisper para transcripción de audio.",
        "Este agente implementa un sistema RAG (Retrieval Augmented Generation) estricto, lo que significa que solo responde basándose en información almacenada en su base de conocimientos vectorial.",
        "La arquitectura del sistema sigue el protocolo MCP (Model Context Protocol) con separación entre el servidor de datos y el agente de procesamiento.",
        "El agente está desplegado en Google Cloud Run y utiliza Qdrant Cloud como base de datos vectorial para almacenar embeddings.",
        "Para agregar nuevos documentos a la base de conocimientos, puedes usar el método add_documents del módulo storage o llamar al endpoint /admin/populate-kb.",
    ]
    
    try:
        storage.add_documents(
            documents=sample_documents,
            metadatas=[{"source": "system_docs", "type": "info"} for _ in sample_documents]
        )
        return {"status": "success", "message": f"Added {len(sample_documents)} documents to knowledge base"}
    except Exception as e:
        logger.error(f"Error populating KB: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/admin/test-search")
async def test_search(query: str = "¿Qué es el Telegram Brain Agent?"):
    """Test endpoint to verify knowledge base search is working."""
    from app.mcp_server.storage import storage
    try:
        results = storage.search(query, limit=3)
        return {"status": "success", "query": query, "results_count": len(results), "results": results}
    except Exception as e:
        logger.error(f"Error testing search: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.get("/admin/debug-agent")
async def debug_agent(question: str = "Cual es el tamaño de electrón ?"):
    """
    Debug endpoint to trace the agent flow step-by-step.
    """
    trace_log = []
    
    def log(step, msg, data=None):
        entry = {"step": step, "message": msg}
        if data:
            entry["data"] = str(data)
        trace_log.append(entry)
    
    try:
        from app.agent import nodes
        from app.agent.state import AgentState
        
        # Initial State
        state = AgentState(
            question=question,
            chat_history=[],
            reformulated_query="",
            context=[],
            is_relevant=False,
            final_answer="",
            media_type="text"
        )
        
        # 1. Reformulation
        log("Reformulation", "Starting reformulation...")
        res_ref = nodes.query_reformulation(state)
        state["reformulated_query"] = res_ref["reformulated_query"]
        log("Reformulation", "Done", state["reformulated_query"])
        
        # 2. Retrieval
        log("Retrieval", f"Retrieving for: {state['reformulated_query']}")
        res_ret = nodes.retrieve(state)
        state["context"] = res_ret["context"]
        log("Retrieval", f"Found {len(state['context'])} docs", state["context"])
        
        # 3. Grading
        log("Grading", "Grading documents...")
        res_grade = nodes.grade_documents(state)
        state["is_relevant"] = res_grade["is_relevant"]
        log("Grading", f"Is Relevant: {state['is_relevant']}")
        
        return {"status": "success", "trace": trace_log}
        
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": trace_log, "stack": traceback.format_exc()}


