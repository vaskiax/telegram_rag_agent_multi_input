import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from qdrant_client import QdrantClient
from app.core.config import settings

print("Checking QdrantClient from library...")
try:
    if settings.QDRANT_URL:
        client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    else:
        client = QdrantClient(host="localhost")
        
    print(f"Client: {client}")
    print(f"Has search: {hasattr(client, 'search')}")
    print(f"Has query_points: {hasattr(client, 'query_points')}")
    print(f"Has search_points: {hasattr(client, 'search_points')}")
    print(f"Has query_batch: {hasattr(client, 'query_batch')}")
    print(f"Has search_batch: {hasattr(client, 'search_batch')}")
except Exception as e:
    print(f"Error: {e}")
