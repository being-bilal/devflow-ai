"""
Self-Reflection Tool
Agent analyzes its own performance using Google Tasks and Calendar data
"""
from langchain_core.tools import tool
from datetime import datetime, timedelta
from dateutil import parser

from src.utils.google_auth import get_tasks_service, get_calendar_service


@tool
def self_reflect() -> str:
    """
    Perform comprehensive self-reflection on productivity and task completion.
    Analyzes Google Tasks and Calendar data to provide insights.
    
    Returns:
        Detailed reflection report with insights and recommendations
    """
    try:
        tasks_service = get_tasks_service()
        calendar_service = get_calendar_service()
        
        # Get default task list
        tasklists = tasks_service.tasklists().list().execute().get('items', [])
        if not tasklists:
            return "❌ No task lists found. Create tasks first."
        
        tasklist_id = tasklists[0]['id']
        
        # Fetch all tasks
        all_tasks = tasks_service.tasks().list(
            tasklist=tasklist_id,
            showCompleted=True,
            showHidden=True,
            maxResults=100
        ).execute().get('items', [])
        
        # Analyze tasks
        total_tasks = len(all_tasks)
        completed_tasks = [t for t in all_tasks if t.get('status') == 'completed']
        pending_tasks = [t for t in all_tasks if t.get('status') != 'completed']
        
        # Check for overdue tasks
        overdue_tasks = []
        today = datetime.now()
        for task in pending_tasks:
            if task.get('due'):
                due_date = parser.parse(task['due'])
                if due_date < today:
                    overdue_tasks.append(task)
        
        # Calculate completion rate
        completion_rate = (len(completed_tasks) / total_tasks * 100) if total_tasks > 0 else 0
        
        # Analyze calendar (today's events)
        now = datetime.now()
        time_min = now.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
        time_max = now.replace(hour=23, minute=59, second=59).isoformat() + 'Z'
        
        events = calendar_service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute().get('items', [])
        
        # Build reflection report
        result = "🤔 Self-Reflection Report\n"
        result += "=" * 60 + "\n\n"
        
        # 1. Current State
        result += "📊 Current State:\n"
        result += f"  • Total Tasks: {total_tasks}\n"
        result += f"  • Completed: {len(completed_tasks)} ({completion_rate:.1f}%)\n"
        result += f"  • Pending: {len(pending_tasks)}\n"
        result += f"  • Overdue: {len(overdue_tasks)}\n"
        result += f"  • Calendar Events Today: {len(events)}\n\n"
        
        # 2. Step Completion Check
        result += "✅ Step Completion Check:\n"
        
        if pending_tasks:
            in_progress_count = 0
            blocked_count = 0
            
            for task in pending_tasks:
                title = task.get('title', '').lower()
                if '🚧' in title or 'in progress' in title:
                    in_progress_count += 1
                if '🚫' in title or 'blocked' in title:
                    blocked_count += 1
            
            if in_progress_count > 0:
                result += f"  ⚠️ {in_progress_count} task(s) in progress\n"
            if blocked_count > 0:
                result += f"  🚫 {blocked_count} task(s) blocked\n"
            
            result += f"  ⏳ {len(pending_tasks) - in_progress_count - blocked_count} task(s) not started\n"
        else:
            result += "  ✅ All tasks completed!\n"
        
        result += "\n"
        
        # 3. Blocker Analysis
        result += "🚧 Blocker Analysis:\n"
        if overdue_tasks:
            result += f"  ⚠️ {len(overdue_tasks)} overdue task(s) need immediate attention:\n"
            for task in overdue_tasks[:3]:  # Top 3
                title = task.get('title', 'Untitled').replace('🔴', '').replace('🟠', '').replace('🟡', '').replace('🟢', '').strip()
                due = parser.parse(task['due'])
                days_overdue = (today - due).days
                result += f"     - {title} (overdue by {days_overdue} days)\n"
            result += "\n  💡 Recommendation: Prioritize overdue tasks or reschedule them\n"
        else:
            result += "  ✅ No overdue tasks\n"
        
        result += "\n"
        
        # 4. Priority Assessment
        result += "🎯 Priority Assessment:\n"
        high_priority = [t for t in pending_tasks if '🔴' in t.get('title', '') or '🟠' in t.get('title', '')]
        
        if high_priority:
            result += f"  ⚡ {len(high_priority)} high-priority task(s):\n"
            for task in high_priority[:3]:
                title = task.get('title', 'Untitled').replace('🔴', '').replace('🟠', '').strip()
                result += f"     - {title}\n"
            result += "\n  💡 Recommendation: Focus on high-priority items first\n"
        else:
            result += "  ✅ No urgent high-priority tasks\n"
        
        result += "\n"
        
        # 5. Time Management
        result += "⏱️ Time Management:\n"
        total_calendar_hours = 0
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            if 'T' in start:  # Has time component
                start_dt = parser.parse(start)
                end_dt = parser.parse(end)
                duration = (end_dt - start_dt).total_seconds() / 3600
                total_calendar_hours += duration
        
        result += f"  • Scheduled today: {total_calendar_hours:.1f} hours\n"
        result += f"  • Events today: {len(events)}\n"
        
        if total_calendar_hours > 8:
            result += "  ⚠️ Heavy schedule today\n"
            result += "  💡 Recommendation: Ensure adequate breaks\n"
        elif total_calendar_hours < 4 and pending_tasks:
            result += "  💡 Recommendation: Schedule focus time for pending tasks\n"
        
        result += "\n"
        
        # 6. Productivity Insights
        result += "📈 Productivity Insights:\n"
        
        if completion_rate >= 70:
            result += f"  🎉 Great work! {completion_rate:.0f}% completion rate\n"
        elif completion_rate >= 50:
            result += f"  👍 Good progress at {completion_rate:.0f}% completion\n"
        elif completion_rate >= 30:
            result += f"  ⚠️ Moderate completion at {completion_rate:.0f}%\n"
        else:
            result += f"  ⚠️ Low completion rate at {completion_rate:.0f}%\n"
        
        # Recent completed tasks
        recent_completed = [t for t in completed_tasks if t.get('completed')]
        recent_completed.sort(key=lambda x: x.get('completed', ''), reverse=True)
        
        if recent_completed:
            result += f"  ✅ Recently completed: {len(recent_completed[:5])} task(s)\n"
        
        result += "\n"
        
        # 7. Key Recommendations
        result += "💡 Key Recommendations:\n"
        recommendations = []
        
        if completion_rate < 50:
            recommendations.append("Low completion rate - focus on finishing tasks before starting new ones")
        
        if len(overdue_tasks) > 0:
            recommendations.append(f"Address {len(overdue_tasks)} overdue task(s) immediately")
        
        if len(high_priority) > 0 and total_calendar_hours < 4:
            recommendations.append("Schedule dedicated time for high-priority tasks")
        
        if len(pending_tasks) > 10:
            recommendations.append("Too many pending tasks - consider breaking them down or archiving old ones")
        
        if total_calendar_hours < 2 and len(pending_tasks) > 0:
            recommendations.append("Light calendar today - good opportunity for deep work")
        
        if not recommendations:
            recommendations.append("Keep up the great work! Stay consistent")
        
        for i, rec in enumerate(recommendations, 1):
            result += f"  {i}. {rec}\n"
        
        result += "\n"
        
        # 8. What's Next
        result += "🚀 What's Next:\n"
        if pending_tasks:
            # Find next task (highest priority)
            next_task = None
            for priority_emoji in ['🔴', '🟠', '🟡', '🟢']:
                candidates = [t for t in pending_tasks if priority_emoji in t.get('title', '')]
                if candidates:
                    next_task = candidates[0]
                    break
            
            if not next_task and pending_tasks:
                next_task = pending_tasks[0]
            
            if next_task:
                title = next_task.get('title', 'Untitled')
                result += f"  → Suggested next task: {title}\n"
                
                if next_task.get('due'):
                    due_date = parser.parse(next_task['due'])
                    days_until = (due_date - today).days
                    if days_until == 0:
                        result += f"     ⏰ Due TODAY!\n"
                    elif days_until > 0:
                        result += f"     📅 Due in {days_until} days\n"
        else:
            result += "  ✨ All tasks complete! Time to plan your next goals.\n"
        
        return result
    
    except Exception as e:
        return f"❌ Error performing self-reflection: {str(e)}"


