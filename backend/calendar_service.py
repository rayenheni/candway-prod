"""
Calendar Integration Service for Candway ATS
Supports Google Calendar, Outlook Calendar, and ICS file generation
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional

from icalendar import Calendar, vText
from icalendar import Event as ICalEvent

logger = logging.getLogger(__name__)


class CalendarService:
    """Unified calendar service for all calendar integrations"""

    @staticmethod
    def generate_ics_file(
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        organizer_email: Optional[str] = None,
        meeting_link: Optional[str] = None,
    ) -> str:
        """
        Generate ICS file content for calendar event

        Args:
            title: Event title
            description: Event description
            start_time: Event start time
            end_time: Event end time
            location: Event location (optional)
            attendees: List of attendee emails (optional)
            organizer_email: Organizer email (optional)
            meeting_link: Online meeting link (optional)

        Returns:
            ICS file content as string
        """
        try:
            cal = Calendar()
            cal.add("prodid", "-//Candway ATS//Interview Scheduler//EN")
            cal.add("version", "2.0")
            cal.add("method", "REQUEST")

            event = ICalEvent()
            event.add("summary", title)
            event.add("description", description)
            event.add("dtstart", start_time)
            event.add("dtend", end_time)
            event.add("dtstamp", datetime.now(UTC))

            # Add location
            if location:
                event.add("location", vText(location))

            # Add meeting link to description if provided
            if meeting_link:
                enhanced_description = f"{description}\n\nJoin Meeting: {meeting_link}"
                event["description"] = vText(enhanced_description)

            # Add organizer
            if organizer_email:
                event.add("organizer", f"mailto:{organizer_email}")

            # Add attendees
            if attendees:
                for attendee in attendees:
                    event.add(
                        "attendee",
                        f"mailto:{attendee}",
                        parameters={"ROLE": "REQ-PARTICIPANT", "RSVP": "TRUE"},
                    )

            # Add alarm (15 minutes before)
            from icalendar import Alarm

            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", f"Reminder: {title}")
            alarm.add("trigger", timedelta(minutes=-15))
            event.add_component(alarm)

            cal.add_component(event)

            return cal.to_ical().decode("utf-8")

        except Exception as e:
            logger.error(f"Failed to generate ICS file: {e}")
            raise

    @staticmethod
    def create_google_calendar_link(
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> str:
        """
        Generate Google Calendar "Add to Calendar" link

        Args:
            title: Event title
            description: Event description
            start_time: Event start time
            end_time: Event end time
            location: Event location (optional)
            attendees: List of attendee emails (optional)

        Returns:
            Google Calendar URL
        """
        try:
            # Format dates for Google Calendar (YYYYMMDDTHHmmssZ)
            start_str = start_time.strftime("%Y%m%dT%H%M%SZ")
            end_str = end_time.strftime("%Y%m%dT%H%M%SZ")

            # Build URL
            base_url = "https://calendar.google.com/calendar/render?action=TEMPLATE"
            params = [
                f"text={title}",
                f"dates={start_str}/{end_str}",
                f"details={description}",
            ]

            if location:
                params.append(f"location={location}")

            if attendees:
                params.append(f"add={','.join(attendees)}")

            url = base_url + "&" + "&".join(params)

            # URL encode
            from urllib.parse import quote

            return quote(url, safe=":/?&=")

        except Exception as e:
            logger.error(f"Failed to create Google Calendar link: {e}")
            return ""

    @staticmethod
    def create_outlook_calendar_link(
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        location: Optional[str] = None,
    ) -> str:
        """
        Generate Outlook Calendar "Add to Calendar" link

        Args:
            title: Event title
            description: Event description
            start_time: Event start time
            end_time: Event end time
            location: Event location (optional)

        Returns:
            Outlook Calendar URL
        """
        try:
            # Format dates for Outlook (YYYY-MM-DDTHH:mm:ss)
            start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")

            # Build URL
            base_url = "https://outlook.live.com/calendar/0/deeplink/compose"
            params = [
                f"subject={title}",
                f"startdt={start_str}",
                f"enddt={end_str}",
                f"body={description}",
            ]

            if location:
                params.append(f"location={location}")

            url = base_url + "?" + "&".join(params)

            # URL encode
            from urllib.parse import quote

            return quote(url, safe=":/?&=")

        except Exception as e:
            logger.error(f"Failed to create Outlook Calendar link: {e}")
            return ""


class GoogleCalendarIntegration:
    """Google Calendar API integration (OAuth 2.0)"""

    def __init__(self, credentials: Dict):
        """
        Initialize Google Calendar integration

        Args:
            credentials: Google OAuth credentials dict
        """
        self.credentials = credentials
        self.service = None

    def authenticate(self):
        """Authenticate with Google Calendar API"""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_info(self.credentials)
            self.service = build("calendar", "v3", credentials=creds)

            logger.info("Google Calendar authenticated successfully")
            return True

        except Exception as e:
            logger.error(f"Google Calendar authentication failed: {e}")
            return False

    def create_event(
        self,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendees: Optional[List[str]] = None,
        location: Optional[str] = None,
        meeting_link: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create event in Google Calendar

        Returns:
            Event ID if successful, None otherwise
        """
        try:
            if not self.service:
                self.authenticate()

            event = {
                "summary": title,
                "description": description,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC",
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC",
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email", "minutes": 24 * 60},  # 24 hours
                        {"method": "popup", "minutes": 60},  # 1 hour
                    ],
                },
            }

            if location:
                event["location"] = location

            if meeting_link:
                event["description"] = f"{description}\n\nJoin Meeting: {meeting_link}"
                event["conferenceData"] = {
                    "entryPoints": [
                        {
                            "entryPointType": "video",
                            "uri": meeting_link,
                            "label": "Join Interview",
                        }
                    ]
                }

            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]

            created_event = (
                self.service.events()
                .insert(
                    calendarId="primary",
                    body=event,
                    sendUpdates="all",  # Send email notifications
                )
                .execute()
            )

            logger.info(f"Google Calendar event created: {created_event.get('id')}")
            return created_event.get("id")

        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")
            return None

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> bool:
        """Update existing Google Calendar event"""
        try:
            if not self.service:
                self.authenticate()

            event = (
                self.service.events()
                .get(calendarId="primary", eventId=event_id)
                .execute()
            )

            if title:
                event["summary"] = title
            if start_time:
                event["start"]["dateTime"] = start_time.isoformat()
            if end_time:
                event["end"]["dateTime"] = end_time.isoformat()

            (
                self.service.events()
                .update(
                    calendarId="primary",
                    eventId=event_id,
                    body=event,
                    sendUpdates="all",
                )
                .execute()
            )

            logger.info(f"Google Calendar event updated: {event_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update Google Calendar event: {e}")
            return False

    def delete_event(self, event_id: str) -> bool:
        """Delete Google Calendar event"""
        try:
            if not self.service:
                self.authenticate()

            self.service.events().delete(
                calendarId="primary", eventId=event_id, sendUpdates="all"
            ).execute()

            logger.info(f"Google Calendar event deleted: {event_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event: {e}")
            return False


