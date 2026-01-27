import logging
import os

from googleapiclient.discovery import build
from google.cloud import storage
from gcloud_storage import update_local_files, update_cloud_files
from tokens.get_tokens import get_credentials, get_refresh_token
from calendar_functions import (get_events, 
                                clear_sync_to_calendar,
                                clear_todo_events, 
                                init_sync_events, 
                                sync_events,
                                init_sync_tasks,
                                sync_tasks,
                                get_updated_events)
from config import get_cal_ids
from storage_functions import (prune_calendar,
                               prune_tasks)
from util import read_file, write_file

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly",
          "https://www.googleapis.com/auth/cloud-platform"]

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)

# Fetch or create credentials if necessary
logger.info("Fetching credentials")
creds = get_credentials()

def journey():
    logger.info("-- Journey --")
    # Build services 
    logger.info("Building services")
    cal_service = build("calendar", "v3", credentials=creds.journey_creds)
    tasks_service = build("tasks", "v1", credentials=creds.journey_creds)

    # Fetch calendars to Sync From and Sync To from config
    logger.info("Fetching calendar ids")
    cal_ids = get_cal_ids(cal_service, "journey")

    # Wipe Sync To Calendar 
    if False:
        confirm = input(f"Confirm clearing of Sync To Calendar by typing YES: ")
        if confirm == "YES":
            clear_sync_to_calendar("journey", cal_service, cal_ids.sync_to)
        return
    
    # Wipe TODO events
    if False:
        confirm = input(f"Confirm clearing of TODO events in calendar {cal_ids.sync_to.name} by typing YES: ")
        if confirm == "YES":
            clear_todo_events(cal_service, cal_ids.sync_to)
        return

    # Initialize Sync To Calendar or update it 
    if read_file("journey_events") != {}:
        logger.info("Syncing events")
        sync_events(cal_service, cal_ids.sync_from, cal_ids.sync_to, "journey")
    else:
        logger.info("Initializing sync to")
        init_sync_events(cal_service, cal_ids.sync_from, cal_ids.sync_to, "journey")

    # Initialize task TODO events in Sync To Calendar or update it
    if read_file("days_events") != {} and read_file("tasks_events") != {}:
        logger.info("Syncing tasks")
        sync_tasks(cal_service, tasks_service, cal_ids.sync_to)
    else:
        logger.info("Initializing TODOs")
        init_sync_tasks(cal_service, tasks_service, cal_ids.sync_to)

    # Prune storage of old mappings
    if False:
        prune_calendar(cal_service, cal_ids.sync_to, "journey")
        prune_tasks(tasks_service)

def mollee():
    logger.info("-- Mollee --")
    # Build services
    logger.info("Building services")
    cal_service = build("calendar", "v3", credentials=creds.mollee_creds)

    # Fetch calendars to sync from and to from config
    logger.info("Fetching calendar ids")
    cal_ids = get_cal_ids(cal_service, "mollee")

    # Wipe sync to 
    if False:
        confirm = input(f"Confirm clearing of Sync To Calendar by typing YES: ")
        if confirm == "YES":
            clear_sync_to_calendar("mollee", cal_service, cal_ids.sync_to)
        return

    # Initialize sync to calendar or update it 
    if read_file("mollee_events") != {}:
        logger.info("Syncing events")
        sync_events(cal_service, cal_ids.sync_from, cal_ids.sync_to, "mollee")
    else:
        logger.info("Initializing sync to")
        init_sync_events(cal_service, cal_ids.sync_from, cal_ids.sync_to, "mollee")

    # Prune storage of old mappings
    if False:
        prune_calendar(cal_service, cal_ids.sync_to, "mollee")

def main():
    client = storage.Client(
        project="quiet-engine-471620-s7",
        credentials=creds.journey_creds)
    
    update_local_files(client=client)

    try:
        journey()
        mollee()
    finally:
        update_cloud_files(client=client)

if __name__ == "__main__":
    main()