"""
Google Calendar Service
Creates calendar invite links (no API needed — uses Google Calendar URL scheme)
For full API integration, use google-calendar-api with service account
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote

logger = logging.getLogger(__name__)


def create_calendar_link(
    title: str,
    description: str,
    meeting_date: str,
    meeting_time: str,
    duration_hours: int = 1,
    location: str = ""
) -> str:
    """
    Create a Google Calendar event link (no API key needed).
    Anyone can click this to add event to their Google Calendar.

    Args:
        meeting_date: Format "25 March 2026" or "2026-03-25"
        meeting_time: Format "3:00 PM" or "15:00"
    """
    try:
        # Parse date and time
        for fmt in ["%d %B %Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                date_obj = datetime.strptime(meeting_date.strip(), fmt)
                break
            except ValueError:
                continue
        else:
            # Default to tomorrow if parsing fails
            date_obj = datetime.now() + timedelta(days=1)

        # Parse time
        for fmt in ["%I:%M %p", "%H:%M", "%I %p"]:
            try:
                time_obj = datetime.strptime(meeting_time.strip().upper(), fmt)
                break
            except ValueError:
                continue
        else:
            time_obj = datetime.strptime("10:00 AM", "%I:%M %p")

        # Combine date and time
        start_dt = date_obj.replace(
            hour=time_obj.hour,
            minute=time_obj.minute,
            second=0
        )
        end_dt = start_dt + timedelta(hours=duration_hours)

        # Format for Google Calendar URL
        start_str = start_dt.strftime("%Y%m%dT%H%M%S")
        end_str = end_dt.strftime("%Y%m%dT%H%M%S")

        # Build URL
        base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
        params = (
            f"&text={quote(title)}"
            f"&dates={start_str}/{end_str}"
            f"&details={quote(description)}"
            f"&location={quote(location)}"
        )

        calendar_link = base_url + params
        logger.info(f"[CALENDAR] ✅ Calendar link created for {start_str}")
        return calendar_link

    except Exception as e:
        logger.error(f"[CALENDAR] ❌ Failed to create calendar link: {e}")
        return ""


def format_meeting_calendar_link(
    client_name: str,
    property_name: str,
    property_type: str,
    city: str,
    meeting_date: str,
    meeting_time: str
) -> str:
    """Helper to create a formatted calendar link for property meetings"""

    title = f"Property Meeting — {client_name} | {property_name}"
    description = (
        f"Meeting with {client_name} regarding {property_type} in {city}.\n"
        f"Property: {property_name}\n"
        f"Scheduled via WhatsApp Property Bot."
    )
    location = city

    return create_calendar_link(
        title=title,
        description=description,
        meeting_date=meeting_date,
        meeting_time=meeting_time,
        location=location
    )