import datetime
import json
import logging
import os

from collections import defaultdict
from datetime import datetime, time
from dateutil.parser import isoparse
from googleapiclient.errors import HttpError
from typing import List, Set
from util import Calendar
from zoneinfo import ZoneInfo

PHX = ZoneInfo("America/Phoenix")
logger = logging.getLogger(__name__)

def extract_ids(events) -> Set[str]:
    ids: Set[str] = set()
    for event in events: ids.add(event["id"]) 

    return ids

def delete_event(service, cal: Calendar, id: str):
    service.events().delete(
        calendarId=cal.id,
        eventId=id
    ).execute()

def is_future_event(event):
    start = event.get("start", {})
    dt = start.get("dateTime") or start.get("date")
    if not dt: return False

    dt = isoparse(dt)
    dt = dt.replace(tzinfo=PHX) if dt.tzinfo is None else dt.astimezone(PHX)

    return dt >= datetime.combine(
        datetime.now(tz=PHX).date(), 
        time.min, 
        tzinfo=PHX)

def get_events(service, calendars: Calendar | List[Calendar], update_sync_tokens: bool):
    if not isinstance(calendars, list): calendars = [calendars]

    try:
        with open("sync_tokens/mapping.json", "r") as f:
            sync_tokens = json.load(f)
    except FileNotFoundError:
        sync_tokens = {}

    events = []
    logger.info("Starting to get events")
    for cal in calendars:
        page_token = None

        while True:
            events_result = service.events().list(
                calendarId=cal.id,
                singleEvents=True,
                maxResults=250,
                pageToken=page_token
            ).execute()
            fetched_events = events_result.get("items", [])
            events.extend(fetched_events)
            logger.info(f"Fetched {len(fetched_events)} events from {cal.name}")

            page_token = events_result.get("nextPageToken")
            if not page_token: 
                sync_token = events_result.get("nextSyncToken")
                if update_sync_tokens and sync_token: sync_tokens[cal.id] = sync_token
                break

    logger.info("Finished fetching events")

    if update_sync_tokens:
        with open("sync_tokens/tokens.json", "w") as f: json.dump(sync_tokens, f)

    future_events = [event for event in events if is_future_event(event)]
    logging.info(f"Filtered {len(events)} events down to {len(future_events)} future events")
    return future_events

def reinit_expired_sync_token(service, cal: Calendar, sync_to: Calendar, name: str):
    events = get_events(service, cal, update_sync_tokens=True)

    try:
        with open(f"mapping/{name}.json") as f:
            mapping = json.load(f)
    except FileNotFoundError:
        mapping = {} 

    for i, event in enumerate(events):
        event_id = event["id"]

        if event_id in mapping: 
            try:
                delete_event(service, sync_to, mapping[event_id])
            except HttpError:
                pass
            del mapping[event_id]

        new_event = {
            "summary": event["summary"],
            "start": event["start"],
            "end": event["end"],
            "description": event.get("description")
        }

        if name == "mollee" and event["summary"] == "Journey anni <3":
            logging.info(f"[{i + 1}/{len(events)}] Skipping (anni)")
            continue

        created_event = service.events().insert(
            calendarId=sync_to.id,
            body=new_event
        ).execute()
        logging.info(f"[{i + 1}/{len(events)}] {event["summary"]} - {event["organizer"].get("displayName", "")}")

        mapping[event["id"]] = created_event["id"]

    with open(f"mapping/{name}.json") as f:
        json.dump(mapping, f)

