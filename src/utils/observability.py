"""
Langfuse Observability Integration
Tracks agent performance, tool usage, and user interactions
"""
import os
from functools import wraps
from datetime import datetime
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

# Initialize Langfuse
langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)


@observe()
def track_agent_call(user_input: str, response: str, tool_calls: list = None):
    """
    Track a complete agent interaction.
    
    Args:
        user_input: User's input message
        response: Agent's response
        tool_calls: List of tools called during interaction
    """
    langfuse_context.update_current_trace(
        name="agent_interaction",
        input=user_input,
        output=response,
        metadata={
            "tool_calls": tool_calls or [],
            "timestamp": datetime.now().isoformat()
        }
    )


@observe()
def track_tool_call(tool_name: str, args: dict, result: str, duration_ms: float):
    """
    Track individual tool calls.
    
    Args:
        tool_name: Name of the tool called
        args: Arguments passed to the tool
        result: Tool's return value
        duration_ms: Execution time in milliseconds
    """
    langfuse_context.update_current_observation(
        name=f"tool_call_{tool_name}",
        input=args,
        output=result,
        metadata={
            "tool": tool_name,
            "duration_ms": duration_ms
        }
    )


def observe_agent(func):
    """
    Decorator to automatically track agent functions.
    
    Usage:
        @observe_agent
        def my_agent_function(input: str):
            ...
    """
    @wraps(func)
    @observe()
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Update trace
            langfuse_context.update_current_trace(
                name=func.__name__,
                metadata={
                    "duration_ms": duration,
                    "status": "success"
                }
            )
            
            return result
        
        except Exception as e:
            # Track errors
            langfuse_context.update_current_trace(
                name=func.__name__,
                metadata={
                    "status": "error",
                    "error": str(e)
                }
            )
            raise
    
    return wrapper


class ObservabilityContext:
    """Context manager for tracking agent sessions"""
    
    def __init__(self, session_id: str, user_id: str = None):
        self.session_id = session_id
        self.user_id = user_id
        self.trace = None
    
    def __enter__(self):
        self.trace = langfuse.trace(
            name="agent_session",
            session_id=self.session_id,
            user_id=self.user_id,
            metadata={
                "start_time": datetime.now().isoformat()
            }
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.trace:
            self.trace.update(
                metadata={
                    "end_time": datetime.now().isoformat(),
                    "status": "error" if exc_type else "success"
                }
            )


def get_performance_metrics(session_id: str = None) -> dict:
    """
    Retrieve performance metrics from Langfuse.
    
    Args:
        session_id: Optional session ID to filter metrics
    
    Returns:
        Dictionary of performance metrics
    """
    # Note: This requires Langfuse API calls
    # For now, return placeholder structure
    return {
        "total_traces": 0,
        "avg_duration_ms": 0,
        "tool_usage": {},
        "error_rate": 0.0
    }


# Export decorated versions of key functions
def setup_observability():
    """
    Setup observability for the agent.
    Call this at application startup.
    """
    print("✅ Langfuse observability initialized")
    print(f"📊 Dashboard: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")


# Example usage in your code:
"""
from src.utils.observability import observe_agent, track_agent_call

@observe_agent
def my_agent_function(user_input: str):
    # Your agent logic
    response = agent.run(user_input)
    
    # Track the interaction
    track_agent_call(
        user_input=user_input,
        response=response,
        tool_calls=agent.tool_history
    )
    
    return response
"""