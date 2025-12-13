
import os
from typing import Dict, Any
from app.agent.state import AgentState
from app.mcp_server.storage import storage
from app.interface.utils import media_processor


# Import registry
from app.core.global_state import task_registry

def ingest_pdf(state: AgentState) -> Dict[str, Any]:
    print("---INGESTING PDF---")
    file_path = state.get("file_path")
    task_id = state.get("task_id")
    
    if not file_path or not os.path.exists(file_path):
        return {"final_answer": "Error: No se encontró el archivo PDF para procesar."}
    
    if task_id:
        task_registry[task_id] = f"Extracting text from PDF (could take a moment)..."
        
    text = media_processor.extract_text_from_pdf(file_path)
    if not text.strip():
        return {"final_answer": "Error: No se pudo extraer texto del PDF (o está vacío)."}
        
    storage.add_documents(
        documents=[text],
        metadatas=[{"source": os.path.basename(file_path), "type": "pdf"}],
        task_id=task_id
    )
    
    # Clean up temp file
    try:
        os.remove(file_path)
    except:
        pass
        
    return {"final_answer": f"✅ He guardado el documento '{os.path.basename(file_path)}' en tu base de conocimientos."}

async def ingest_url(state: AgentState) -> Dict[str, Any]:
    print("---INGESTING URL---")
    url = state.get("url")
    task_id = state.get("task_id")
    
    if not url:
        return {"final_answer": "Error: URL no proporcionada."}
        
    if task_id:
        task_registry[task_id] = f"Scraping content from {url}..."
        
    text = await media_processor.scrape_url(url)
    if not text.strip():
        return {"final_answer": f"Error: No se pudo extraer contenido de {url}."}
        
    storage.add_documents(
        documents=[text],
        metadatas=[{"source": url, "type": "url"}],
        task_id=task_id
    )
    
    return {"final_answer": f"✅ He procesado y guardado el contenido de: {url}"}

def ingest_image(state: AgentState) -> Dict[str, Any]:
    print("---INGESTING IMAGE---")
    file_path = state.get("file_path") # We expect a temp file path for consistency
    if not file_path or not os.path.exists(file_path):
        return {"final_answer": "Error: No se encontró la imagen para procesar."}
    
    try:
        with open(file_path, "rb") as img_file:
            image_bytes = img_file.read()
            
        description = media_processor.describe_image_from_bytes(image_bytes)
        
        if "Error" in description or "Hubo un error" in description:
             return {"final_answer": description} # Return the error message from utils
        
        storage.add_documents(
            documents=[description],
            metadatas=[{"source": "image_upload", "type": "image_description"}]
        )
        
        return {"final_answer": f"✅ Imagen analizada y guardada.\n\n📝 Descripción generada:\n{description}"}
        
    except Exception as e:
        return {"final_answer": f"Error procesando imagen: {str(e)}"}
    finally:
        # Clean up temp file
        try:
            os.remove(file_path)
        except:
            pass

def ingest_text_note(state: AgentState) -> Dict[str, Any]:
    """Handles explicit /save commands for text notes"""
    print("---INGESTING TEXT NOTE---")
    text = state.get("question") # strict raw text
    # Usually the command logic in bot.py removes the "/save " prefix
    
    storage.add_documents(
        documents=[text],
        metadatas=[{"source": "user_note", "type": "text"}]
    )
    return {"final_answer": "✅ Nota guardada en la base de conocimientos."}