class OutlookCalendarIntegration:
    """Microsoft Outlook Calendar API integration (Microsoft Graph)"""

    def __init__(self, access_token: str):
        """
        Initialize Outlook Calendar integration

        Args:
            access_token: Microsoft Graph API access token
        """
        self.access_token = access_token
        self.base_url = "https://graph.microsoft.com/v1.0"

    def create_event(
        self,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendees: Optional[List[str]] = None,
        location: Optional[str] = None,
        meeting_link: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create event in Outlook Calendar

        Returns:
            Event ID if successful, None otherwise
        """
        try:
            import requests

            event = {
                "subject": title,
                "body": {"contentType": "HTML", "content": description},
                "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
                "isReminderOn": True,
                "reminderMinutesBeforeStart": 60,
            }

            if location:
                event["location"] = {"displayName": location}

            if meeting_link:
                event["body"]["content"] = (
                    f"{description}<br><br><a href='{meeting_link}'>Join Meeting</a>"
                )

            if attendees:
                event["attendees"] = [
                    {"emailAddress": {"address": email}, "type": "required"}
                    for email in attendees
                ]

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"{self.base_url}/me/events", headers=headers, json=event
            )

            if response.status_code == 201:
                event_data = response.json()
                logger.info(f"Outlook Calendar event created: {event_data.get('id')}")
                return event_data.get("id")
            else:
                logger.error(f"Failed to create Outlook event: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Failed to create Outlook Calendar event: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """Delete Outlook Calendar event"""
        try:
            import requests

            headers = {"Authorization": f"Bearer {self.access_token}"}

            response = requests.delete(
                f"{self.base_url}/me/events/{event_id}", headers=headers
            )

            if response.status_code == 204:
                logger.info(f"Outlook Calendar event deleted: {event_id}")
                return True
            else:
                logger.error(f"Failed to delete Outlook event: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete Outlook Calendar event: {e}")
            return False
