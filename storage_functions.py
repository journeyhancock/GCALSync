import json
import logging

from calendar_functions import get_task, is_future_task, get_event, is_future_event
from datetime import datetime
from util import Calendar, read_file, write_file
from zoneinfo import ZoneInfo

PHX = ZoneInfo("America/Phoenix")
logger = logging.getLogger(__name__)

def prune_calendar(service, sync_to: Calendar, name: str):
    mapping = read_file(f"mapping/{name}.json")

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

    write_file(f"mapping/{name}.json", mapping)

    logger.info("Finished pruning")

def prune_tasks(service):
    now = datetime.now(tz=PHX).isoformat()
    day = now[:11] + "00:00:00.000Z"

    days_events = read_file("mapping/days_events.json")
    tasks_events = read_file("mapping/tasks_events.json")

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

    write_file("mapping/days_events.json", days_events)
    write_file("mapping/tasks_events.json", tasks_events)

    logger.info("Finished pruning")