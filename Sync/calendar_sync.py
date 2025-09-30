import datetime
import json

from collections import defaultdict
from Database.setup import JourneyEventMap, MolleeEventMap, TasksDayEventMap, get_session
from zoneinfo import ZoneInfo

class CalendarSync:
    def __init__(self, name, service, task_service, sync_from, sync_to):
        self.name = name
        self.service = service
        self.task_service = task_service
        self.sync_from = sync_from
        self.sync_to = sync_to

    # Check database, tasks, and sync_to TODO events are synced
    def sync_tasks(self):
        now = datetime.datetime.now(tz=ZoneInfo("America/Phoenix")).isoformat()
        day = now[:11] + "00:00:00.000Z"

        tasks = defaultdict(list)
        page_token = None
        while True:
            tasks_result = self.task_service.tasks().list(
                tasklist="@default",
                showHidden=True,
                showCompleted=True,
                pageToken=page_token
            ).execute()

            for task in tasks_result.get("items", []):
                due_time = task["due"]
                if due_time >= day: tasks[due_time[:11] + "00:00:00.000Z"].append(task)

            page_token = tasks_result.get("nextPageToken")
            if not page_token: break

        todo_events = {}
        events_result = self.service.events().list(
            calendarId=self.sync_to[1],
            singleEvents=True,
            timeMin=day
        ).execute()
        for event in events_result.get("items", []):
            if event["summary"] == "TODO": todo_events[event["id"]] = event

        session = get_session()
        try:
            mappings = session.query(TasksDayEventMap)
            db_mapping = {str(m.day) : str(m.event_id) for m in mappings}
        finally:
            session.close()

        for day, task_list in tasks.items():
            names_list = []
            for task in task_list: names_list.append(task["title"])

            formatted_task_list = []
            for task in task_list:
                if task["status"] == "completed":
                    formatted_task_list.append(f"<s>{task['title']}</s>")
                else:
                    formatted_task_list.append(task["title"])
            new_task_list = "\n".join(formatted_task_list)

            if day in db_mapping:
                todo_event_id = db_mapping[day]
                
                todo_event = self.service.events().get(
                    calendarId=self.sync_to[1],
                    eventId=todo_event_id
                ).execute()

                curr_task_list = todo_event["description"]
                if curr_task_list != new_task_list:
                    updated_event = self.service.events().patch(
                        calendarId=self.sync_to[1],
                        eventId=todo_event_id,
                        body={"description" : new_task_list}
                    ).execute()
            else:
                new_event = {
                    "summary" : "TODO",
                    "start" : {"dateTime" : day[:11] + "06:00:00.000", "timeZone" : "America/Phoenix"},
                    "end" : {"dateTime" : day[:11] + "06:00:30.000", "timeZone" : "America/Phoenix"},
                    "description" : new_task_list 
                }

                created_event = self.service.events().insert(
                    calendarId=self.sync_to[1],
                    body=new_event
                ).execute()
                created_event_id = created_event["id"]

                session = get_session()
                try:
                    mapping = TasksDayEventMap(
                        day=day,
                        event_id=created_event_id,
                        last_synced=datetime.datetime.now(tz=datetime.timezone.utc)
                    )
                    session.add(mapping)
                    session.commit()
                finally:
                    session.close()

        # if length of TODO events is larger than the length of tasks then delete the blank TODO
        swapped_db_mapping = {value: key for key, value in db_mapping.items()}
        if len(todo_events) > len(tasks):
            for todo_event_id in todo_events.keys():                
                day = swapped_db_mapping.get(todo_event_id)
                if day is not None and day not in tasks:
                    self.service.events().delete(
                        calendarId=self.sync_to[1],
                        eventId=todo_event_id
                    ).execute()

                    session = get_session()
                    try:
                        mapping = session.query(TasksDayEventMap).filter_by(day=day).first()
                        if mapping:
                            session.delete(mapping)
                            session.commit()
                    finally:
                        session.close()