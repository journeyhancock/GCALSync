import json

from googleapiclient.errors import HttpError

# Get ids of all relevant calendars
def get_cal_ids(service, name):
     sync_from = {}
     sync_to = ()

     with open("config.json", "r") as json_config:
        config = json.load(json_config)

        sync_from_names = config["calendar_sync"][name]["sync_from"]
        sync_to_name = config["calendar_sync"][name]["sync_to"]
        try:
            cals = service.calendarList().list().execute()
            for cal in cals["items"]:
                cal_name = cal["summary"]
                if cal_name.lower() in sync_from_names:
                    sync_from[cal_name] = cal["id"]
                elif cal_name.lower() == sync_to_name:
                    sync_to = (cal_name, cal["id"])

        except HttpError as error:
            print(f"An error occurred: {error}")
            
        return sync_from, sync_to