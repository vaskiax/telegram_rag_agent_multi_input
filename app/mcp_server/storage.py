
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class KnowledgeBaseStorage:
    def __init__(self):
        # Initialize Qdrant Client based on config (Cloud vs Local)
        if settings.QDRANT_URL:
            logger.info(f"Connecting to Qdrant Cloud at {settings.QDRANT_URL}")
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY
            )
        else:
            host = settings.QDRANT_HOST or "localhost"
            logger.info(f"Connecting to Qdrant Local at {host}:{settings.QDRANT_PORT}")
            self.client = QdrantClient(
                host=host,
                port=settings.QDRANT_PORT
            )
            
        # OpenAI API (For Embeddings)
        import os
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
             logger.warning("OPENAI_API_KEY not found. Embeddings using DeepSeek might fail if model not compatible.")
        
        # Use Standard OpenAI Client for Embeddings (DeepSeek for Chat is in Nodes)
        self.openai_client = OpenAI(
            api_key=openai_key
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.embedding_model = "text-embedding-3-small"
        self._ensure_collection()

    def _ensure_collection(self):
        """Ensures the Qdrant collection exists with the correct config."""
        try:
            if not self.client.collection_exists(self.collection_name):
                logger.info(f"Creating collection {self.collection_name}...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,  # Dimension for text-embedding-3-small
                        distance=models.Distance.COSINE
                    )
                )
                logger.info("Collection created.")
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            # In production, we might want to verify connectivity here.

    def _get_embedding(self, text: str) -> List[float]:
        """Generates embedding for the given text using OpenAI."""
        text = text.replace("\n", " ")
        return self.openai_client.embeddings.create(
            input=[text], 
            model=self.embedding_model
        ).data[0].embedding

    def search(self, query: str, limit: int = 5) -> List[str]:
        """
        Embeds the query and searches the knowledge base.
        Returns a list of document contents (payload 'content').
        """
        try:
            vector = self._get_embedding(query)
            
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=limit
            ).points
            
            documents = []
            for hit in results:
                if hit.payload and "content" in hit.payload:
                    documents.append(hit.payload["content"])
            
            return documents
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return []

    
    def _get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of texts using OpenAI."""
        # Clean texts
        cleaned_texts = [text.replace("\n", " ") for text in texts]
        
        try:
            response = self.openai_client.embeddings.create(
                input=cleaned_texts, 
                model=self.embedding_model
            )
            # Response.data is a list of Embedding objects, ordered by input index
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise e

    
    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]] = None, task_id: Optional[str] = None):
        """
        Adds text documents to the knowledge base with Chunking and Batch Processing.
        Tracks progress if task_id is provided.
        """
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        import uuid
        import time
        # Import registry 
        from app.core.global_state import task_registry
        
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        # LOG
        if task_id:
             task_registry[task_id] = "Splitting text into chunks..."
            
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " ", ""]
        )
            
        all_chunks = []
        all_metadatas = []
        
        # 1. Split all documents first
        for doc, meta in zip(documents, metadatas):
            chunks = text_splitter.split_text(doc)
            for chunk in chunks:
                all_chunks.append(chunk)
                # Store metadata + helpful preview
                payload = meta.copy()
                payload["content"] = chunk
                payload["full_source_preview"] = doc[:200] + "..." 
                all_metadatas.append(payload)
                
        # 2. Process in batches (OpenAI limit is usually 2048 dims or batch size limits, safe bet is ~100-500)
        BATCH_SIZE = 100
        total_chunks = len(all_chunks)
        
        if task_id:
            task_registry[task_id] = f"Generating embeddings for {total_chunks} chunks..."
            
        logger.info(f"Processing {total_chunks} total chunks in batches of {BATCH_SIZE}...")
        
        points_to_upsert = []
        
        for i in range(0, total_chunks, BATCH_SIZE):
            # UPDATE STATUS
            if task_id:
                 current_batch = i // BATCH_SIZE + 1
                 total_batches = (total_chunks // BATCH_SIZE) + 1
                 task_registry[task_id] = f"Embedding Batch {current_batch}/{total_batches} ({i}/{total_chunks} chunks)..."
            
            batch_texts = all_chunks[i : i + BATCH_SIZE]
            batch_metas = all_metadatas[i : i + BATCH_SIZE]
            
            try:
                # Generate embeddings for the whole batch
                embeddings = self._get_batch_embeddings(batch_texts)
                
                # Create points
                for text, embedding, meta in zip(batch_texts, embeddings, batch_metas):
                    point_id = str(uuid.uuid4())
                    points_to_upsert.append(models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=meta
                    ))
                
                logger.info(f"Processed batch {i // BATCH_SIZE + 1}/{(total_chunks // BATCH_SIZE) + 1}")
                
            except Exception as e:
                logger.error(f"Failed to process batch starting at index {i}: {e}")
                # Continue process? Or fail hard? For now fail hard to avoid partial state confusion
                # But typically we might want to retry.
                
        # 3. Upsert to Qdrant (Qdrant handles large batches well, but we can also chunk this upsert if needed)
        # We can upsert all at once if memory allows, or incrementally. 
        # For simplicity/safety, let's upsert what we have.
        if points_to_upsert:
            if task_id:
                task_registry[task_id] = f"Upserting {len(points_to_upsert)} vectors to DB..."
                
            # We can upsert in chunks of 500 to be safe with HTTP request size
            UPSERT_BATCH = 100
            for i in range(0, len(points_to_upsert), UPSERT_BATCH):
               batch_points = points_to_upsert[i : i + UPSERT_BATCH]
               self.client.upsert(
                   collection_name=self.collection_name,
                   points=batch_points
               )
            
            logger.info(f"Successfully added {len(points_to_upsert)} chunks to Qdrant.")

storage = KnowledgeBaseStorage()
