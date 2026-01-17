import datetime

from typing import List
from util import Calendar

def get_events(service, calendars: Calendar | List[Calendar]):
    if not isinstance(calendars, list): calendars = [calendars]
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    events = []
    for cal in calendars: 
        page_token = None

        while True:
            events_result = service.events().list(
                calendarId=cal.id,
                singleEvents=True,
                timeMin=now
            ).execute()
            events += events_result.get("items", [])

            page_token = events_result.get("nextPageToken")
            if not page_token: break

    return events        