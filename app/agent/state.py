from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    question: str
    reformulated_query: str
    context: List[str]
    is_relevant: bool
    final_answer: str
    # Ingestion Fields
    file_path: Optional[str]
    url: Optional[str]
    media_type: Optional[str] # 'pdf', 'url', 'image', 'audio'
    ingestion_status: Optional[str]
