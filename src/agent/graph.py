"""
LangGraph Agent for DevFlow AI - Enhanced Ollama Version
With markdown output formatting, effort analysis, and GitHub integration
"""
from typing import Literal, Dict, Tuple
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re
from src.tools.github_tools import GITHUB_TOOLS
from src.agent.state import AgentState
from src.tools.google_calendar import CALENDAR_TOOLS
from src.tools.google_tasks import TASKS_TOOLS
from src.tools.reflection import REFLECTION_TOOLS
from src.tools.github_tools import get_my_assigned_issues, get_my_pull_requests


load_dotenv()


# Combine all tools
ALL_TOOLS = CALENDAR_TOOLS + TASKS_TOOLS + REFLECTION_TOOLS + GITHUB_TOOLS

# Initialize Ollama LLM with optimized settings
llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    temperature=0.4,
    num_ctx=8192,
    repeat_penalty=1.1
).bind_tools(ALL_TOOLS)


def classify_output(response: str, tool_calls: list) -> str:
    """
    Classify agent output based on content and tool execution results.
    
    Returns: "success", "info", "warning", or "error"
    """
    response_lower = response.lower()
    
    # ERROR indicators
    error_patterns = [
        "error", "failed", "could not", "couldn't", "unable to",
        "not found", "invalid", "incorrect", "❌", "cannot",
        "exception", "crashed", "broken"
    ]
    
    if any(pattern in response_lower for pattern in error_patterns):
        return "error"
    
    # Check tool call failures
    if tool_calls:
        failed_tools = [tc for tc in tool_calls if tc.get("status") == "invalid"]
        if failed_tools:
            return "error"
    
    # WARNING indicators
    warning_patterns = [
        "blocked", "overdue", "high priority", "urgent", "pending",
        "attention", "⚠️", "limited", "quota", "exceeded",
        "missing", "incomplete"
    ]
    
    if any(pattern in response_lower for pattern in warning_patterns):
        warning_count = sum(1 for pattern in warning_patterns if pattern in response_lower)
        if warning_count >= 2:
            return "warning"
    
    # SUCCESS indicators
    success_patterns = [
        "created", "scheduled", "completed", "updated", "deleted",
        "✅", "successfully", "done", "finished", "saved",
        "confirmed", "added"
    ]
    
    if any(pattern in response_lower for pattern in success_patterns):
        return "success"
    
    # Check if tools were called successfully
    if tool_calls:
        successful_tools = [tc for tc in tool_calls if tc.get("status") == "valid"]
        if successful_tools:
            return "success"
    
    # Default to INFO for neutral responses
    return "info"


def should_include_effort_analysis(user_input: str) -> bool:
    """
    Determine if user is explicitly asking for workload/effort analysis.
    Only return True for explicit requests.
    """
    explicit_keywords = [
        "how am i doing",
        "how busy am i",
        "workload",
        "effort level",
        "analyze my schedule",
        "am i overloaded",
        "show my workload",
        "check my effort",
        "how loaded am i",
        "schedule analysis"
    ]
    
    user_lower = user_input.lower()
    return any(keyword in user_lower for keyword in explicit_keywords)


def get_github_comprehensive_summary() -> str:
    """
    Fetches all relevant user data from GitHub and formats it into 
    a single high-level dashboard.
    """
    try:
        # Fetch data using your verified tools
        issues_md = get_my_assigned_issues.invoke({})
        prs_md = get_my_pull_requests.invoke({})
        
        # Clean up the headers for the combined view
        issues_content = issues_md.replace("## 📌 Your Assigned Issues", "")
        prs_content = prs_md.replace("## 🔀 Your Pull Requests", "")

        dashboard = [
            "# 🖥️ GitHub Developer Dashboard",
            "---",
            "### 🛠️ Issues Needing Attention",
            issues_content if "✨" not in issues_md else "   - *No pending issues*",
            "\n### 🔍 Active Pull Requests",
            prs_content if "✨" not in prs_md else "   - *No active PRs*",
            "\n---",
            f"**Last Updated**: {datetime.now().strftime('%H:%M:%S')}"
        ]
        
        return "\n".join(dashboard)
    except Exception as e:
        return f"❌ **Dashboard Error**: {str(e)}"


