"""Calendar parser and scheduler for content proposals."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

from twitter_agent.models.schemas import CalendarEvent


class CalendarError(Exception):
    """Custom exception for calendar errors."""

    pass


class CalendarProcessor:
    """Process calendar files and schedule content proposals."""

    def __init__(self, calendar_file: Optional[str] = None):
        """
        Initialize calendar processor.

        Args:
            calendar_file: Path to calendar file (JSON or YAML)
        """
        self.calendar_file = Path(calendar_file) if calendar_file else None
        self.events: list[CalendarEvent] = []

    def load_calendar(self, calendar_file: Optional[str] = None) -> list[CalendarEvent]:
        """
        Load calendar events from file.

        Args:
            calendar_file: Path to calendar file (overrides default)

        Returns:
            List of CalendarEvent objects

        Raises:
            CalendarError: If file parsing fails
        """
        file_path = Path(calendar_file) if calendar_file else self.calendar_file
        if not file_path or not file_path.exists():
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            if file_path.suffix.lower() in {".yaml", ".yml"}:
                data = yaml.safe_load(content)
            elif file_path.suffix.lower() == ".json":
                data = json.loads(content)
            else:
                # Try to parse as JSON first, then YAML
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = yaml.safe_load(content)

            # Handle different formats
            events = []
            if isinstance(data, list):
                events_data = data
            elif isinstance(data, dict):
                events_data = data.get("events", [])
            else:
                events_data = []

            for event_data in events_data:
                # Parse date
                date_str = event_data.get("date") or event_data.get("datetime")
                if isinstance(date_str, str):
                    try:
                        event_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        # Try other date formats
                        from dateutil import parser

                        event_date = parser.parse(date_str)
                else:
                    continue

                event = CalendarEvent(
                    date=event_date,
                    title=event_data.get("title"),
                    description=event_data.get("description"),
                    tags=event_data.get("tags", []),
                    content_suggestions=event_data.get("content_suggestions", []),
                )
                events.append(event)

            self.events = sorted(events, key=lambda e: e.date)
            return self.events
        except Exception as e:
            raise CalendarError(f"Failed to parse calendar file: {str(e)}") from e

    def get_upcoming_events(self, days_ahead: int = 30) -> list[CalendarEvent]:
        """
        Get upcoming calendar events.

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming CalendarEvent objects
        """
        if not self.events:
            if self.calendar_file:
                self.load_calendar()
            else:
                return []

        now = datetime.now()
        cutoff = now + timedelta(days=days_ahead)

        return [event for event in self.events if now <= event.date <= cutoff]

    def get_event_for_date(self, target_date: datetime) -> Optional[CalendarEvent]:
        """
        Get calendar event for a specific date.

        Args:
            target_date: Target date to find event for

        Returns:
            CalendarEvent if found, None otherwise
        """
        if not self.events:
            if self.calendar_file:
                self.load_calendar()
            else:
                return None

        # Match by date (ignoring time)
        target_date_only = target_date.date()
        for event in self.events:
            if event.date.date() == target_date_only:
                return event

        return None

    def generate_schedule_hints(self, days_ahead: int = 7) -> str:
        """
        Generate scheduling hints for content proposals.

        Args:
            days_ahead: Number of days to generate hints for

        Returns:
            Formatted string with scheduling hints
        """
        upcoming = self.get_upcoming_events(days_ahead)
        if not upcoming:
            return "No calendar events found for scheduling."

        hints = []
        hints.append(f"UPCOMING CALENDAR EVENTS (next {days_ahead} days):")
        for event in upcoming:
            date_str = event.date.strftime("%Y-%m-%d %H:%M")
            hint = f"- {date_str}: {event.title or 'Untitled'}"
            if event.description:
                hint += f" - {event.description[:50]}"
            if event.tags:
                hint += f" [Tags: {', '.join(event.tags)}]"
            if event.content_suggestions:
                hint += f" [Suggested topics: {', '.join(event.content_suggestions)}]"
            hints.append(hint)

        return "\n".join(hints)

    def suggest_content_dates(self, count: int = 5) -> list[datetime]:
        """
        Suggest dates for content posting based on calendar.

        Args:
            count: Number of dates to suggest

        Returns:
            List of suggested datetime objects
        """
        upcoming = self.get_upcoming_events(30)
        if not upcoming:
            # No calendar events, suggest regular intervals
            suggestions = []
            for i in range(1, count + 1):
                suggestions.append(datetime.now() + timedelta(days=i * 2))
            return suggestions

        # Use calendar event dates as suggestions
        suggestions = [event.date for event in upcoming[:count]]
        # Fill remaining with intervals
        if len(suggestions) < count:
            last_date = suggestions[-1] if suggestions else datetime.now()
            for i in range(len(suggestions), count):
                suggestions.append(last_date + timedelta(days=(i + 1) * 2))

        return suggestions

