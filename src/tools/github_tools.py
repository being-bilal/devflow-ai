"""
GitHub Tools for DevFlow AI
Integrates GitHub API for repository, issue, and PR management.
"""
from langchain_core.tools import tool
from typing import Optional
from github import Github
import os
from dotenv import load_dotenv

load_dotenv()

def get_gh_client():
    """Lazy initializer for GitHub client to ensure env vars are loaded."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not found in environment variables.")
    return Github(token)

@tool
def get_my_assigned_issues() -> str:
    """
    Get all open issues assigned to the authenticated user across all repositories.
    Use this for questions like 'What are my tasks?' or 'What is on my plate?'.
    """
    try:
        gh = get_gh_client()
        user = gh.get_user()
        query = f"assignee:{user.login} is:issue is:open"
        issues = gh.search_issues(query)
        
        results = []
        for i, issue in enumerate(issues):
            if i >= 15: break
            repo_name = issue.repository.full_name if issue.repository else "Unknown Repo"
            results.append(f"🔴 **#{issue.number}** in {repo_name}: {issue.title}\n   - [View Issue]({issue.html_url})")
            
        if not results:
            return "✨ You have no open assigned issues on GitHub."
            
        return "## 📌 Your Assigned Issues\n\n" + "\n".join(results)
    except Exception as e:
        return f"❌ **GitHub Error**: {str(e)}"

@tool
def get_my_pull_requests() -> str:
    """
    Get all open pull requests created by the authenticated user.
    Use this to check the status of your code reviews.
    """
    try:
        gh = get_gh_client()
        user = gh.get_user()
        query = f"author:{user.login} is:pr is:open"
        prs = gh.search_issues(query)
        
        results = []
        for i, pr in enumerate(prs):
            if i >= 15: break
            repo_name = pr.repository.full_name if pr.repository else "Unknown Repo"
            results.append(f"⏳ **#{pr.number}** in {repo_name}: {pr.title}\n   - [View PR]({pr.html_url})")
            
        if not results:
            return "✨ You have no open pull requests."
            
        return "## 🔀 Your Pull Requests\n\n" + "\n".join(results)
    except Exception as e:
        return f"❌ **GitHub Error**: {str(e)}"

@tool
def list_repo_issues(repo_name: str, state: str = "open") -> str:
    """
    List issues for a specific repository. 
    Args:
        repo_name: Repository name in format 'owner/repo'
        state: 'open', 'closed', or 'all'
    """
    try:
        gh = get_gh_client()
        repo = gh.get_repo(repo_name)
        issues = repo.get_issues(state=state)
        
        results = []
        count = 0
        for issue in issues:
            if count >= 15: break
            if not issue.pull_request:  # Filter out PRs
                results.append(f"- **#{issue.number}**: {issue.title} ([Link]({issue.html_url}))")
                count += 1
        
        if not results:
            return f"No {state} issues found in {repo_name}."
            
        return f"### 🐛 Issues in {repo_name}\n\n" + "\n".join(results)
    except Exception as e:
        return f"❌ **Error**: {str(e)}"

@tool
def list_pull_requests(repo_name: str, state: str = "open") -> str:
    """
    List pull requests for a specific repository.
    Args:
        repo_name: Repository name in format 'owner/repo'
        state: 'open', 'closed', or 'all'
    """
    try:
        gh = get_gh_client()
        repo = gh.get_repo(repo_name)
        pulls = repo.get_pulls(state=state)
        
        results = []
        for i, pr in enumerate(pulls):
            if i >= 15: break
            results.append(f"- **#{pr.number}**: {pr.title} ([Link]({pr.html_url}))")
            
        if not results:
            return f"No {state} PRs found in {repo_name}."
            
        return f"### 🔀 Pull Requests in {repo_name}\n\n" + "\n".join(results)
    except Exception as e:
        return f"❌ **Error**: {str(e)}"

# Export list for LangGraph
GITHUB_TOOLS = [
    get_my_assigned_issues, 
    get_my_pull_requests, 
    list_repo_issues, 
    list_pull_requests
]