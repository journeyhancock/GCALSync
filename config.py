from dataclasses import dataclass
from googleapiclient.errors import HttpError
from typing import List
from util import CalIds, Calendar

@dataclass(frozen=True)
class JourneyConfig:
    sync_from: tuple[str, ...] = ("classes", "clubs", "career", "personal")
    sync_to: str = "journey!!"

@dataclass(frozen=True)
class MolleeConfig:
    sync_from: tuple[str, ...] = ("ca", "wclax '25-'26", "wclax '25-'26 eboard", "classes", "mjkahan3@gmail.com", "mjkahan@asu.edu")
    sync_to: str = "mollee :)"

def get_cal_ids(service, name: str) -> CalIds:
    config = JourneyConfig() if name == "journey" else MolleeConfig()
    ids = CalIds()

    try:
        calendars = service.calendarList().list().execute()
        for calendar in calendars["items"]:
            calendar_name = calendar["summary"]
            if calendar_name.lower() in config.sync_from:
                ids.sync_from.append(Calendar(calendar_name, calendar["id"]))
            elif calendar_name.lower() == config.sync_to:
                ids.sync_to = Calendar(calendar_name, calendar["id"])
    except HttpError as error:
        print(error)

    return ids
