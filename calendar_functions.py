import datetime
import json
import logging
import os

from collections import defaultdict
from typing import List, Set
from util import Calendar
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

def extract_ids(events) -> Set[str]:
    ids: Set[str] = set()
    for event in events: ids.add(event["id"]) 

    return ids

def get_events(service, calendars: Calendar | List[Calendar]):
    if not isinstance(calendars, list): calendars = [calendars]
    now = datetime.datetime.now(tz=ZoneInfo("America/Phoenix")).isoformat()[:11] + "00:00:00.000Z"
    print(now)

    events = []
    logger.info("Starting to get events")
    for cal in calendars: 
        page_token = None

        while True:
            events_result = service.events().list(
                calendarId=cal.id,
                singleEvents=True,
                timeMin=now,
                pageToken=page_token,
                maxResults=250
            ).execute()
            fetched_events = events_result.get("items", [])
            events.extend(fetched_events)
            logger.info(f"Fetched {len(fetched_events)} events from {cal.name}")

            page_token = events_result.get("nextPageToken")
            if not page_token: break

    logger.info("Finished fetching events")
    return events

def init_sync_events(name: str, service, sync_from: List[Calendar], sync_to: Calendar) -> None:
    sync_from_events = get_events(service, sync_from)
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
    sync_from_events = get_events(service, sync_from)
    sync_to_events = get_events(service, sync_to)

    with open(f"mapping/{name}.json", "r") as f:
        pass

def init_sync_tasks(cal_service, tasks_service, sync_to: Calendar) -> None:
    now = datetime.datetime.now(tz=ZoneInfo("America/Phoenix")).isoformat()
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
    confirm = input(f"Confirm clearing of sync to calendar {calendar.name} by typing YES: ")
    if confirm == "YES":
        logging.info(f"Clearing calendar {calendar.name}")
        
        events = get_events(service, calendar)
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

def clear_todo_events(service, calendar: Calendar):
    confirm = input(f"Confirm clearing of TODO events in calendar {calendar.name} by typing YES: ")
    if confirm == "YES":
        logging.info(f"Clearing TODO events in {calendar.name}")
        
        events = get_events(service, calendar)
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