"""
Google Calendar API Tools
Create, read, and manage calendar events
"""
from datetime import datetime, timedelta
from typing import Optional, Literal
from langchain_core.tools import tool
import pytz
from dateutil import parser

from src.utils.google_auth import get_calendar_service

# Timezone
LOCAL_TZ = pytz.timezone('Asia/Kolkata')  # Change to your timezone


@tool
def create_calendar_event(
    summary: str,
    start_time: str,
    duration_hours: float,
    description: str = "",
    event_type: Literal["coding", "meeting", "break", "learning", "review"] = "coding"
) -> str:
    """
    Create a new event in Google Calendar.
    
    Args:
        summary: Event title/summary
        start_time: Start time (ISO format or natural language like "2pm", "tomorrow 10am")
        duration_hours: Event duration in hours
        description: Event description
        event_type: Type of event (coding, meeting, break, learning, review)
    
    Returns:
        Success message with event link
    """
    try:
        service = get_calendar_service()
        
        # Parse start time
        start_dt = parse_time_natural(start_time)
        end_dt = start_dt + timedelta(hours=duration_hours)
        
        # Emoji mapping
        emoji_map = {
            "coding": "💻",
            "meeting": "👥",
            "break": "☕",
            "learning": "📚",
            "review": "👀"
        }
        
        # Create event
        event = {
            'summary': f"{emoji_map.get(event_type, '📌')} {summary}",
            'description': description or f"{event_type.capitalize()} session",
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': str(LOCAL_TZ),
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': str(LOCAL_TZ),
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10},
                ],
            },
            'colorId': '9',  # Blue for coding/work
        }
        
        result = service.events().insert(calendarId='primary', body=event).execute()
        
        return (
            f"✅ Calendar event created!\n\n"
            f"📅 {summary}\n"
            f"🕐 {start_dt.strftime('%b %d, %Y at %I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
            f"⏱️ Duration: {duration_hours}h\n"
            f"🔗 Link: {result.get('htmlLink')}"
        )
    
    except Exception as e:
        return f"❌ Error creating calendar event: {str(e)}"


@tool
def get_calendar_events(
    date: str = "today",
    max_results: int = 10
) -> str:
    """
    Get calendar events for a specific date.
    
    Args:
        date: Date to fetch (today, tomorrow, or YYYY-MM-DD)
        max_results: Maximum number of events to return
    
    Returns:
        List of calendar events
    """
    try:
        service = get_calendar_service()
        
        # Parse date
        if date.lower() == "today":
            target_date = datetime.now(LOCAL_TZ)
        elif date.lower() == "tomorrow":
            target_date = datetime.now(LOCAL_TZ) + timedelta(days=1)
        else:
            target_date = parser.parse(date).replace(tzinfo=LOCAL_TZ)
        
        # Set time bounds (start and end of day)
        time_min = target_date.replace(hour=0, minute=0, second=0).isoformat()
        time_max = target_date.replace(hour=23, minute=59, second=59).isoformat()
        
        # Fetch events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📅 No events scheduled for {date}"
        
        result = f"📅 Schedule for {target_date.strftime('%b %d, %Y')}:\n\n"
        
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            start_dt = parser.parse(start)
            
            end = event['end'].get('dateTime', event['end'].get('date'))
            end_dt = parser.parse(end)
            
            duration = (end_dt - start_dt).total_seconds() / 3600
            
            result += f"🕐 {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}\n"
            result += f"   {event.get('summary', 'Untitled')} ({duration:.1f}h)\n"
            
            if event.get('description'):
                result += f"   📝 {event['description'][:50]}...\n"
            
            result += "\n"
        
        return result.strip()
    
    except Exception as e:
        return f"❌ Error fetching calendar events: {str(e)}"


