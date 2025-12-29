"""
Model Context Protocol (MCP) Server for DevFlow AI
Exposes agent capabilities as MCP tools
"""
import asyncio
import json
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server

from src.storage.memory import TaskMemory
from src.agent.graph import run_agent

# Initialize
app = Server("devflow-ai")
memory = TaskMemory()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List all available MCP tools.
    """
    return [
        Tool(
            name="create_dev_task",
            description="Create a new development task with priority and time estimate",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title/summary"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Task priority level"
                    },
                    "estimated_hours": {
                        "type": "number",
                        "description": "Estimated time to complete in hours"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed task description"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Task tags (e.g., backend, bug, api)"
                    }
                },
                "required": ["title", "priority", "estimated_hours"]
            }
        ),
        Tool(
            name="list_dev_tasks",
            description="List development tasks, optionally filtered by status",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "blocked", "done"],
                        "description": "Filter by status (optional)"
                    }
                }
            }
        ),
        Tool(
            name="update_task_status",
            description="Update the status of a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID of the task to update"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "blocked", "done"],
                        "description": "New status"
                    }
                },
                "required": ["task_id", "status"]
            }
        ),
        Tool(
            name="schedule_coding_session",
            description="Schedule a focused coding session for a task",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "ID of the task to work on"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time (HH:MM or natural language like 'after lunch')"
                    },
                    "duration_hours": {
                        "type": "number",
                        "description": "Session duration in hours"
                    },
                    "session_type": {
                        "type": "string",
                        "enum": ["coding", "review", "debugging", "learning"],
                        "description": "Type of session"
                    }
                },
                "required": ["task_id", "start_time", "duration_hours"]
            }
        ),
        Tool(
            name="get_daily_schedule",
            description="View scheduled coding sessions for a specific day",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to view (default: today)"
                    }
                }
            }
        ),
        Tool(
            name="productivity_reflection",
            description="Perform self-reflection on productivity and task completion",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="prioritize_tasks",
            description="Analyze and suggest task prioritization",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_productivity_stats",
            description="Get productivity statistics and completion metrics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="chat_with_agent",
            description="Natural language interaction with the DevFlow AI agent",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Your message to the agent"
                    }
                },
                "required": ["message"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Execute an MCP tool.
    """
    try:
        if name == "create_dev_task":
            task = memory.add_task(
                title=arguments["title"],
                priority=arguments["priority"],
                estimated_hours=arguments["estimated_hours"],
                description=arguments.get("description", ""),
                tags=arguments.get("tags")
            )
            return [TextContent(
                type="text",
                text=f"Task created: #{task['id']} - {task['title']}"
            )]
        
        elif name == "list_dev_tasks":
            tasks = memory.get_tasks(status=arguments.get("status"))
            
            if not tasks:
                return [TextContent(type="text", text="No tasks found.")]
            
            task_list = "📋 Tasks:\n\n"
            for task in tasks:
                task_list += f"#{task['id']} - {task['title']}\n"
                task_list += f"  Status: {task['status']} | Priority: {task['priority']}\n\n"
            
            return [TextContent(type="text", text=task_list)]
        
        elif name == "update_task_status":
            task = memory.update_task(
                arguments["task_id"],
                status=arguments["status"]
            )
            
            if task:
                return [TextContent(
                    type="text",
                    text=f"Task #{task['id']} updated to: {arguments['status']}"
                )]
            return [TextContent(
                type="text",
                text=f"Task #{arguments['task_id']} not found"
            )]
        
        elif name == "schedule_coding_session":
            # Use the agent to schedule
            from src.tools.code_session import schedule_coding_session
            result = schedule_coding_session.invoke(arguments)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_daily_schedule":
            from src.tools.code_session import get_daily_schedule
            result = get_daily_schedule.invoke(arguments)
            return [TextContent(type="text", text=result)]
        
        elif name == "productivity_reflection":
            from src.tools.reflection import self_reflect
            result = self_reflect.invoke({})
            return [TextContent(type="text", text=result)]
        
        elif name == "prioritize_tasks":
            from src.tools.task_manager import prioritize_tasks
            result = prioritize_tasks.invoke({})
            return [TextContent(type="text", text=result)]
        
        elif name == "get_productivity_stats":
            from src.tools.task_manager import get_productivity_stats
            result = get_productivity_stats.invoke({})
            return [TextContent(type="text", text=result)]
        
        elif name == "chat_with_agent":
            # Full agent interaction
            result = run_agent(arguments["message"])
            response = result["messages"][-1].content
            return [TextContent(type="text", text=response)]
        
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error executing tool: {str(e)}"
        )]


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    print("DevFlow AI MCP Server starting...")
    print("Listening on stdio...")
    asyncio.run(main())