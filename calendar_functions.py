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
        with open("sync_tokens/event_tokens.json", "r") as f:
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
        with open("sync_tokens/event_tokens.json", "w") as f: json.dump(sync_tokens, f)

    future_events = [event for event in events if is_future_event(event)]
    logging.info(f"Filtered {len(events)} events down to {len(future_events)} future events")
    return future_events

def reinit_expired_calendar_sync_token(service, cal: Calendar, sync_to: Calendar, name: str):
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
            mapping.pop(event_id)

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
        with open("sync_tokens/event_tokens.json", "r") as f:
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
                    syncToken=sync_token
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
                    reinit_expired_calendar_sync_token(service, cal, sync_to, name)
                else:
                    raise

    if update_sync_tokens: 
        with open("sync_tokens/event_tokens.json", "w") as f: json.dump(sync_tokens, f)

    logger.info("Finished fetching events")

    return events

def init_sync_events(service, sync_from: List[Calendar], sync_to: Calendar, name: str) -> None:
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
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Deleted - Deleting Sync To Event")
                
                delete_event(service, sync_to, mapping[event_id])
                mapping.pop(event_id)
            else:
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Edited - Updating Sync To Event")

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
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Added - Creating Sync To Event")

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
            else:
                logger.info(f"[{i + 1}/{len(sync_from_events)}] {event["summary"]}: Sync From Event Canceled - Skipping (Not in sync to)")

    logger.info("Finished syncing events")
    with open(f"mapping/{name}.json", "w") as f:
        json.dump(mapping, f)

def is_future_task(task):
    now = datetime.now(tz=PHX).isoformat()
    day = now[:11] + "00:00:00.000Z"

    due_time = task["due"]
    return True if due_time >= day else False

