from dataclasses import dataclass, field
from typing import List

@dataclass
class Calendar:
    name: str
    id: str

@dataclass
class CalIds:
    sync_from: List[Calendar] = field(default_factory=list)
    sync_to: Calendar = field(init=False)