"""
GitHub Authentication Helper
Used for GitHub Issues, Repos, Pull Requests API
"""

import os
from github import Github

def get_github_client():
    """
    Returns an authenticated GitHub client using token.
    
    Prerequisite:
        Set GITHUB_TOKEN in your environment or create token.txt file.
        Get token from: https://github.com/settings/tokens?type=beta
        Enable scopes: repo, read:user, workflow
    """

    token = os.getenv("GITHUB_TOKEN")

    # Fallback if user wants file based auth like Google token.json
    if not token and os.path.exists("github_token.txt"):
        with open("github_token.txt", "r") as f:
            token = f.read().strip()

    if not token:
        raise Exception(
            "❌ GitHub Token not found.\n"
            "Create one at https://github.com/settings/tokens?type=beta\n"
            "and either:\n"
            "1. Add to environment: export GITHUB_TOKEN=your_token\n"
            "OR\n"
            "2. Save to 'github_token.txt'"
        )

    return Github(token)


def test_github_auth():
    """
    Test GitHub connection
    """

    try:
        gh = get_github_client()
        user = gh.get_user()
        print(f"✅ GitHub Auth successful! Logged in as {user.login}")
        return True

    except Exception as e:
        print(f"❌ GitHub Authentication Failed: {e}")
        return False


if __name__ == "__main__":
    test_github_auth()
