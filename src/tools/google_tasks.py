"""
Google Tasks API Tools
Create, read, update, and manage tasks
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
from langchain_core.tools import tool
from dateutil import parser

from src.utils.google_auth import get_tasks_service


def get_or_create_tasklist(tasklist_name: str = "DevFlow Tasks") -> str:
    """
    Get or create a task list.
    
    Args:
        tasklist_name: Name of the task list
    
    Returns:
        Task list ID
    """
    service = get_tasks_service()
    
    # Get all task lists
    results = service.tasklists().list().execute()
    tasklists = results.get('items', [])
    
    # Find existing list
    for tasklist in tasklists:
        if tasklist['title'] == tasklist_name:
            return tasklist['id']
    
    # Create new list if not found
    new_list = service.tasklists().insert(
        body={'title': tasklist_name}
    ).execute()
    
    return new_list['id']


@tool
def create_task(
    title: str,
    priority: Literal["low", "medium", "high", "critical"],
    estimated_hours: float,
    description: str = "",
    due_date: Optional[str] = None
) -> str:
    """
    Create a new development task in Google Tasks.
    
    Args:
        title: Task title
        priority: Task priority (low, medium, high, critical)
        estimated_hours: Estimated time to complete in hours
        description: Task description
        due_date: Optional due date (YYYY-MM-DD or natural language)
    
    Returns:
        Success message with task details
    """
    try:
        service = get_tasks_service()
        tasklist_id = get_or_create_tasklist()
        
        # Priority emoji mapping
        priority_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        
        # Build task notes with metadata
        notes = f"{description}\n\n---\nPriority: {priority}\nEstimated: {estimated_hours}h"
        
        # Create task body
        task_body = {
            'title': f"{priority_emoji.get(priority, '⚪')} {title}",
            'notes': notes
        }
        
        # Add due date if provided
        if due_date:
            try:
                if due_date.lower() in ["today", "tomorrow"]:
                    if due_date.lower() == "today":
                        due_dt = datetime.now()
                    else:
                        due_dt = datetime.now() + timedelta(days=1)
                else:
                    due_dt = parser.parse(due_date)
                
                # Google Tasks expects RFC 3339 timestamp
                task_body['due'] = due_dt.strftime('%Y-%m-%dT00:00:00.000Z')
            except:
                pass
        
        # Create task
        result = service.tasks().insert(
            tasklist=tasklist_id,
            body=task_body
        ).execute()
        
        return (
            f"✅ Task created!\n\n"
            f"{priority_emoji.get(priority, '⚪')} {title}\n"
            f"Priority: {priority}\n"
            f"Estimated: {estimated_hours}h\n"
            f"ID: {result['id'][:8]}..."
        )
    
    except Exception as e:
        return f"❌ Error creating task: {str(e)}"


@tool
def list_tasks(status: Literal["all", "pending", "completed"] = "pending") -> str:
    """
    List tasks from Google Tasks.
    
    Args:
        status: Filter by status (all, pending, completed)
    
    Returns:
        Formatted list of tasks
    """
    try:
        service = get_tasks_service()
        tasklist_id = get_or_create_tasklist()
        
        # Fetch tasks
        params = {'tasklist': tasklist_id, 'maxResults': 100}
        
        if status == "completed":
            params['showCompleted'] = True
            params['showHidden'] = True
        
        results = service.tasks().list(**params).execute()
        tasks = results.get('items', [])
        
        if not tasks:
            return "📝 No tasks found."
        
        # Filter by status
        if status == "pending":
            tasks = [t for t in tasks if t.get('status') != 'completed']
        elif status == "completed":
            tasks = [t for t in tasks if t.get('status') == 'completed']
        
        result = f"📋 Tasks ({len(tasks)}):\n\n"
        
        for task in tasks:
            # Extract priority from title
            title = task.get('title', 'Untitled')
            status_emoji = "✅" if task.get('status') == 'completed' else "⏳"
            
            result += f"{status_emoji} {title}\n"
            
            # Extract metadata from notes
            notes = task.get('notes', '')
            if notes:
                lines = notes.split('\n')
                for line in lines:
                    if 'Priority:' in line or 'Estimated:' in line:
                        result += f"   {line.strip()}\n"
            
            if task.get('due'):
                due_date = parser.parse(task['due'])
                result += f"   📅 Due: {due_date.strftime('%b %d, %Y')}\n"
            
            result += "\n"
        
        return result.strip()
    
    except Exception as e:
        return f"❌ Error listing tasks: {str(e)}"


@tool
def update_task_status(task_title: str, completed: bool = True) -> str:
    """
    Mark a task as completed or pending.
    
    Args:
        task_title: Title of the task (or partial match)
        completed: True to mark as completed, False for pending
    
    Returns:
        Success or error message
    """
    try:
        service = get_tasks_service()
        tasklist_id = get_or_create_tasklist()
        
        # Find task by title
        results = service.tasks().list(
            tasklist=tasklist_id,
            maxResults=100
        ).execute()
        tasks = results.get('items', [])
        
        # Search for matching task
        matching_task = None
        for task in tasks:
            if task_title.lower() in task.get('title', '').lower():
                matching_task = task
                break
        
        if not matching_task:
            return f"❌ Task not found: {task_title}"
        
        # Update task
        matching_task['status'] = 'completed' if completed else 'needsAction'
        
        if completed:
            matching_task['completed'] = datetime.now().isoformat() + 'Z'
        
        service.tasks().update(
            tasklist=tasklist_id,
            task=matching_task['id'],
            body=matching_task
        ).execute()
        
        status_text = "completed" if completed else "pending"
        return f"✅ Task marked as {status_text}: {matching_task['title']}"
    
    except Exception as e:
        return f"❌ Error updating task: {str(e)}"


@tool
def delete_task(task_title: str) -> str:
    """
    Delete a task from Google Tasks.
    
    Args:
        task_title: Title of the task to delete
    
    Returns:
        Success or error message
    """
    try:
        service = get_tasks_service()
        tasklist_id = get_or_create_tasklist()
        
        # Find task
        results = service.tasks().list(
            tasklist=tasklist_id,
            maxResults=100
        ).execute()
        tasks = results.get('items', [])
        
        matching_task = None
        for task in tasks:
            if task_title.lower() in task.get('title', '').lower():
                matching_task = task
                break
        
        if not matching_task:
            return f"❌ Task not found: {task_title}"
        
        # Delete task
        service.tasks().delete(
            tasklist=tasklist_id,
            task=matching_task['id']
        ).execute()
        
        return f"✅ Task deleted: {matching_task['title']}"
    
    except Exception as e:
        return f"❌ Error deleting task: {str(e)}"


@tool
def get_task_statistics() -> str:
    """
    Get statistics about tasks (completion rate, pending count, etc.).
    
    Returns:
        Task statistics
    """
    try:
        service = get_tasks_service()
        tasklist_id = get_or_create_tasklist()
        
        # Fetch all tasks
        results = service.tasks().list(
            tasklist=tasklist_id,
            showCompleted=True,
            showHidden=True,
            maxResults=100
        ).execute()
        tasks = results.get('items', [])
        
        if not tasks:
            return "📊 No tasks found."
        
        # Calculate stats
        total = len(tasks)
        completed = len([t for t in tasks if t.get('status') == 'completed'])
        pending = total - completed
        
        # Count overdue tasks
        overdue = 0
        today = datetime.now()
        for task in tasks:
            if task.get('status') != 'completed' and task.get('due'):
                due_date = parser.parse(task['due'])
                if due_date < today:
                    overdue += 1
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        result = "📊 Task Statistics:\n\n"
        result += f"Total Tasks: {total}\n"
        result += f"✅ Completed: {completed}\n"
        result += f"⏳ Pending: {pending}\n"
        result += f"⚠️ Overdue: {overdue}\n"
        result += f"\nCompletion Rate: {completion_rate:.1f}%\n"
        
        return result
    
    except Exception as e:
        return f"❌ Error fetching statistics: {str(e)}"


@tool
def prioritize_tasks() -> str:
    """
    Analyze and suggest task prioritization.
    
    Returns:
        Prioritized task list with recommendations
    """
    try:
        service = get_tasks_service()
        tasklist_id = get_or_create_tasklist()
        
        # Fetch pending tasks
        results = service.tasks().list(
            tasklist=tasklist_id,
            maxResults=100
        ).execute()
        tasks = results.get('items', [])
        
        pending_tasks = [t for t in tasks if t.get('status') != 'completed']
        
        if not pending_tasks:
            return "✨ No pending tasks! Time to plan your next sprint."
        
        # Sort by due date and priority
        def get_priority_score(task):
            title = task.get('title', '')
            
            # Extract priority from emoji
            if '🔴' in title:
                return 4
            elif '🟠' in title:
                return 3
            elif '🟡' in title:
                return 2
            else:
                return 1
        
        sorted_tasks = sorted(
            pending_tasks,
            key=lambda t: (
                -get_priority_score(t),
                t.get('due', '9999-12-31')
            )
        )
        
        result = "🎯 Recommended Task Priority:\n\n"
        
        for i, task in enumerate(sorted_tasks[:10], 1):
            title = task.get('title', 'Untitled')
            result += f"{i}. {title}\n"
            
            if task.get('due'):
                due_date = parser.parse(task['due'])
                days_until = (due_date - datetime.now()).days
                
                if days_until < 0:
                    result += f"   ⚠️ OVERDUE by {abs(days_until)} days!\n"
                elif days_until == 0:
                    result += f"   🔥 Due TODAY!\n"
                elif days_until <= 3:
                    result += f"   ⏰ Due in {days_until} days\n"
            
            result += "\n"
        
        return result.strip()
    
    except Exception as e:
        return f"❌ Error prioritizing tasks: {str(e)}"


# Export tools
TASKS_TOOLS = [
    create_task,
    list_tasks,
    update_task_status,
    delete_task,
    get_task_statistics,
    prioritize_tasks
]