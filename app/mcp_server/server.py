
from mcp.server.fastmcp import FastMCP
from app.mcp_server.storage import storage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("telegram-brain-mcp")

@mcp.tool()
def search_knowledge_base(query: str) -> str:
    """
    Search the knowledge base for relevant information using semantic search.
    Args:
        query: The user's question or search query.
    Returns:
        A formatted string containing relevant document chunks from the database.
    """
    logger.info(f"Received search query: {query}")
    results = storage.search(query)
    
    if not results:
        return "No relevant information found in the knowledge base."
    
    formatted_results = "\n\n---\n\n".join(results)
    return formatted_results

if __name__ == "__main__":
    logger.info("Starting MCP Server...")
    mcp.run()
