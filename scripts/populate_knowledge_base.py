"""
Script to populate the Qdrant knowledge base with sample documents.
Run this locally or from Cloud Shell to add initial data.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mcp_server.storage import storage

# Sample documents about the Telegram Brain Agent itself
sample_documents = [
    "El Telegram Brain Agent es un asistente de IA multimodal que puede procesar texto, audio y imágenes. Utiliza GPT-4o para análisis visual y Whisper para transcripción de audio.",
    "Este agente implementa un sistema RAG (Retrieval Augmented Generation) estricto, lo que significa que solo responde basándose en información almacenada en su base de conocimientos vectorial.",
    "La arquitectura del sistema sigue el protocolo MCP (Model Context Protocol) con separación entre el servidor de datos y el agente de procesamiento.",
    "El agente está desplegado en Google Cloud Run y utiliza Qdrant Cloud como base de datos vectorial para almacenar embeddings.",
    "Para agregar nuevos documentos a la base de conocimientos, puedes usar el método add_documents del módulo storage.",
]

def main():
    print("🚀 Iniciando carga de documentos de ejemplo...")
    
    try:
        storage.add_documents(
            documents=sample_documents,
            metadatas=[{"source": "system_docs", "type": "info"} for _ in sample_documents]
        )
        print(f"✅ Se agregaron {len(sample_documents)} documentos exitosamente!")
        
        # Test search
        print("\n🔍 Probando búsqueda...")
        results = storage.search("¿Qué es el Telegram Brain Agent?", limit=2)
        print(f"Resultados encontrados: {len(results)}")
        if results:
            print(f"Primer resultado: {results[0][:100]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
