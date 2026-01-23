import json
import logging

from calendar_functions import get_task, is_future_task, get_event, is_future_event
from datetime import datetime
from util import Calendar
from zoneinfo import ZoneInfo

PHX = ZoneInfo("America/Phoenix")
logger = logging.getLogger(__name__)

def prune_calendar(service, sync_to: Calendar, name: str):
    try:
        with open(f"mapping/{name}.json", "r") as f:
            mapping = json.load(f)
    except FileNotFoundError:
        mapping = {}

    logger.info(f"Pruning {name} Sync To")
    to_remove = []
    for i, (sync_from_id, sync_to_id) in enumerate(mapping.items()):
        sync_to_event = get_event(service, sync_to_id, sync_to)
        
        if not is_future_event(sync_to_event):
            logger.info(f"[{i + 1}/{len(mapping)}] Removing - Event in past")
            to_remove.append(sync_from_id)
        else:
            logger.info(f"[{i + 1}/{len(mapping)}] Keeping - Event in future")
    for event_id in to_remove: mapping.pop(event_id)
    logger.info(f"Pruned {len(to_remove)} {name} event mappings")

    with open(f"mapping/{name}.json", "w") as f:
        json.dump(mapping, f)

    logger.info("Finished pruning")

def prune_tasks(service):
    now = datetime.now(tz=PHX).isoformat()
    day = now[:11] + "00:00:00.000Z"

    try:
        with open("mapping/days_events.json", "r") as f:
            days_events = json.load(f)
    except FileNotFoundError:
        days_events = {}

    try:
        with open("mapping/tasks_events.json", "r") as f:
            tasks_events = json.load(f)
    except FileNotFoundError:
        tasks_events = {}

    logger.info("Pruning Tasks")
    to_remove = []
    for i, day in enumerate(days_events.keys()):
        if day < now:
            logger.info(f"[{i + 1}/{len(days_events)}] Removing - Day in past")
            to_remove.append(day)
        else:
            logger.info(f"[{i + 1}/{len(days_events)}] Skipping - Day in future")
    for day in to_remove: days_events.pop(day)
    logger.info(f"Pruned {len(to_remove)} day:event mappings")

    to_remove = []
    for i, task_id in enumerate(tasks_events.keys()):
        task = get_task(service, task_id)
        
        if not is_future_task(task): 
            logger.info(f"[{i + 1}/{len(tasks_events)}] Removing - Task due in past")
            to_remove.append(task_id)
        else:
            logger.info(f"[{i + 1}/{len(tasks_events)}] Skipping - Task due in future")
    for task_id in to_remove: tasks_events.pop(task_id)
    logger.info(f"Pruned {len(to_remove)} task:event mappings")

    with open("mapping/days_events.json", "w") as f:
        json.dump(days_events, f)

    with open("mapping/tasks_events.json", "w") as f:
        json.dump(tasks_events, f)

    logger.info("Finished pruning")