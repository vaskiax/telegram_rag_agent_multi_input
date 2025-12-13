from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes import query_reformulation, retrieve, grade_documents, generate, fallback_nodes, system_status_response
from app.agent.ingestion_nodes import ingest_pdf, ingest_url, ingest_image, ingest_text_note

def route_start(state: AgentState):
    """
    Router at the start of the graph.
    Decides whether to do RAG, Ingestion, or System Status response.
    """
    media_type = state.get("media_type")
    question = state.get("question", "")
    
    # 1. Priority: System Status Short-Circuit
    if "[SYSTEM_STATUS:" in question:
        return "system_status_response"
    
    # 2. Ingestion Flows
    if media_type == "pdf":
        return "ingest_pdf"
    elif media_type == "url":
        return "ingest_url"
    elif media_type == "image":
        return "ingest_image"
    elif media_type == "text_note":
        return "ingest_text_note"
        
    # 3. Default RAG
    else:
        return "query_reformulation"

def route_grading(state: AgentState):
    """
    Router after grading documents.
    """
    if state["is_relevant"]:
        return "generate"
    else:
        return "fallback"

workflow = StateGraph(AgentState)

# RAG Nodes
workflow.add_node("query_reformulation", query_reformulation)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)
workflow.add_node("fallback", fallback_nodes)
workflow.add_node("system_status_response", system_status_response)

# Ingestion Nodes
workflow.add_node("ingest_pdf", ingest_pdf)
workflow.add_node("ingest_url", ingest_url)
workflow.add_node("ingest_image", ingest_image)
workflow.add_node("ingest_text_note", ingest_text_note)

# Edges
workflow.set_conditional_entry_point(
    route_start,
    {
        "query_reformulation": "query_reformulation",
        "ingest_pdf": "ingest_pdf",
        "ingest_url": "ingest_url",
        "ingest_image": "ingest_image",
        "ingest_text_note": "ingest_text_note",
        "system_status_response": "system_status_response"
    }
)

# RAG Flow Edges
workflow.add_edge("query_reformulation", "retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges(
    "grade_documents",
    route_grading,
    {
        "generate": "generate",
        "fallback": "fallback"
    }
)
workflow.add_edge("generate", END)
workflow.add_edge("fallback", END)
workflow.add_edge("system_status_response", END)

# Ingestion Flow Edges
workflow.add_edge("ingest_pdf", END)
workflow.add_edge("ingest_url", END)
workflow.add_edge("ingest_image", END)
workflow.add_edge("ingest_text_note", END)

agent_app = workflow.compile()