def get_tasks(service, update_sync_time: bool):
    try:
        with open("sync_tokens/tasks_sync_time.json", "r") as f:
            tasks_time = json.load(f)
    except FileNotFoundError:
        tasks_time = {}

    tasks = []
    page_token = None
    logger.info("Starting to get tasks")
    
    while True:
        tasks_result = service.tasks().list(
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
        if not page_token: 
            if update_sync_time: tasks_time["tasks"] = datetime.now(tz=PHX).isoformat()
            break

    logger.info("Finished fetching tasks")

    if update_sync_time:
        with open("sync_tokens/tasks_sync_time.json", "w") as f:
            json.dump(tasks_time, f)

    future_tasks = [task for task in tasks if is_future_task(task)]
    logging.info(f"Filtered {len(tasks)} tasks down to {len(future_tasks)} future tasks")
    return future_tasks

def get_updated_tasks(tasks_service, update_sync_time: bool):
    try:
        with open("sync_tokens/tasks_sync_time.json", "r") as f:
            tasks_time = json.load(f)
    except FileNotFoundError:
        tasks_time = {}

    tasks = []
    logger.info("Starting to get updated tasks")
    page_token = None
    sync_time = tasks_time["tasks"]

    while True:
        tasks_result = tasks_service.tasks().list(
            tasklist="@default",
            showHidden=True,
            showCompleted=True,
            showDeleted=True,
            updatedMin=sync_time,
            pageToken=page_token
        ).execute()
        fetched_tasks = tasks_result.get("items", [])
        tasks.extend(fetched_tasks)
        logger.info(f"Fetched {len(fetched_tasks)} updated events")

        page_token = tasks_result.get("nextPageToken")
        if not page_token:
            if update_sync_time: tasks_time["tasks"] = datetime.now(tz=PHX).isoformat()
            break

    if update_sync_time:
        with open("sync_tokens/tasks_sync_time.json", "w") as f: json.dump(tasks_time, f)

    logger.info("Finished fetching tasks")

    return tasks

def init_sync_tasks(cal_service, tasks_service, sync_to: Calendar) -> None:
    now = datetime.now(tz=PHX).isoformat()
    day = now[:11] + "00:00:00.000Z"

    tasks = get_tasks(tasks_service, update_sync_time=True)

    # Sort tasks by their day
    sorted_tasks = defaultdict(list)
    logging.info(f"Processing {len(tasks)} tasks")
    for i, task in enumerate(tasks):
        due_time = task.get("due")
        sorted_tasks[due_time[:11] + "00:00:00.000Z"].append(task)
        logging.info(f"[{i + 1}/{len(tasks)}] {task["title"]} in day {due_time[:11]}")
    
    logging.info(f"Creating events for {sum(len(task_list) for task_list in sorted_tasks.values())}")
    day_event_mapping = {}
    task_event_mapping = {}
    for i, (day, task_list) in enumerate(sorted_tasks.items()):
        formatted_task_list = []
        for task in task_list:
            if task["status"] == "completed":
                formatted_task_list.append(f"\u2705 {task["title"]}")
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
        
        day_event_mapping[day] = created_event["id"]
        for task in task_list: task_event_mapping[task["id"]] = created_event["id"]
        
    logging.info("Finished syncing tasks")

    with open("mapping/days_events.json", "w") as f:
        json.dump(day_event_mapping, f)
    with open("mapping/tasks_events.json", "w") as f:
        json.dump(task_event_mapping, f)

def get_event(service, event_id: str, cal: Calendar):
    return service.events().get(
        calendarId=cal.id,
        eventId=event_id
    ).execute()

def get_task(service, task_id: str):
    return service.tasks().get(
        tasklist="@default",
        task=task_id
    ).execute() 

def remove_task(cal_service, sync_to: Calendar, event, task):
    todo_list = event.get("description").strip()
    new_todo_list = "\n".join(
        line for line in todo_list.splitlines()
        if line.lstrip("\u2705\u274C ").strip() != task["title"]
    )

    updated_event = cal_service.events().patch(
        calendarId=sync_to.id,
        eventId=event["id"],
        body={"description": new_todo_list}
    ).execute()

def sync_tasks(cal_service, tasks_service, sync_to: Calendar) -> None:
    tasks = get_updated_tasks(tasks_service, update_sync_time=True)
    logger.info(f"Found {len(tasks)} tasks to sync")
    if len(tasks) == 0: return

    with open("mapping/days_events.json", "r") as f:
        days_events = json.load(f)
    stored_days = set(days_events.keys())

    with open("mapping/tasks_events.json", "r") as f:
        tasks_events = json.load(f)
    stored_tasks = set(tasks_events.keys())

    for i, task in enumerate(tasks):
        day = task["due"][:11] + "00:00:00.000Z"
        if day in stored_days:
            event_id = days_events[day]

            if task.get("deleted"):
                logger.info(f"[{i + 1}/{len(tasks)}] {task["title"]}: Task Deleted - Removing from TODO event")

                event = get_event(cal_service, event_id, sync_to)
                remove_task(cal_service, sync_to, event, task)
                tasks_events.pop(task["id"])
            else:
                task_id = task["id"]
                if task_id in stored_tasks:
                    logger.info(f"[{i + 1}/{len(tasks)}] {task["title"]}: Task Updated - Placing in existing TODO event")

                    old_event_id = tasks_events[task_id]
                    old_event = cal_service.events().get(
                        calendarId=sync_to.id,
                        eventId=old_event_id
                    ).execute()
                    remove_task(cal_service, sync_to, old_event, task)
                else:
                    logger.info(f"[{i + 1}/{len(tasks)}] {task["title"]}: Task Created - Placing in existing TODO event")

                event = get_event(cal_service, event_id, sync_to)
                todo_list = event.get("description")

                new_todo_list = todo_list + f"\n{"\u2705" if task["status"] == "completed" else "\u274C"} {task["title"]}"
                updated_event = cal_service.events().patch(
                    calendarId=sync_to.id,
                    eventId=days_events[day],
                    body={"description": new_todo_list}
                ).execute()
                    
                tasks_events[task_id] = event_id
        else:
            task_id = task["id"]
            if task_id in stored_tasks:
                logger.info(f"[{i + 1}/{len(tasks)}] {task["title"]}: Task Updated - Placing in new TODO event")

                old_event_id = tasks_events[task["id"]]
                old_event = get_event(cal_service, old_event_id, sync_to)
                remove_task(cal_service, sync_to, old_event, task)
            else:
                logger.info(f"[{i + 1}/{len(tasks)}] {task["title"]}: Task Created - Placing in new TODO event")
                
            new_event = {
                "summary": "TODO",
                "start": {"dateTime": day[:11] + "06:00:00.000", "timeZone" : "America/Phoenix"},
                "end": {"dateTime": day[:11] + "06:30:00.000", "timeZone" : "America/Phoenix"},
                "description": f"{"\u2705" if task["status"] == "completed" else "\u274C"} {task["title"]}"
            }

            created_event = cal_service.events().insert(
                calendarId=sync_to.id,
                body=new_event
            ).execute()
            
            days_events[day] = created_event["id"]
            tasks_events[task_id] = created_event["id"]
            
    logger.info("Finished syncing tasks")
    
    with open("mapping/days_events.json", "w") as f:
        json.dump(days_events, f)

    with open(f"mapping/tasks_events.json", "w") as f:
        json.dump(tasks_events, f) 

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

    if os.path.exists("sync_tokens/event_tokens.json"):
        os.remove("sync_tokens/event_tokens.json")
        logging.info("Remove event sync tokens")

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

    if os.path.exists("sync_tokens/task_token.json"):
        os.remove("sync_tokens/task_token.json")
        logging.info("Removing tasks sync token")

    if os.path.exists("mapping/days_events.json"): 
        os.remove("mapping/days_events.json")
        logging.info("Removing days events mapping")
    
    if os.path.exists("mapping/tasks_events.json"):
        os.remove("mapping/tasks_events.json")
        logging.info("Removing tasks events mapping")