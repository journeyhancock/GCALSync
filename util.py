import json

from dataclasses import dataclass, field
from typing import List, Dict, Any

EVENTS_TO_SKIP = {
    "mollee": ["Journey anni <3", "Call mak"],
    "journey": ["Pay Rent", "Off Friday"]
}

@dataclass
class GetEventsResult:
    sync_tokens: Dict[str, str]
    events: List[Any]

@dataclass
class GetTasksResult:
    sync_time: str
    tasks: List[Any]

@dataclass
class Calendar:
    name: str
    id: str

@dataclass
class CalIds:
    sync_from: List[Calendar] = field(default_factory=list)
    sync_to: Calendar = field(init=False)

def read_file(file_name: str, path="storage/"):
    try:
        with open(f"{path}{file_name}.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {path} does not exist")
        return {}
    
def write_file(file_name: str, data: Dict[str, str], path="storage/"):
    with open(f"{path}{file_name}.json", "w") as f:
        json.dump(data, f)

def skip_event(cal_name: str, event_summary: str):
    return event_summary in EVENTS_TO_SKIP[cal_name]