def get_github_workload() -> Dict[str, any]:
    """
    Get GitHub workload data including issues and PRs.
    
    Returns:
        Dict with GitHub stats and formatted data for UI
    """
    try:
        from github import Github
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return {
                "total_issues": 0,
                "total_prs": 0,
                "assigned_issues": [],
                "my_prs": [],
                "estimated_hours": 0,
                "error": "GitHub token not configured"
            }
        
        gh = Github(token)
        user = gh.get_user()
        
        # Get assigned issues
        assigned_issues = []
        issues_search = gh.search_issues(f"assignee:{user.login} is:issue is:open")
        
        for issue in issues_search[:50]:  # Limit to 50
            priority = "medium"
            if any(l.name.lower() in ["critical", "urgent", "p0"] for l in issue.labels):
                priority = "critical"
            elif any(l.name.lower() in ["high", "important", "p1"] for l in issue.labels):
                priority = "high"
            elif any(l.name.lower() in ["low", "p3"] for l in issue.labels):
                priority = "low"
            
            assigned_issues.append({
                "number": issue.number,
                "title": issue.title,
                "repo": issue.repository.full_name,
                "url": issue.html_url,
                "priority": priority,
                "created": issue.created_at.strftime('%Y-%m-%d'),
                "comments": issue.comments,
                "labels": [l.name for l in issue.labels]
            })
        
        # Get my PRs
        my_prs = []
        prs_search = gh.search_issues(f"author:{user.login} is:pr is:open")
        
        for pr in prs_search[:50]:  # Limit to 50
            my_prs.append({
                "number": pr.number,
                "title": pr.title,
                "repo": pr.repository.full_name,
                "url": pr.html_url,
                "draft": pr.draft if hasattr(pr, 'draft') else False,
                "created": pr.created_at.strftime('%Y-%m-%d'),
                "comments": pr.comments,
                "reviews": getattr(pr, 'review_comments', 0)
            })
        
        # Estimate hours based on issues and PRs
        # Critical issues: 4h, High: 3h, Medium: 2h, Low: 1h
        # PRs awaiting review: 0.5h per PR
        estimated_hours = 0
        for issue in assigned_issues:
            if issue["priority"] == "critical":
                estimated_hours += 4
            elif issue["priority"] == "high":
                estimated_hours += 3
            elif issue["priority"] == "medium":
                estimated_hours += 2
            else:
                estimated_hours += 1
        
        # PRs need attention for reviews
        estimated_hours += len(my_prs) * 0.5
        
        return {
            "total_issues": len(assigned_issues),
            "total_prs": len(my_prs),
            "assigned_issues": assigned_issues,
            "my_prs": my_prs,
            "estimated_hours": round(estimated_hours, 1),
            "error": None
        }
        
    except Exception as e:
        return {
            "total_issues": 0,
            "total_prs": 0,
            "assigned_issues": [],
            "my_prs": [],
            "estimated_hours": 0,
            "error": str(e)
        }