def get_updated_events(service, calendars: Calendar | List[Calendar], sync_to: Calendar, name: str, update_sync_tokens: bool):
    if not isinstance(calendars, list): calendars = [calendars]

    try:
        with open("sync_tokens/tokens.json", "r") as f:
            sync_tokens = json.load(f)
    except FileNotFoundError:
        sync_tokens = {}

    events = []
    logger.info("Starting to get updated events")
    for cal in calendars: 
        page_token = None
        sync_token = sync_tokens.get(cal.id)

        logger.info(f"Fetching updated events for {cal.name}")
        while True:
            try:
                events_result = service.events().list(
                    calendarId=cal.id,
                    singleEvents=True,
                    maxResults=250,
                    showDeleted=True,
                    pageToken=page_token,
                    syncToken = sync_token
                ).execute()
                fetched_events = events_result.get("items", [])
                events.extend(fetched_events)
                logger.info(f"Fetched {len(fetched_events)} updated events from {cal.name}")

                page_token = events_result.get("nextPageToken")
                if not page_token: 
                    sync_token = events_result.get("nextSyncToken")
                    if update_sync_tokens and sync_token: sync_tokens[cal.id] = sync_token
                    break

            except HttpError as e:
                if e.resp.status == 410:
                    logger.warning(f"Sync token expired for {cal.name}")
                    reinit_expired_sync_token(service, cal, sync_to, name)
                else:
                    raise

    if update_sync_tokens: 
        with open("sync_tokens/tokens.json", "w") as f: json.dump(sync_tokens, f)

    logger.info("Finished fetching events")

    return events

def init_sync_events(name: str, service, sync_from: List[Calendar], sync_to: Calendar) -> None:
    sync_from_events = get_events(service, sync_from, update_sync_tokens=True)
    logging.info(f"Fetched {len(sync_from_events)} sync from events")

    mapping = {}
    logging.info("Creating sync to events")
    for i, event in enumerate(sync_from_events):
        new_event = {
            "summary": event["summary"],
            "start": event["start"],
            "end": event["end"],
            "description": event.get("description", "")
        }

        if name == "mollee" and event["summary"] == "Journey anni <3":
            logging.info(f"[{i + 1}/{len(sync_from_events)}] Skipping (anni)")
            continue

        created_event = service.events().insert(
            calendarId=sync_to.id,
            body=new_event
        ).execute()
        logging.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]} - {event["organizer"].get("displayName", "")}")

        mapping[event["id"]] = created_event["id"]
    logging.info("Finished syncing events")

    with open(f"mapping/{name}.json", "w") as f:
        json.dump(mapping, f)

def sync_events(service, sync_from: List[Calendar], sync_to: Calendar, name: str) -> None:
    sync_from_events = get_updated_events(service, sync_from, sync_to, name, update_sync_tokens=True)
    logger.info(f"Found {len(sync_from_events)} events to sync")
    if len(sync_from_events) == 0: return

    with open(f"mapping/{name}.json", "r") as f:
        mapping = json.load(f)
    stored_sync_from_ids = set(mapping.keys())

    for i, event in enumerate(sync_from_events):
        event_id = event["id"]
        if event_id in stored_sync_from_ids:
            sync_to_event_id = mapping[event_id]

            if event["status"] == "cancelled":
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Deleted - Deleting Sync To Event ")
                
                delete_event(service, sync_to, mapping[event_id])
                del mapping[event_id]
            else:
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Edited - Updating Sync To Event ")

                updated_info = {
                    "summary": event["summary"],
                    "start": event["start"],
                    "end": event["end"],
                    "description": event.get("description")
                }

                updated_event = service.events().patch(
                    calendarId=sync_to.id,
                    eventId=sync_to_event_id,
                    body=updated_info
                ).execute()
        else:
            if event["status"] != "cancelled":
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Added - Creating Sync To Event ")

                new_event = {
                    "summary": event["summary"],
                    "start": event["start"],
                    "end": event["end"],
                    "description": event.get("description")
                }

                created_event = service.events().insert(
                    calendarId=sync_to.id,
                    body=new_event
                ).execute()

                mapping[event_id] = created_event["id"]

    logger.info("Finished syncing events")
    with open(f"mapping/{name}.json", "w") as f:
        json.dump(mapping, f)

