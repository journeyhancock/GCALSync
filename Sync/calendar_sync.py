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

    # Check database, sync_from calendars, and sync_to calendar are synced
    def sync_all(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        
        # Get all events from sync_from calendars
        sync_from_events = {}
        for cal_name, cal_id in self.sync_from.items():
            events_result = self.service.events().list(
                calendarId=cal_id,
                singleEvents=True,
                timeMin=now
            ).execute()
            events = events_result.get("items", [])
            for event in events: sync_from_events[event["id"]] = event

        # Get all events from sync_to calendar
        sync_to_events = {}
        events_result = self.service.events().list(
            calendarId=self.sync_to[1],
            singleEvents=True,
            timeMin=now
        ).execute()
        events = events_result.get("items", [])
        for event in events: sync_to_events[event["id"]] = event

        # Get current database mapping of sync_from to sync_to events
        session = get_session()
        try:
            if self.name == "journey":
                mappings = session.query(JourneyEventMap).all()
            else:
                mappings = session.query(MolleeEventMap).all()
            db_mapping = {m.original_event_id : m.new_event_id for m in mappings}
        finally:
            session.close()

        for sync_from_id, sync_from_event in sync_from_events.items():
            # If sync from event has a sync to event, check for updates and update sync_to event if necessary
            if sync_from_id in db_mapping:
                sync_to_id = db_mapping[sync_from_id]
                sync_to_event = sync_to_events[sync_to_id]
                
                changed = False
                if sync_from_event.get("summary") != sync_to_event.get("summary"): 
                    sync_to_event["summary"] = sync_from_event.get("summary")
                    changed = True
                if sync_from_event.get("start") != sync_to_event.get("start"): 
                    sync_to_event["start"] = sync_from_event.get("start")
                    changed = True
                if sync_from_event.get("end") != sync_to_event.get("end"): 
                    sync_to_event["end"] = sync_from_event.get("end")
                    changed = True

                if changed:
                    updated_event = self.service.events().patch(
                        calendarId=self.sync_to[1],
                        eventId=sync_to_id,
                        body=sync_to_event
                    ).execute()

            # If sync_from event does not have a sync_to event, add the event to sync_to 
            # and the id mapping to the database
            else:
                new_event = {
                    "summary" : sync_from_event.get("summary"),
                    "start" : sync_from_event.get("start"),
                    "end" : sync_from_event.get("end")
                }

                created_event = self.service.events().insert(
                    calendarId=self.sync_to[1],
                    body=new_event
                ).execute()

                session = get_session()
                try:
                    if self.name == "journey":
                        mapping = JourneyEventMap(
                            original_event_id=sync_from_id,
                            new_event_id=created_event["id"],
                            last_synced=datetime.datetime.now(tz=datetime.timezone.utc)
                        )
                    else:
                        mapping = MolleeEventMap(
                            original_event_id=sync_from_id,
                            new_event_id=created_event["id"],
                            last_synced=datetime.datetime.now(tz=datetime.timezone.utc)
                        )

                    session.add(mapping)
                    session.commit()
                finally:
                    session.close()

        # Investigate possible deleted event
        swapped_db_mapping = {value: key for key, value in db_mapping.items()}
        if len(sync_to_events) > len(sync_from_events):
            for sync_to_event_id in sync_to_events.keys():
                sync_from_event_id = swapped_db_mapping.get(sync_to_event_id)

                if sync_from_event_id is not None:
                    if sync_from_event_id not in sync_from_events.keys():
                        session = get_session()

                        try:
                            if self.name == "journey":
                                mapping = session.query(JourneyEventMap).filter_by(original_event_id=sync_from_event_id).first()
                            else:
                                mapping = session.query(MolleeEventMap).filter_by(original_event_id=sync_from_event_id).first()
                            if mapping:
                                session.delete(mapping)
                                session.commit()
                        finally:
                            session.close()

                        self.service.events().delete(
                            calendarId=self.sync_to[1],
                            eventId=sync_to_event_id
                        ).execute()
                else:
                    if sync_to_events[sync_to_event_id]["summary"] != "TODO":
                        self.service.events().delete(
                            calendarId=self.sync_to[1],
                            eventId=sync_to_event_id
                        ).execute()