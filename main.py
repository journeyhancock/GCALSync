import json
import logging
import os

from googleapiclient.discovery import build
from google.cloud import storage
from gcloud_storage import download_file, upload_file
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

def update_local_files(client: storage.Client):
    logging.info("Updating local files")

    # mappings
    journey = download_file(client, "journey.json")
    with open("mapping/journey.json", "w") as f: json.dump(journey, f)
    logging.info("Downloaded Journey event mapping")

    mollee = download_file(client, "mollee.json")
    with open("mapping/mollee.json", "w") as f: json.dump(mollee, f)
    logging.info("Downloaded Mollee event mapping")

    days_events = download_file(client, "days_events.json")
    with open("mapping/days_events.json", "w") as f: json.dump(days_events, f)
    logging.info("Downloaded days events mapping")

    tasks_events = download_file(client, "tasks_events.json")
    with open("mapping/tasks_events.json", "w") as f: json.dump(tasks_events, f)
    logging.info("Downloaded tasks events mapping")

    # sync tokens
    journey_event_tokens = download_file(client, "journey_event_tokens.json")
    with open("sync_tokens/journey_event_tokens.json", "w") as f: json.dump(journey_event_tokens, f)
    logging.info("Downloaded Journey event tokens")

    mollee_event_tokens = download_file(client, "mollee_event_tokens.json")
    with open("sync_tokens/mollee_event_tokens.json", "w") as f: json.dump(mollee_event_tokens, f)
    logging.info("Downloaded Mollee event tokens")

    tasks_sync_time = download_file(client, "tasks_sync_time.json")
    with open("sync_tokens/tasks_sync_time.json", "w") as f: json.dump(tasks_sync_time, f)
    logging.info("Downloaded task sync time")

def update_cloud_files(client: storage.Client):
    # mappings
    with open("mapping/journey.json", "r") as f: journey = json.load(f)
    upload_file(client, file="journey.json", data=journey)
    logging.info("Uploaded Journey event mapping")

    with open("mapping/mollee.json", "r") as f: mollee = json.load(f)
    upload_file(client, file="mollee.json", data=mollee)
    logging.info("Uploaded Mollee event mapping")

    with open("mapping/days_events.json", "r") as f: days_events = json.load(f)
    upload_file(client, file="days_events.json", data=days_events)
    logging.info("Uploaded days events mapping")

    with open("mapping/tasks_events.json", "r") as f: tasks_events = json.load(f)
    upload_file(client, file="tasks_events.json", data=tasks_events)
    logging.info("Uploaded tasks events mapping")

    # sync tokens
    with open("sync_tokens/journey_event_tokens.json", "r") as f: journey_event_tokens = json.load(f)
    upload_file(client, file="journey_event_tokens.json", data=journey_event_tokens)
    logging.info("Uploaded Journey event tokens")

    with open("sync_tokens/mollee_event_tokens.json", "r") as f: mollee_event_tokens = json.load(f)
    upload_file(client, file="mollee_event_tokens.json", data=mollee_event_tokens)
    logging.info("Uploaded Mollee event tokens")

    with open("sync_tokens/tasks_sync_time.json", "r") as f: tasks_sync_time = json.load(f)
    upload_file(client, file="tasks_sync_time.json", data=tasks_sync_time)
    logging.info("Uploaded tasks sync time")

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
    if os.path.exists("mapping/journey.json"):
        logger.info("Syncing events")
        sync_events(cal_service, cal_ids.sync_from, cal_ids.sync_to, "journey")
    else:
        logger.info("Initializing sync to")
        init_sync_events(cal_service, cal_ids.sync_from, cal_ids.sync_to, "journey")

    # Initialize task TODO events in Sync To Calendar or update it
    if os.path.exists("mapping/days_events.json") and os.path.exists("mapping/tasks_events.json"):
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
    if os.path.exists("mapping/mollee.json"):
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

    journey()
    mollee()

    update_cloud_files(client=client)

if __name__ == "__main__":
    main()