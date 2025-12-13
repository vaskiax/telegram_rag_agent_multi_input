
import os
import sys
import logging

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.agent.state import AgentState
from app.agent import nodes

logging.basicConfig(level=logging.INFO)

# Mock state
state = AgentState(
    question="Cual es el tamaño de electrón ?",
    chat_history=[],
    reformulated_query="",
    context=[],
    is_relevant=False,
    final_answer="",
    media_type="text"
)


# Redirect stdout to file
with open("debug_output.txt", "w", encoding="utf-8") as f:
    sys.stdout = f
    
    print(f"--- STARTING DEBUG FLOW FOR: {state['question']} ---")

    # 1. Reformulation
    print("\n[1] REFORMULATION")
    try:
        res = nodes.query_reformulation(state)
        state["reformulated_query"] = res["reformulated_query"]
        print(f"Reformulated Query: {state['reformulated_query']}")
    except Exception as e:
        print(f"Reformulation Failed: {e}")

    # 2. Retrieval
    print("\n[2] RETRIEVAL")
    try:
        res = nodes.retrieve(state)
        state["context"] = res["context"]
        print(f"Retrieved {len(state['context'])} docs.")
        for i, doc in enumerate(state["context"]):
            print(f"  [Doc {i}] --------------------------------------------------")
            print(doc)
            print("  ------------------------------------------------------------")
    except Exception as e:
        print(f"Retrieval Failed: {e}")

    # 3. Grading
    print("\n[3] GRADING")
    try:
        res = nodes.grade_documents(state)
        state["is_relevant"] = res["is_relevant"]
        print(f"Is Relevant: {state['is_relevant']}")
    except Exception as e:
        print(f"Grading Failed: {e}")

    if not state["is_relevant"]:
        print("\n[RESULT] Fallback would be triggered.")
    else:
        print("\n[RESULT] Generator would be called.")
        
    sys.stdout = sys.__stdout__

