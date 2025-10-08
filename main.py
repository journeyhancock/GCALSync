import json

from Database import setup
from Database import util as db_util

from Sync import calendar_sync, tasks_sync, auth, util as sync_util

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def main():
    setup.init_db()

    session = setup.get_session()
    conn = db_util.start_connection()

    # Gather local config
    config = {}
    with open("config.json", "r") as json_config:
        config = json.load(json_config)
    
    calendar_config = config["calendar_sync"]["journey"]
    creds = auth.authenticate("journey") # Authenticate connection to Google API
    service = build("calendar", "v3", credentials=creds) # Start calendar service 
    task_service = build("tasks", "v1", credentials=creds) # Start calendar service
    sync_from, sync_to = sync_util.get_cal_ids(service=service, name="journey") # Run setup for cal sync
    CalendarSyncJourney = calendar_sync.CalendarSync("journey", service=service, task_service=task_service, sync_from=sync_from, sync_to=sync_to) # CalendarSync object

    # response = input("Perform a reset of journey sync_to? (y/n): ")
    # if response == "y": CalendarSyncJourney.clear_sync_to()

    CalendarSyncJourney.sync_all() # Confirm database, sync_from, and sync_to are synced
    CalendarSyncJourney.sync_tasks() # Confirm database, tasks, and sync_to TODOs are synced
    
    print("-----------------------")

    calendar_config = config["calendar_sync"]["mollee"]
    creds = auth.authenticate("mollee") # Authenticate connection to Google API
    service = build("calendar", "v3", credentials=creds) # Start calendar service 
    sync_from, sync_to = sync_util.get_cal_ids(service=service, name="mollee") # Run setup for cal sync
    CalendarSyncMollee = calendar_sync.CalendarSync("mollee", service=service, task_service=None, sync_from=sync_from, sync_to=sync_to) # CalendarSync object

    # response = input("Perform a reset of mollee sync_to? (y/n): ")
    # if response == "y": CalendarSyncMollee.clear_sync_to()
    
    CalendarSyncMollee.sync_all() # Confirm database, sync_from, and sync_to are synced

if __name__ == "__main__":
    main()