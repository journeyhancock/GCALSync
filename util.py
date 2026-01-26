import json

from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Calendar:
    name: str
    id: str

@dataclass
class CalIds:
    sync_from: List[Calendar] = field(default_factory=list)
    sync_to: Calendar = field(init=False)

def read_file(file_name: str):
    try:
        with open(f"storage/{file_name}.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    
def write_file(file_name: str, data: Dict[str, str]):
    with open(f"storage/{file_name}.json", "w") as f:
        json.dump(data, f)