@tool
def find_free_time_slots(
    date: str = "today",
    duration_hours: float = 2.0,
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> str:
    """
    Find available free time slots in the calendar.
    
    Args:
        date: Date to check (today, tomorrow, or YYYY-MM-DD)
        duration_hours: Minimum slot duration needed
        work_hours_start: Start of work day (hour)
        work_hours_end: End of work day (hour)
    
    Returns:
        List of available time slots
    """
    try:
        service = get_calendar_service()
        
        # Parse date
        if date.lower() == "today":
            target_date = datetime.now(LOCAL_TZ)
        elif date.lower() == "tomorrow":
            target_date = datetime.now(LOCAL_TZ) + timedelta(days=1)
        else:
            target_date = parser.parse(date).replace(tzinfo=LOCAL_TZ)
        
        # Work hours bounds
        work_start = target_date.replace(hour=work_hours_start, minute=0, second=0)
        work_end = target_date.replace(hour=work_hours_end, minute=0, second=0)
        
        # Fetch busy times
        body = {
            "timeMin": work_start.isoformat(),
            "timeMax": work_end.isoformat(),
            "items": [{"id": "primary"}]
        }
        
        freebusy = service.freebusy().query(body=body).execute()
        busy_times = freebusy['calendars']['primary'].get('busy', [])
        
        # Find free slots
        free_slots = []
        current_time = work_start
        
        for busy in busy_times:
            busy_start = parser.parse(busy['start'])
            
            # Check if there's a gap
            gap_duration = (busy_start - current_time).total_seconds() / 3600
            
            if gap_duration >= duration_hours:
                free_slots.append({
                    'start': current_time,
                    'end': busy_start,
                    'duration': gap_duration
                })
            
            current_time = parser.parse(busy['end'])
        
        # Check remaining time until end of work day
        final_gap = (work_end - current_time).total_seconds() / 3600
        if final_gap >= duration_hours:
            free_slots.append({
                'start': current_time,
                'end': work_end,
                'duration': final_gap
            })
        
        if not free_slots:
            return f"❌ No free slots of {duration_hours}h found on {date}"
        
        result = f"✨ Available time slots for {date} ({duration_hours}h+ needed):\n\n"
        
        for i, slot in enumerate(free_slots, 1):
            result += f"{i}. {slot['start'].strftime('%I:%M %p')} - {slot['end'].strftime('%I:%M %p')}"
            result += f" ({slot['duration']:.1f}h available)\n"
        
        result += f"\n💡 Use: schedule_coding_session with one of these times"
        
        return result
    
    except Exception as e:
        return f"❌ Error finding free slots: {str(e)}"


@tool
def delete_calendar_event(event_summary: str) -> str:
    """
    Delete a calendar event by its summary/title.
    
    Args:
        event_summary: Title of the event to delete
    
    Returns:
        Success or error message
    """
    try:
        service = get_calendar_service()
        
        # Search for event
        now = datetime.now(LOCAL_TZ).isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            q=event_summary,
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"❌ No event found with title: {event_summary}"
        
        # Delete first matching event
        service.events().delete(
            calendarId='primary',
            eventId=events[0]['id']
        ).execute()
        
        return f"✅ Event deleted: {event_summary}"
    
    except Exception as e:
        return f"❌ Error deleting event: {str(e)}"


def parse_time_natural(time_str: str) -> datetime:
    """
    Parse natural language time expressions.
    
    Examples:
        "2pm" -> today at 2 PM
        "tomorrow 10am" -> tomorrow at 10 AM
        "14:00" -> today at 2 PM
        "after lunch" -> today at 1 PM
    """
    now = datetime.now(LOCAL_TZ)
    time_str = time_str.lower()
    
    # Handle "after lunch"
    if "after lunch" in time_str or "post lunch" in time_str:
        return now.replace(hour=13, minute=0, second=0, microsecond=0)
    
    # Handle "tomorrow"
    if "tomorrow" in time_str:
        tomorrow = now + timedelta(days=1)
        # Extract time if present
        if "am" in time_str or "pm" in time_str:
            try:
                time_part = time_str.split("tomorrow")[1].strip()
                parsed = parser.parse(time_part)
                return tomorrow.replace(
                    hour=parsed.hour,
                    minute=parsed.minute,
                    second=0,
                    microsecond=0
                )
            except:
                pass
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # Try parsing as time
    try:
        parsed = parser.parse(time_str)
        return now.replace(
            hour=parsed.hour,
            minute=parsed.minute,
            second=0,
            microsecond=0
        )
    except:
        pass
    
    # Default: 2 hours from now
    return now + timedelta(hours=2)


# Export tools
CALENDAR_TOOLS = [
    create_calendar_event,
    get_calendar_events,
    find_free_time_slots,
    delete_calendar_event
]