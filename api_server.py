"""
FastAPI Backend for DevFlow AI Web App
Connects HTML/CSS/JS frontend to the LangGraph agent
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, List
import os, sys, requests
from pathlib import Path
from src.tools.github_tools import (
    list_repo_issues, 
    list_pull_requests, 
    get_my_assigned_issues, 
    get_my_pull_requests
)
# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.agent.graph import run_agent, calculate_schedule_effort
from src.tools.google_tasks import get_task_statistics, list_tasks
from src.tools.google_calendar import get_calendar_events
from src.utils.observability import track_agent_call

# ────────────────────────────────────────────── #
# 🔥 Response classifier (NEW — integrated here)
# ────────────────────────────────────────────── #
def classify_response(text: str):
    t = text.lower()

    if any(w in t for w in ["error", "failed", "unable", "exception"]):
        return "error"
    if any(w in t for w in ["warning", "caution", "be careful"]):
        return "warning"
    if any(w in t for w in ["done", "created", "added", "scheduled", "success", "completed"]):
        return "success"
    return "info"   # default fallback


app = FastAPI(title="DevFlow AI API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    state: Optional[Dict] = None

class ChatResponse(BaseModel):
    response: str
    classification: str
    state: Dict

class StatusResponse(BaseModel):
    ollama: bool
    google: bool
    github: bool
    model: str


# ────────────────────────────────────────────── #
# System Health Checks
# ────────────────────────────────────────────── #
def check_ollama():
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        response = requests.get(f"{base_url}/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False
    
def check_github_auth():
    try:
        from github import Github
        gh = Github(os.getenv("GITHUB_TOKEN"))
        gh.get_user().login
        return True
    except:
        return False

def check_google_auth():
    try:
        from src.utils.google_auth import get_google_credentials
        creds = get_google_credentials()
        return creds is not None and creds.valid
    except:
        return False


# ────────────────────────────────────────────── #
# 🔥 NEW: GitHub parsing functions
# ────────────────────────────────────────────── #
def parse_github_issues(issues_text: str) -> List[Dict]:
    """Parse GitHub issues from markdown text"""
    issues = []
    current_repo = None
    lines = issues_text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detect repo header
        if line.startswith('###') and not line.startswith('####'):
            current_repo = line.replace('###', '').strip()
            i += 1
            continue
        
        # Detect issue line (starts with emoji)
        if line and (line.startswith('🔴') or line.startswith('🟠') or 
                     line.startswith('🟡') or line.startswith('🟢') or 
                     line.startswith('🔵')):
            
            priority_map = {
                '🔴': 'critical',
                '🟠': 'high',
                '🟡': 'medium',
                '🟢': 'low',
                '🔵': 'low'
            }
            
            priority = priority_map.get(line[0], 'medium')
            
            # Extract issue number and title
            if '**#' in line and '**' in line:
                parts = line.split('**')
                if len(parts) >= 3:
                    number_part = parts[1].replace('#', '').strip()
                    title = parts[3].strip() if len(parts) > 3 else parts[2].strip()
                    
                    issue = {
                        'repo': current_repo or 'Unknown',
                        'number': number_part,
                        'title': title,
                        'priority': priority,
                        'created': None,
                        'assignee': None,
                        'labels': [],
                        'url': None,
                        'estimate': 2  # Default estimate
                    }
                    
                    # Parse metadata from next few lines
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith('-'):
                        meta_line = lines[j].strip()
                        
                        if '**Created**:' in meta_line:
                            issue['created'] = meta_line.split(':')[1].strip()
                        elif '**Assignee**:' in meta_line:
                            issue['assignee'] = meta_line.split(':')[1].strip()
                        elif '**Labels**:' in meta_line:
                            labels_str = meta_line.split(':')[1].strip()
                            issue['labels'] = [l.strip('`').strip() for l in labels_str.split(',')]
                        elif '**Link**:' in meta_line:
                            issue['url'] = meta_line.split('Link**:')[1].strip()
                        
                        j += 1
                    
                    issues.append(issue)
                    i = j
                    continue
        
        i += 1
    
    return issues


def parse_github_prs(prs_text: str) -> List[Dict]:
    """Parse GitHub PRs from markdown text"""
    prs = []
    current_repo = None
    lines = prs_text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detect repo header
        if line.startswith('###') and not line.startswith('####'):
            current_repo = line.replace('###', '').strip()
            i += 1
            continue
        
        # Detect PR line (starts with status emoji)
        if line and (line.startswith('⏳') or line.startswith('✅') or line.startswith('📝')):
            
            status_map = {
                '⏳': 'open',
                '✅': 'merged',
                '📝': 'draft'
            }
            
            status = status_map.get(line[0], 'open')
            
            # Extract PR number and title
            if '**#' in line and '**' in line:
                parts = line.split('**')
                if len(parts) >= 3:
                    number_part = parts[1].replace('#', '').strip()
                    title = parts[3].strip() if len(parts) > 3 else parts[2].strip()
                    
                    pr = {
                        'repo': current_repo or 'Unknown',
                        'number': number_part,
                        'title': title,
                        'status': status,
                        'priority': 'medium',
                        'created': None,
                        'assignee': None,
                        'labels': [],
                        'url': None,
                        'estimate': 3  # Default estimate for PRs
                    }
                    
                    # Parse metadata from next few lines
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith('-'):
                        meta_line = lines[j].strip()
                        
                        if '**Created**:' in meta_line:
                            pr['created'] = meta_line.split(':')[1].strip()
                        elif '**Author**:' in meta_line:
                            pr['assignee'] = meta_line.split(':')[1].strip()
                        elif '**Link**:' in meta_line:
                            pr['url'] = meta_line.split('Link**:')[1].strip()
                        
                        j += 1
                    
                    prs.append(pr)
                    i = j
                    continue
        
        i += 1
    
    return prs


# ────────────────────────────────────────────── #
# API ROUTES
# ────────────────────────────────────────────── #

@app.get("/")
async def root():
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(open(html_path).read())
    return {"message": "DevFlow AI API running. Host UI separately."}


@app.get("/status")
async def get_status() -> StatusResponse:
    return StatusResponse(
        ollama=check_ollama(),
        google=check_google_auth(),
        github=check_github_auth(),
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    )


# ────────────────────────────────────────────── #
# 🔥 MAIN CHAT ENDPOINT — classifier integrated
# ────────────────────────────────────────────── #
@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = run_agent(request.message, request.state, include_analysis=True)

        response_content = result["messages"][-1].content
        classification = classify_response(response_content)   # ← NEW

        try:
            track_agent_call(request.message, response_content, result.get("tool_calls", []))
        except:
            pass

        return ChatResponse(
            response=response_content,
            classification=classification,
            state=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
async def get_tasks():
    try:
        pending_tasks = list_tasks.invoke({"status": "pending"})
        stats = get_task_statistics.invoke({})

        total = completed = pending = 0
        for line in stats.split("\n"):
            if "Total Tasks" in line: total = int(line.split(":")[1].strip())
            if "Completed" in line: completed = int(line.split(":")[1].strip())
            if "Pending" in line: pending = int(line.split(":")[1].strip())

        return {"content": pending_tasks, "total": total, "completed": completed, "pending": pending}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/calendar")
async def get_calendar(date: str = "today"):
    try:
        events = get_calendar_events.invoke({"date": date})
        return {"content": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workload")
async def get_workload():
    try:
        state = {"messages": [], "tasks": [], "sessions": [], "tool_calls": [], "user_context": {}}
        return calculate_schedule_effort(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/github")
async def get_github_summary(repo: str = None):
    """
    🔥 Enhanced GitHub endpoint with parsed data
    If repo is provided, gets issues/PRs for that specific repo
    Otherwise, gets all assigned issues and PRs for the authenticated user
    """
    try:
        if repo:
            # Get specific repo data
            issues_text = list_repo_issues.invoke({"repo_name": repo})
            prs_text = list_pull_requests.invoke({"repo_name": repo})
        else:
            # Get user's assigned issues and PRs across all repos
            issues_text = get_my_assigned_issues.invoke({})
            prs_text = get_my_pull_requests.invoke({})
        
        # Parse the markdown text into structured data
        issues = parse_github_issues(issues_text)
        prs = parse_github_prs(prs_text)
        
        # Calculate estimated hours (2h per issue, 3h per PR)
        estimated_hours = (len(issues) * 2) + (len(prs) * 3)
        
        return {
            "repo": repo or "All Repositories",
            "issues": issues,
            "prs": prs,
            "estimatedHours": estimated_hours,
            "issues_summary": issues_text,  # Keep raw text for backward compatibility
            "prs_summary": prs_text
        }
    except Exception as e:
        print(f"GitHub endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard")
async def get_dashboard():
    """
    🔥 Dashboard endpoint with comprehensive metrics
    Aggregates data from Tasks, Calendar, and GitHub
    """
    try:
        # Get tasks data
        try:
            tasks_result = list_tasks.invoke({"status": "pending"})
            tasks_today = tasks_result.count('\n') if tasks_result else 0
        except Exception as e:
            print(f"Tasks error: {e}")
            tasks_today = 0
        
        # Get calendar data
        try:
            calendar_result = get_calendar_events.invoke({"date": "today"})
            meetings = calendar_result.count('🕐') if calendar_result else 0
        except Exception as e:
            print(f"Calendar error: {e}")
            meetings = 0
        
        # Get GitHub data
        try:
            issues_result = get_my_assigned_issues.invoke({})
            prs_result = get_my_pull_requests.invoke({})
            
            github_issues = issues_result.count('🔴') + issues_result.count('🟠') + \
                           issues_result.count('🟡') + issues_result.count('🟢')
            github_prs = prs_result.count('⏳') + prs_result.count('📝')
            github_items = github_issues + github_prs
        except Exception as e:
            print(f"GitHub error: {e}")
            github_issues = 0
            github_prs = 0
            github_items = 0
        
        # Calculate productivity score (simple algorithm)
        total_items = tasks_today + github_items
        if total_items == 0:
            productivity_score = "100%"
        elif total_items <= 5:
            productivity_score = "85%"
        elif total_items <= 10:
            productivity_score = "70%"
        elif total_items <= 15:
            productivity_score = "55%"
        else:
            productivity_score = "40%"
        
        # Workload analysis
        total_hours = (tasks_today * 1.5) + (meetings * 1) + (github_items * 2)
        
        if total_hours < 4:
            workload_analysis = "🟢 Light Workload\n\n"
            workload_analysis += f"Total estimated hours: {total_hours:.1f}h\n"
            workload_analysis += "You have capacity for additional tasks today.\n\n"
            workload_analysis += "Recommendations:\n"
            workload_analysis += "- Good time for deep work\n"
            workload_analysis += "- Consider tackling complex problems\n"
            workload_analysis += "- Review backlog items"
        elif total_hours < 8:
            workload_analysis = "🟡 Balanced Workload\n\n"
            workload_analysis += f"Total estimated hours: {total_hours:.1f}h\n"
            workload_analysis += "Your schedule is well-balanced for today.\n\n"
            workload_analysis += "Recommendations:\n"
            workload_analysis += "- Maintain steady pace\n"
            workload_analysis += "- Take regular breaks\n"
            workload_analysis += "- Stay focused on priorities"
        elif total_hours < 12:
            workload_analysis = "🟠 Heavy Workload\n\n"
            workload_analysis += f"Total estimated hours: {total_hours:.1f}h\n"
            workload_analysis += "You have a busy day ahead.\n\n"
            workload_analysis += "Recommendations:\n"
            workload_analysis += "- Prioritize high-impact tasks\n"
            workload_analysis += "- Defer low-priority items\n"
            workload_analysis += "- Schedule breaks every 90 minutes"
        else:
            workload_analysis = "🔴 Overloaded Schedule\n\n"
            workload_analysis += f"Total estimated hours: {total_hours:.1f}h\n"
            workload_analysis += "⚠️ Your workload exceeds available hours.\n\n"
            workload_analysis += "Recommendations:\n"
            workload_analysis += "- Reschedule non-urgent tasks\n"
            workload_analysis += "- Consider delegating work\n"
            workload_analysis += "- Focus only on critical items\n"
            workload_analysis += "- Communicate workload to team"
        
        workload_analysis += f"\n\nBreakdown:\n"
        workload_analysis += f"- Tasks: {tasks_today} ({tasks_today * 1.5:.1f}h)\n"
        workload_analysis += f"- Meetings: {meetings} ({meetings * 1:.1f}h)\n"
        workload_analysis += f"- GitHub: {github_items} ({github_items * 2:.1f}h)\n"
        
        return {
            "metrics": {
                "tasksToday": tasks_today,
                "meetings": meetings,
                "githubItems": github_items,
                "productivityScore": productivity_score
            },
            "workloadAnalysis": workload_analysis
        }
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    
@app.get("/health")
async def health_check():
    return {"status": "healthy", "ollama": check_ollama(), "google": check_google_auth()}


# ────────────────────────────────────────────── #
# Run server
# ────────────────────────────────────────────── #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)