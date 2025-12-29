"""
Google OAuth Authentication Helper
Handles authentication for Google Calendar and Tasks APIs
"""
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes for Google APIs
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

def get_google_credentials():
    """
    Get or refresh Google API credentials.
    
    Returns:
        Credentials object for Google APIs
    """
    creds = None
    token_path = 'token.json'
    credentials_path = 'credentials.json'
    
    # Check if we have existing credentials
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # If credentials are invalid or don't exist, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh expired credentials
            creds.refresh(Request())
        else:
            # Get new credentials
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"'{credentials_path}' not found. "
                    "Download it from Google Cloud Console:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a project (or select existing)\n"
                    "3. Enable Calendar API and Tasks API\n"
                    "4. Create OAuth 2.0 credentials (Desktop app)\n"
                    "5. Download as 'credentials.json'"
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return creds


def get_calendar_service():
    """
    Get Google Calendar API service.
    
    Returns:
        Google Calendar service object
    """
    creds = get_google_credentials()
    return build('calendar', 'v3', credentials=creds)


def get_tasks_service():
    """
    Get Google Tasks API service.
    
    Returns:
        Google Tasks service object
    """
    creds = get_google_credentials()
    return build('tasks', 'v1', credentials=creds)


def test_authentication():
    """
    Test if authentication is working.
    
    Returns:
        Boolean indicating success
    """
    try:
        calendar_service = get_calendar_service()
        tasks_service = get_tasks_service()
        
        # Test Calendar API
        calendar_service.calendarList().list().execute()
        
        # Test Tasks API
        tasks_service.tasklists().list().execute()
        
        print("✅ Google API authentication successful!")
        return True
    
    except Exception as e:
        print(f"❌ Authentication failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Run authentication test
    test_authentication()