def calculate_schedule_effort(state: AgentState, include_github: bool = True) -> Dict[str, any]:
    """
    Calculate effort level based on tasks, calendar events, and GitHub work.
    """
    try:
        from src.tools.google_tasks import list_tasks
        from src.tools.google_calendar import get_calendar_events
        
        # Get tasks
        tasks_result = list_tasks.invoke({"status": "pending"})
        pending_hours = 0.0
        task_count = 0
        
        for line in tasks_result.split('\n'):
            if 'Est:' in line:
                try:
                    hours_match = re.search(r'Est:\s*([\d.]+)h', line)
                    if hours_match:
                        pending_hours += float(hours_match.group(1))
                        task_count += 1
                except:
                    pass
        
        # Get calendar events
        calendar_result = get_calendar_events.invoke({"date": "today"})
        scheduled_hours = 0.0
        event_count = 0
        
        for line in calendar_result.split('\n'):
            if '(' in line and 'h)' in line:
                try:
                    duration_match = re.search(r'\((\d+\.?\d*)h', line)
                    if duration_match:
                        scheduled_hours += float(duration_match.group(1))
                        event_count += 1
                except:
                    pass
        
        # Get GitHub workload
        github_hours = 0.0
        github_issues = 0
        github_prs = 0
        github_data = None
        
        if include_github:
            github_data = get_github_workload()
            github_hours = github_data.get("estimated_hours", 0)
            github_issues = github_data.get("total_issues", 0)
            github_prs = github_data.get("total_prs", 0)
        
        total_hours = pending_hours + scheduled_hours + github_hours
        standard_day = 8.0
        
        if total_hours < 4:
            effort_level = "low"
            effort_description = "Light workload - good opportunity for deep work or learning"
        elif total_hours < 8:
            effort_level = "medium"
            effort_description = "Balanced workload - maintain steady pace"
        elif total_hours < 12:
            effort_level = "high"
            effort_description = "Heavy workload - prioritize and take breaks"
        else:
            effort_level = "overloaded"
            effort_description = "Overloaded schedule - consider rescheduling or delegating"
        
        utilization = (total_hours / standard_day) * 100
        
        analysis = {
            "summary": effort_description,
            "utilization": f"{utilization:.1f}%",
            "breakdown": {
                "scheduled_events": f"{event_count} events ({scheduled_hours:.1f}h)",
                "pending_tasks": f"{task_count} tasks ({pending_hours:.1f}h)",
                "github_work": f"{github_issues} issues + {github_prs} PRs ({github_hours:.1f}h)",
                "total_workload": f"{total_hours:.1f}h"
            },
            "recommendations": []
        }
        
        if effort_level == "low":
            analysis["recommendations"] = [
                "Good time to tackle complex tasks",
                "Consider scheduling focus time",
                "Review backlog for new tasks"
            ]
        elif effort_level == "medium":
            analysis["recommendations"] = [
                "Maintain current pace",
                "Schedule regular breaks",
                "Monitor task completion"
            ]
        elif effort_level == "high":
            analysis["recommendations"] = [
                "Prioritize high-impact tasks",
                "Defer low-priority items",
                "Block focus time, minimize meetings",
                "Take breaks every 90 minutes"
            ]
        else:
            analysis["recommendations"] = [
                "⚠️ Reschedule non-urgent tasks",
                "⚠️ Consider delegating work",
                "⚠️ Communicate workload to team",
                "⚠️ Focus only on critical items"
            ]
        
        return {
            "effort_level": effort_level,
            "total_hours": round(total_hours, 1),
            "scheduled_hours": round(scheduled_hours, 1),
            "pending_hours": round(pending_hours, 1),
            "github_hours": round(github_hours, 1),
            "utilization_percent": round(utilization, 1),
            "analysis": analysis,
            "github_data": github_data
        }
        
    except Exception as e:
        return {
            "effort_level": "unknown",
            "total_hours": 0,
            "scheduled_hours": 0,
            "pending_hours": 0,
            "github_hours": 0,
            "utilization_percent": 0,
            "analysis": {
                "summary": f"Could not calculate effort: {str(e)}",
                "utilization": "N/A",
                "breakdown": {},
                "recommendations": []
            },
            "github_data": None
        }


def format_effort_report(effort_data: Dict) -> str:
    """
    Format effort analysis into markdown report.
    """
    effort_emoji = {
        "low": "🟢",
        "medium": "🟡",
        "high": "🟠",
        "overloaded": "🔴",
        "unknown": "⚪"
    }
    
    level = effort_data["effort_level"]
    emoji = effort_emoji.get(level, "⚪")
    
    report = f"\n## 📊 Workload Analysis\n\n"
    report += f"{emoji} **Effort Level**: {level.upper()}\n\n"
    
    analysis = effort_data["analysis"]
    report += f"**Summary**: {analysis['summary']}\n\n"
    report += f"**Utilization**: {analysis['utilization']}\n\n"
    
    if analysis["breakdown"]:
        report += "### Breakdown\n\n"
        for key, value in analysis["breakdown"].items():
            report += f"- **{key.replace('_', ' ').title()}**: {value}\n"
    
    if analysis["recommendations"]:
        report += f"\n### Recommendations\n\n"
        for rec in analysis["recommendations"]:
            report += f"- {rec}\n"
    
    return report


