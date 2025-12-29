"""
Agent State Management for DevFlow AI
Defines the state structure for the LangGraph agent
"""
from typing import Annotated, TypedDict, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    State for the developer productivity agent.
    
    Attributes:
        messages: Conversation history
        current_task: Active task being worked on
        tasks: List of all tasks
        sessions: Scheduled coding sessions
        reflection: Latest self-reflection output
        tool_calls: History of tool calls made
        user_context: Developer's preferences and context
    """
    # Conversation
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Task Management
    current_task: str | None
    tasks: list[dict]
    
    # Scheduling
    sessions: list[dict]
    
    # Reflection & Memory
    reflection: str | None
    tool_calls: list[dict]
    
    # User Context
    user_context: dict


class DeveloperContext(TypedDict):
    """Developer-specific context"""
    name: str
    role: str  
    tech_stack: list[str]
    work_hours: dict  # {"start": "09:00", "end": "17:00"}
    break_preferences: dict
    focus_duration: int  # minutes
    daily_goal: str | None