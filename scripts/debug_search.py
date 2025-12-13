
import os
import logging
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.mcp_server.storage import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_search():
    print("--- Testing Search Configuration ---")
    print(f"Qdrant URL: {settings.QDRANT_URL}")
    print(f"Collection: {settings.QDRANT_COLLECTION_NAME}")
    print(f"OpenAI Key Present: {bool(os.environ.get('OPENAI_API_KEY'))}")
    
    try:
        query = "electron"
        print(f"Attempting query_points for: {query}")
        
        # storage.search uses client.search internally, so we expect it to fail currently.
        # We will manually test client.query_points here to verify the fix.
        vector = storage._get_embedding(query)
        print("Embedding generated.")
        
        results = storage.client.query_points(
            collection_name=storage.collection_name,
            query=vector,
            limit=5
        ).points
        
        print(f"Found {len(results)} results using query_points.")

        print(f"Found {len(results)} results.")
        for i, res in enumerate(results):
            print(f"[{i}] {res[:100]}...")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_search()