def get_daily_work_summary() -> dict:
    """
    Get total workload across Calendar + Tasks + GitHub.
    Helps answer prompts like:
    - "What do I have to do today?"
    - "How busy am I?"
    - "Summarize my work for the day"
    - "Plan my day"

    Returns a dict with all work items and formatted summary.
    """
    summary = {
        "events_today": 0,
        "tasks_pending": 0,
        "github_issues": 0,
        "github_prs": 0,
        "github_data": None,
        "tasks_data": [],
        "events_data": []
    }

    # -------------------- GOOGLE TASKS --------------------
    try:
        from src.tools.google_tasks import list_tasks
        task_data = list_tasks.invoke({"status": "pending"})
        summary["tasks_pending"] = task_data.count("**") // 2  # Count task titles
        summary["tasks_data"] = task_data
    except:
        pass

    # ------------------- GOOGLE CALENDAR -------------------
    try:
        from src.tools.google_calendar import get_calendar_events
        events = get_calendar_events.invoke({"date": "today"})
        summary["events_today"] = events.count("🕐")
        summary["events_data"] = events
    except:
        pass

    # ---------------------- GITHUB -------------------------
    github_data = get_github_workload()
    summary["github_issues"] = github_data.get("total_issues", 0)
    summary["github_prs"] = github_data.get("total_prs", 0)
    summary["github_data"] = github_data

    # ------------------ FINAL NATURAL SUMMARY ------------------
    summary["summary"] = (
        f"Today you have {summary['events_today']} calendar events, "
        f"{summary['tasks_pending']} pending tasks, "
        f"{summary['github_issues']} assigned GitHub issues, and "
        f"{summary['github_prs']} open pull requests."
    )

    return summary