@tool
def analyze_weekly_trends() -> str:
    """
    Analyze productivity trends over the past week.
    
    Returns:
        Weekly trend analysis
    """
    try:
        tasks_service = get_tasks_service()
        calendar_service = get_calendar_service()
        
        # Get task list
        tasklists = tasks_service.tasklists().list().execute().get('items', [])
        if not tasklists:
            return "❌ No task lists found"
        
        tasklist_id = tasklists[0]['id']
        
        # Fetch completed tasks from last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        
        all_tasks = tasks_service.tasks().list(
            tasklist=tasklist_id,
            showCompleted=True,
            showHidden=True,
            completedMin=week_ago.isoformat() + 'Z',
            maxResults=100
        ).execute().get('items', [])
        
        completed_this_week = [t for t in all_tasks if t.get('status') == 'completed']
        
        result = "📊 Weekly Productivity Trends\n"
        result += "=" * 60 + "\n\n"
        
        result += f"📅 Past 7 Days:\n"
        result += f"  • Tasks Completed: {len(completed_this_week)}\n"
        result += f"  • Average per Day: {len(completed_this_week) / 7:.1f}\n\n"
        
        if completed_this_week:
            result += "✅ Recent Completions:\n"
            for task in completed_this_week[:5]:
                title = task.get('title', 'Untitled')
                completed = task.get('completed')
                if completed:
                    completed_dt = parser.parse(completed)
                    result += f"  • {title}\n"
                    result += f"    Completed: {completed_dt.strftime('%b %d at %I:%M %p')}\n"
        
        result += "\n💡 Keep tracking your progress to identify patterns!"
        
        return result
    
    except Exception as e:
        return f"❌ Error analyzing trends: {str(e)}"


# Export tools
REFLECTION_TOOLS = [
    self_reflect,
    analyze_weekly_trends
]