def init_sync_tasks(cal_service, tasks_service, sync_to: Calendar) -> None:
    now = datetime.now(tz=PHX).isoformat()
    day = now[:11] + "00:00:00.000Z"

    page_token = None
    tasks = []
    while True:
        tasks_result = tasks_service.tasks().list(
            tasklist="@default",
            showHidden=True,
            showCompleted=True,
            maxResults=100,
            pageToken=page_token
        ).execute()
        task_items = tasks_result.get("items", [])
        tasks.extend(task_items)
        
        logging.info(f"Fetched {len(task_items)} tasks")

        page_token = tasks_result.get("nextPageToken")
        if not page_token: break

    # Only handle tasks that are today or in the future 
    logging.info(f"Processing {len(tasks)} tasks")
    sorted_tasks = defaultdict(list)
    for i, task in enumerate(tasks):
        due_time = task["due"]
        if due_time >= day: 
            sorted_tasks[due_time[:11] + "00:00:00.000Z"].append(task)
            logging.info(f"[{i + 1}/{len(tasks)}] {task["title"]} in day {due_time[:11]}")
    
    logging.info(f"Creating events for {sum(len(task_list) for task_list in sorted_tasks.values())}")
    mapping = {}
    for i, (day, task_list) in enumerate(sorted_tasks.items()):
        formatted_task_list = []
        for task in task_list:
            if task["status"] == "completed":
                formatted_task_list.append(f"\u2705 {task['title']}")
            else:
                formatted_task_list.append(f"\u274C {task["title"]}")
        new_task_list = "\n".join(formatted_task_list)

        new_event = {
            "summary": "TODO",
            "start": {"dateTime": day[:11] + "06:00:00.000", "timeZone" : "America/Phoenix"},
            "end": {"dateTime": day[:11] + "06:30:00.000", "timeZone" : "America/Phoenix"},
            "description": new_task_list
        }

        created_event = cal_service.events().insert(
            calendarId=sync_to.id,
            body=new_event
        ).execute()
        logging.info(f"Day [{i + 1}/{len(sorted_tasks.keys())}] added tasks\n{new_task_list}")
        
        mapping[created_event["id"]] = [task["id"] for task in task_list]
        logging.info("Finished syncing tasks")

    with open("mapping/tasks.json", "w") as f:
        json.dump(mapping, f)

def sync_tasks(cal_service, tasks_service, sync_to: Calendar) -> None:
    pass

def clear_sync_to_calendar(name: str, service, calendar: Calendar):
    logging.info(f"Clearing calendar {calendar.name}")
    
    events = get_events(service, calendar, update_sync_tokens=False)
    logging.info(f"Clearing {len(events)} events")
    
    for i, event in enumerate(events):
        if event["summary"] == "TODO": 
            logging.info(f"[{i + 1}/{len(events)}] Skipping TODO Event")
            continue
        service.events().delete(
            calendarId=calendar.id,
            eventId=event.get("id")
        ).execute()
        logging.info(f"[{i + 1}/{len(events)}] {event["summary"]} - {event["organizer"].get("displayName", "")}")

    logging.info("Finished clearing events")

    if os.path.exists(f"mapping/{name}.json"): 
        os.remove(f"mapping/{name}.json")
        logging.info("Removing mapping")

    if os.path.exists("sync_tokens/tokens.json"):
        os.remove("sync_tokens/tokens.json")
        logging.info("Remove sync tokens")

def clear_todo_events(service, calendar: Calendar):
    logging.info(f"Clearing TODO events in {calendar.name}")
    
    events = get_events(service, calendar, update_sync_tokens=False)
    for i, event in enumerate(events):
        if event["summary"] == "TODO": 
            service.events().delete(
                calendarId=calendar.id,
                eventId=event.get("id")
            ).execute()
            logging.info(f"[{i + 1}/{len(events)}] {event["summary"]} - {event["organizer"].get("displayName", "")}")
        else:
            logging.info(f"[{i + 1}/{len(events)}] Skipping non TODO event")

    logging.info("Finished clearing events")

    if os.path.exists(f"mapping/tasks.json"): 
        os.remove(f"mapping/tasks.json")
        logging.info("Removing mapping")