def parse_natural_time(time_str: str) -> str:
    """Parse natural language time to ISO format."""
    time_str = time_str.lower().strip()
    now = datetime.now()
    
    time_mapping = {
        "now": now,
        "in an hour": now + timedelta(hours=1),
        "in 2 hours": now + timedelta(hours=2),
        "after lunch": now.replace(hour=13, minute=0, second=0, microsecond=0),
        "lunch": now.replace(hour=12, minute=0, second=0, microsecond=0),
        "morning": now.replace(hour=9, minute=0, second=0, microsecond=0),
        "afternoon": now.replace(hour=14, minute=0, second=0, microsecond=0),
        "evening": now.replace(hour=18, minute=0, second=0, microsecond=0),
        "tonight": now.replace(hour=19, minute=0, second=0, microsecond=0),
        "tomorrow": (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
        "tomorrow morning": (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
        "tomorrow afternoon": (now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0),
        "next week": (now + timedelta(days=7)).replace(hour=9, minute=0, second=0, microsecond=0),
    }
    
    if time_str in time_mapping:
        return time_mapping[time_str].isoformat()
    
    time_pattern = r'at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
    match = re.search(time_pattern, time_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
            
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if target_time < now:
            target_time += timedelta(days=1)
            
        return target_time.isoformat()
    
    duration_pattern = r'in (\d+)\s*(hour|minute)s?'
    match = re.search(duration_pattern, time_str)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'hour':
            target_time = now + timedelta(hours=amount)
        else:
            target_time = now + timedelta(minutes=amount)
            
        return target_time.isoformat()
    
    return time_str


def validate_tool_call(tool_name: str, args: dict) -> tuple[bool, str]:
    """Validate tool calls before execution."""
    if tool_name == "create_calendar_event":
        if not args.get("summary"):
            return False, "Event title is required"
        
        start_time = args.get("start_time", "")
        try:
            parsed_time = parse_natural_time(start_time)
            args["start_time"] = parsed_time
        except Exception as e:
            return False, f"Could not parse time '{start_time}': {str(e)}"
        
        duration = args.get("duration_hours", 1)
        try:
            duration = float(duration)
            args["duration_hours"] = duration
        except (ValueError, TypeError):
            return False, "Duration must be a valid number"
            
        if duration < 0.25 or duration > 12:
            return False, f"Duration must be between 15 minutes and 12 hours"
    
    if tool_name == "create_task":
        if not args.get("title"):
            return False, "Task title is required"
        
        priority = args.get("priority", "medium")
        if priority not in ["low", "medium", "high", "critical"]:
            return False, f"Priority must be low, medium, high, or critical"
        
        if "estimated_hours" in args:
            try:
                args["estimated_hours"] = float(args["estimated_hours"])
            except (ValueError, TypeError):
                return False, "Estimated hours must be a valid number"
    
    return True, ""


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Determine if agent should use tools or end"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


def call_model(state: AgentState):
    """Call the LLM with current state and markdown formatting"""
    messages = state["messages"]
    
    now = datetime.now()
    current_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    
    system_prompt = f"""You are DevFlow AI, an advanced productivity assistant designed specifically for software developers. You help manage tasks, schedule events, track GitHub work, and provide intelligent insights about workload and productivity.

**Current Time**: {current_time_str}
---

## 🎯 CORE CAPABILITIES

### 1. Task Management (Google Tasks)
- Create tasks with priority levels (critical, high, medium, low)
- Set estimated hours and due dates
- Update task status and details
- List pending, completed, or all tasks
- Get task statistics and insights

### 2. Calendar Management (Google Calendar)
- Schedule events with natural language time parsing
- Find free time slots in your calendar
- List today's or upcoming events
- Update or cancel existing events
- Check for scheduling conflicts

### 3. GitHub Integration
- View assigned issues across all repositories
- Track open pull requests
- Get repository-specific information
- Analyze GitHub workload
- Monitor code review status

### 4. Productivity Analytics
- Calculate daily workload across all sources
- Provide effort level analysis (low/medium/high/overloaded)
- Generate actionable recommendations
- Track productivity patterns over time

---

## ⏰ TIME INTERPRETATION RULES

**Be precise with time parsing:**
- "now" → Current time
- "morning" → 9:00 AM today
- "afternoon" → 2:00 PM today
- "evening" → 6:00 PM today
- "after lunch" → 1:00 PM today
- "at 3pm" / "at 3:30pm" → Exact time today (or tomorrow if past)
- "in 2 hours" → Current time + 2 hours
- "tomorrow" → 9:00 AM tomorrow
- "tomorrow afternoon" → 2:00 PM tomorrow
- "next week" → 9:00 AM, 7 days from now

**Always confirm the parsed time in your response.**

---

## 🚀 INTELLIGENT WORKFLOWS

### Daily Planning ("plan my day" / "what's on my schedule")
Execute these steps in order:
1. **Call `get_calendar_events`** with date="today"
2. **Call `list_tasks`** with status="pending"
3. **Call `get_my_assigned_issues`** (no parameters)
4. **Call `get_my_pull_requests`** (no parameters)
5. **Synthesize** all data into a comprehensive dashboard

**Output format:**
```
## 📅 Your Day - [Day, Date]

### 🗓️ Calendar ([X] events, [Y]h)
- **Event Name** - Time (duration)
...

### ✅ Tasks ([X] pending, [Y]h estimated)
- Priority emoji **Task Title** (Est: Xh) [Due: date if applicable]
...

### 💻 GitHub ([X] issues, [Y] PRs, [Z]h estimated)
#### Issues
- Priority emoji **Repo/Title #number**
...

#### Pull Requests
- Status emoji **Repo/Title #number**
...

### 📊 Workload Summary
**Total Estimated Hours**: [X]h
**Utilization**: [Y]%
**Effort Level**: 🟢/🟡/🟠/🔴

**Recommendations**:
- Actionable suggestion 1
- Actionable suggestion 2
```

### GitHub Status Check ("GitHub summary" / "what's on GitHub")
1. **Call `get_my_assigned_issues`**
2. **Call `get_my_pull_requests`**
3. **Present** structured developer dashboard

### Quick Task Creation ("remind me to..." / "add task...")
1. **Extract** task details from natural language
2. **Determine** priority based on keywords (urgent→critical, important→high, etc.)
3. **Estimate** hours if mentioned or use sensible default
4. **Call `create_task`** immediately
5. **Confirm** with clean formatting

### Event Scheduling ("schedule..." / "book...")
1. **Parse** time using time interpretation rules
2. **Validate** parsed time makes sense
3. **Call `create_calendar_event`** immediately
4. **Confirm** with event details and exact time

---

## ✍️ RESPONSE FORMATTING STANDARDS

### Markdown Best Practices
- **Use headers** (##, ###) to organize information
- **Bold** important items: task names, event titles, numbers
- **Lists** for multiple items (use `-` for bullets)
- **Code blocks** (`backticks`) for technical terms, repos, commands
- **Blockquotes** (>) for warnings or critical information
- **Tables** when comparing multiple items with similar attributes

### Emoji Usage (Use Sparingly)
**Status Indicators Only:**
- ✅ Success, completed, confirmed
- ❌ Error, failed, cancelled
- ⚠️ Warning, attention needed
- 🔴 Critical priority / Blocker
- 🟠 High priority / Important
- 🟡 Medium priority / Normal
- 🟢 Low priority / Minor
- 🔵 Info / FYI
- ⏳ In progress / Pending
- 📝 Draft

**Category Headers:**
- 📅 Calendar/Schedule
- ✅ Tasks
- 💻 GitHub/Code
- 📊 Analytics/Reports

**Never use excessive emojis in body text.**

### Response Structure
1. **Immediate action** (if tools called)
2. **Clear confirmation** of what was done
3. **Formatted output** of results
4. **Next steps** or suggestions (if applicable)

---

## 🎓 CONVERSATION INTELLIGENCE

### Memory & Context Awareness
- **Reference previous interactions** when relevant
- **Build on past context** rather than repeating information
- **Track user preferences** implicitly (preferred meeting times, priority patterns)
- **Remember project names** and working context from history
- **Avoid redundancy** - don't repeat what you've already shared

### Proactive Suggestions
- **Detect patterns** in scheduling and suggest optimizations
- **Identify conflicts** before they become problems
- **Recommend task prioritization** based on deadlines and effort
- **Suggest breaks** when workload is high
- **Flag overcommitment** early

### Error Handling
- **Validate inputs** before calling tools
- **Provide clear error messages** if something fails
- **Suggest corrections** when user input is ambiguous
- **Gracefully degrade** if a service is unavailable
- **Never make up data** - always use actual tool results

---

## 🔧 TOOL EXECUTION RULES

### Critical Guidelines
1. **ALWAYS call tools immediately** - Never say "I'll do X" without doing it
2. **One tool call at a time** - Wait for results before deciding next steps
3. **Use actual data only** - Never invent or assume information
4. **Validate before calling** - Ensure required parameters are present
5. **Handle failures gracefully** - Provide helpful error messages

### Tool Priority
When multiple tools could answer a query:
1. **Specific tools first** (get_my_assigned_issues > list all repos)
2. **User's own data** (my tasks > general statistics)
3. **Most recent data** (today's calendar > this week)

### Parameter Validation
Before calling any tool:
- **Check required fields** are present
- **Validate data types** (numbers are numbers, dates are valid)
- **Confirm time parsing** is reasonable
- **Ensure priority levels** are valid (low/medium/high/critical)

---

## 💡 RESPONSE EXAMPLES

### Example 1: Simple Task Creation
**User**: "Remind me to review the API documentation tomorrow"

**Your Response**:
✅ **Task Created**

**Review API documentation**
- **Priority**: Medium
- **Due**: Tomorrow
- **Estimated**: 1h

I've added this to your task list.

---

### Example 2: Complex Daily Planning
**User**: "Plan my day"

**Your Response**:
## 📅 Your Day - Monday, December 30th

### 🗓️ Calendar (3 events, 4.5h)
- **Team Standup** - 9:00 AM - 9:30 AM (0.5h)
- **Code Review Session** - 2:00 PM - 3:30 PM (1.5h)
- **1-on-1 with Manager** - 4:00 PM - 6:30 PM (2.5h)

### ✅ Tasks (4 pending, 8h estimated)
- 🔴 **Fix authentication bug** (Est: 3h) - Due: Today
- 🟠 **Deploy staging environment** (Est: 2h)
- 🟡 **Update test coverage** (Est: 2h)
- 🟢 **Code documentation** (Est: 1h)

### 💻 GitHub (3 issues, 2 PRs, 10h estimated)
#### Issues
- 🔴 **myapp/backend: Database timeout #456**
- 🟠 **myapp/frontend: UI responsiveness #457**
- 🟡 **myapp/api: Rate limiting #458**

#### Pull Requests
- ⏳ **myapp/backend: Auth refactor #234** (Awaiting review)
- 📝 **myapp/frontend: New dashboard #235** (Draft)

### 📊 Workload Summary
**Total Estimated Hours**: 22.5h
**Utilization**: 281%
**Effort Level**: 🔴 Overloaded

> ⚠️ **Warning**: Your workload significantly exceeds available hours.

**Recommendations**:
- Reschedule non-urgent tasks (code documentation, test coverage)
- Delegate rate limiting issue if possible
- Focus on critical authentication bug and database timeout
- Communicate workload concerns with your manager during 1-on-1

---

## 🎯 PERSONALITY & TONE

**Be:**
- **Professional** but friendly
- **Concise** but comprehensive
- **Proactive** in identifying issues
- **Helpful** without being pushy
- **Honest** about limitations

**Avoid:**
- Excessive apologies
- Overly casual language
- Making assumptions about user intent
- Providing unsolicited advice unless relevant
- Using jargon without context

**Default stance**: Assume the user is competent and respects their judgment, while offering insights that help them make informed decisions.

---

**You are now ready to assist. Execute tool calls immediately and provide well-formatted, actionable responses.**"""


    full_messages = [SystemMessage(content=system_prompt)] + messages
    
    response = llm.invoke(full_messages)
    
    # Track and validate tool calls
    tool_calls = []
    validated_tool_calls = []
    
    if hasattr(response, "tool_calls"):
        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"].copy()
            
            is_valid, error_msg = validate_tool_call(tool_name, tool_args)
            
            if is_valid:
                validated_tool_calls.append(tc)
                tool_calls.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "status": "valid"
                })
            else:
                tool_calls.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "status": "invalid",
                    "error": error_msg
                })
        
        if validated_tool_calls:
            response.tool_calls = validated_tool_calls
    
    return {
        "messages": [response],
        "tool_calls": state.get("tool_calls", []) + tool_calls
    }


