import os

from googleapiclient.discovery import build
from tokens.get_tokens import get_credentials
from calendar_functions import get_events
from config import get_cal_ids

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly"]

# Fetch or create credentials if necessary
creds = get_credentials()

# -- Journey --
# Build services 
cal_service = build("calendar", "v3", credentials=creds.journey_creds)
tasks_service = build("tasks", "v1", credentials=creds.journey_creds)

# Fetch calendars to sync from and to from config
cal_ids = get_cal_ids(cal_service, "journey")
print(cal_ids)

print("** Sync From Events **")
sync_from_events = get_events(cal_service, cal_ids.sync_from)
for event in sync_from_events:
    print(f"{event["summary"]} - {event["id"]}")
print("----------------------")

print("** Sync To Events **")
sync_to_events = get_events(cal_service, cal_ids.sync_to)
for event in sync_from_events:
    print(f"{event["summary"]} - {event["id"]}")
print("----------------------")

# -- Mollee --
# Build services
cal_service = build("calendar", "v3", credentials=creds.mollee_creds)