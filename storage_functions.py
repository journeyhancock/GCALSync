import json
import logging

from calendar_functions import get_task, get_event
from datetime import date, datetime, timedelta
from dateutil.parser import isoparse
from googleapiclient.errors import HttpError
from util import Calendar, read_file, write_file
from zoneinfo import ZoneInfo

PHX = ZoneInfo("America/Phoenix")
PRUNE_AGE = timedelta(hours=24)
logger = logging.getLogger(__name__)

def prune_cutoff() -> datetime:
    # Only prune things more than PRUNE_AGE older than now, so a run near midnight never touches the current day
    return datetime.now(tz=PHX) - PRUNE_AGE

def is_date_before_cutoff(value: str, cutoff: datetime) -> bool:
    # Date-only values (all-day events, task due dates, day keys) are compared by calendar date
    return date.fromisoformat(value[:10]) < cutoff.date()

def is_event_before_cutoff(event, cutoff: datetime) -> bool:
    end = event.get("end", {})
    if end.get("dateTime"):
        return isoparse(end["dateTime"]).astimezone(PHX) < cutoff
    if end.get("date"):
        # All-day end dates are exclusive, so the last day of the event is the day before
        last_day = date.fromisoformat(end["date"]) - timedelta(days=1)
        return last_day < cutoff.date()
    return False

def prune_calendar(service, sync_to: Calendar, name: str):
    mapping = read_file(name)
    cutoff = prune_cutoff()

    logger.info(f"Pruning {name} Sync To, cutoff {cutoff.isoformat()}")
    to_remove = []
    for i, (sync_from_id, sync_to_id) in enumerate(mapping.items()):
        try:
            sync_to_event = get_event(service, sync_to_id, sync_to)
        except HttpError as e:
            if e.resp.status != 404: raise
            logger.info(f"[{i + 1}/{len(mapping)}] Removing - Event no longer exists")
            to_remove.append(sync_from_id)
            continue

        if is_event_before_cutoff(sync_to_event, cutoff):
            logger.info(f"[{i + 1}/{len(mapping)}] Removing - Event in past")
            to_remove.append(sync_from_id)
        else:
            logger.info(f"[{i + 1}/{len(mapping)}] Keeping - Event in future")
    for event_id in to_remove: mapping.pop(event_id)
    logger.info(f"Pruned {len(to_remove)} {name} event mappings")

    write_file(name, mapping)

    logger.info("Finished pruning")

def prune_tasks(service):
    cutoff = prune_cutoff()

    days_events = read_file("days_events")
    tasks_events = read_file("tasks_events")

    logger.info(f"Pruning Tasks, cutoff {cutoff.isoformat()}")
    to_remove = []
    for i, day in enumerate(days_events.keys()):
        if is_date_before_cutoff(day, cutoff):
            logger.info(f"[{i + 1}/{len(days_events)}] Removing - Day in past")
            to_remove.append(day)
        else:
            logger.info(f"[{i + 1}/{len(days_events)}] Skipping - Day in future")
    for day in to_remove: days_events.pop(day)
    logger.info(f"Pruned {len(to_remove)} day:event mappings")

    to_remove = []
    for i, task_id in enumerate(tasks_events.keys()):
        try:
            task = get_task(service, task_id)
        except HttpError as e:
            if e.resp.status != 404: raise
            logger.info(f"[{i + 1}/{len(tasks_events)}] Removing - Task no longer exists")
            to_remove.append(task_id)
            continue

        if is_date_before_cutoff(task["due"], cutoff):
            logger.info(f"[{i + 1}/{len(tasks_events)}] Removing - Task due in past")
            to_remove.append(task_id)
        else:
            logger.info(f"[{i + 1}/{len(tasks_events)}] Skipping - Task due in future")
    for task_id in to_remove: tasks_events.pop(task_id)
    logger.info(f"Pruned {len(to_remove)} task:event mappings")

    write_file("days_events", days_events)
    write_file("tasks_events", tasks_events)

    logger.info("Finished pruning")