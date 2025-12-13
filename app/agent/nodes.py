
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from app.agent.state import AgentState
from app.mcp_server.storage import storage
from app.core.config import settings

# Initialize LLM with DeepSeek
llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0
)

def query_reformulation(state: AgentState) -> Dict[str, Any]:
    print("---QUERY REFORMULATION---")
    question = state["question"]
    messages = state.get("messages", [])
    
    # Format history (last 5 interactions)
    # messages is List[BaseMessage]
    history_str = ""
    if messages:
        # Take last 6 messages (3 turns) excluding current human input if it's already there
        recent_msgs = messages[-6:] 
        for msg in recent_msgs:
            role = "Human" if msg.type == "human" else "AI"
            history_str += f"{role}: {msg.content}\n"
            
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at optimizing search queries for semantic vector databases. 
        Transform the user input into a specific, context-rich query.
        Use the Chat History to resolve pronouns like "it", "that", "the previous one" etc.
        
        If the question is standalone, just clean it up.
        If the question refers to history (e.g. "What did you say about X?"), include X in the new query.
        """),
        ("human", "Chat History:\n{history}\n\nUser Question: {question}\n\nOptimized Query:")
    ])
    chain = prompt | llm | StrOutputParser()
    reformulated = chain.invoke({"question": question, "history": history_str})
    return {"reformulated_query": reformulated}

def retrieve(state: AgentState) -> Dict[str, Any]:
    print("---RETRIEVAL (MCP TOOL CALL)---")
    query = state["reformulated_query"]
    docs = storage.search(query)
    return {"context": docs}

def grade_documents(state: AgentState) -> Dict[str, Any]:
    print("---GRADING DOCUMENTS---")
    # Bypass Strict Grading: Trust Vector Search
    # If we found documents, we assume they are relevant enough to attempt generation.
    # The Generator LLM will decide if it can answer or not.
    context = state["context"]
    if not context:
        return {"is_relevant": False}
        
    return {"is_relevant": True}

def generate(state: AgentState) -> Dict[str, Any]:
    print("---GENERATING ANSWER---")
    question = state["question"]
    context = state["context"]
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the 'Telegram Brain Agent', a charismatic and expert Physics Tutor.
        
        **CORE INSTRUCTION**:
        The texts provided in the Context are YOUR OWN INTERNAL KNOWLEDGE/MEMORY. You already know this!
        Therefore, you must NEVER say "According to the context" or "The document says". 
        Instead, speak with authority and confidence, as if you are teaching a student from your own mind.
        
        **TONE GUIDELINES**:
        - Be natural, engaging, and direct.
        - Explain concepts clearly (Feynman technique).
        - If asked a question, answer it directly. Do not meta-explain where you got the info.
           
        **LATEX INSTRUCTION (SMART VISUALS)**:
        - Use double dollar signs `$$` ONLY for meaningful, complex equations (integrals, sums, definitions) that need visualization.
        - For simple variables (like x, y, K) or short expressions, use standard text or bold text (e.g., **x**, **K**). Do NOT use `$$` for simple names.
        - Example logic:
          - "The integral is `$$ \int x dx $$`" -> Image (Good).
          - "The variable `$$ x $$`" -> Image (BAD - Spam). Use "**x**" instead.
           
        **CONTEXT USAGE**:
        - Use ONLY the provided context to form your answer, but DO NOT mention you are doing so.
        - If the answer is not in the context, say: "I don't have that specific information right now."
        """),
        ("human", "Chat History:\n{history}\n\nUser Question: {question}")
    ])
    chain = prompt | llm | StrOutputParser()
    context_str = "\n\n".join(context)
    
    # Format history for Generator (same as Reformulator)
    messages = state.get("messages", [])
    history_str = ""
    if messages:
        # Take last 6 messages
        recent_msgs = messages[-6:] 
        for msg in recent_msgs:
            # Skip the very last one if it's the current question (usually it is)
            if msg.content == question and msg.type == "human":
                 continue
            role = "Human" if msg.type == "human" else "AI"
            history_str += f"{role}: {msg.content}\n"
            
    answer = chain.invoke({"context": context_str, "question": question, "history": history_str})
    return {"final_answer": answer}

def fallback_nodes(state: AgentState) -> Dict[str, Any]:
    print("---FALLBACK RESPONSE---")
    return {"final_answer": "No tengo información sobre esto en tu base de conocimientos."}

def system_status_response(state: AgentState) -> Dict[str, Any]:
    print("---SYSTEM STATUS RESPONSE (SHORT CIRCUIT)---")
    question = state["question"]
    status_msg = "Unknown status"
    
    # Extract status from tag [SYSTEM_STATUS: ...]
    import re
    match = re.search(r"\[SYSTEM_STATUS: (.*?)\]", question)
    if match:
        status_msg = match.group(1)
        
    # We can either return raw status or use LLM to be polite.
    # Let's use simple logic for speed and no hallucinations.
    
    return {"final_answer": f"⚠️ Actualmente estoy ocupado realizando una tarea en segundo plano:\n\n**Estado**: {status_msg}\n\nPor favor espera a que termine para realizar nuevas consultas sobre este material."}