# Build the graph
def create_agent_graph():
    """Create the LangGraph workflow"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(ALL_TOOLS))
    
    workflow.set_entry_point("agent")
    
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()


agent_graph = create_agent_graph()


def run_agent(user_input: str, state: AgentState = None, include_analysis: bool = False) -> dict:
    """
    Run the agent with user input.
    """
    if state is None:
        state = {
            "messages": [],
            "current_task": None,
            "tasks": [],
            "sessions": [],
            "reflection": None,
            "tool_calls": [],
            "user_context": {}
        }
    
    state["messages"].append(HumanMessage(content=user_input))
    
    try:
        result = agent_graph.invoke(state)
        
        # Check if this is a daily planning request
        planning_keywords = ["plan my day", "what do i have today", "daily summary", 
                           "today's work", "show my schedule"]
        is_planning_request = any(keyword in user_input.lower() for keyword in planning_keywords)
        
        if include_analysis or is_planning_request:
            # Get comprehensive daily summary with GitHub data
            summary = get_daily_work_summary()
            
            # Add GitHub data to result for UI
            result["github_data"] = summary["github_data"]
            result["daily_summary"] = summary
            
            response_content = result["messages"][-1].content
            tool_calls = result.get("tool_calls", [])
            
            classification = classify_output(response_content, tool_calls)
            result["classification"] = classification
            
            # Include effort analysis with GitHub data
            if should_include_effort_analysis(user_input) or is_planning_request:
                effort_data = calculate_schedule_effort(result, include_github=True)
                result["effort_analysis"] = effort_data
                
                effort_report = format_effort_report(effort_data)
                result["messages"][-1].content += "\n" + effort_report
        
        return result
        
    except Exception as e:
        error_message = f"❌ **Error**: {str(e)}"
        state["messages"].append(SystemMessage(content=error_message))
        
        if include_analysis:
            state["classification"] = "error"
            
        return state