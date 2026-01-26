import json
import logging

from google.cloud import storage
from google.api_core.exceptions import NotFound
from typing import Any, Dict
from util import write_file, read_file

BUCKET = "gcalsync-storage"
logger = logging.getLogger(__name__)

def download_file(client: storage.Client, file: str) -> Dict[str, str]:
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(file)

    try: 
        data = blob.download_as_text()
        return json.loads(data)
    except NotFound:
        return {}
    
def upload_file(client: storage.Client, file: str, data: Dict[str, str]) -> None:
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(file)

    blob.upload_from_string(
        json.dumps(data, indent=2),
        content_type="application/json"
    )

def update_local_files(client: storage.Client):
    logging.info("Updating local files")

    # mappings
    write_file("journey_events", download_file(client, "journey_events.json"))
    logging.info("Downloaded Journey event mapping")

    write_file("mollee_events", download_file(client, "mollee_events.json"))
    logging.info("Downloaded Mollee event mapping")

    write_file("days_events", download_file(client, "days_events.json"))
    logging.info("Downloaded days events mapping")

    write_file("tasks_events", download_file(client, "tasks_events.json"))
    logging.info("Downloaded tasks events mapping")

    # sync tokens
    write_file("journey_event_tokens", download_file(client, "journey_event_tokens.json"))
    logging.info("Downloaded Journey event tokens")

    write_file("mollee_event_tokens", download_file(client, "mollee_event_tokens.json"))
    logging.info("Downloaded Mollee event tokens")

    write_file("tasks_sync_time", download_file(client, "tasks_sync_time.json"))
    logging.info("Downloaded task sync time")

def update_cloud_files(client: storage.Client):
    # mappings
    upload_file(client, "journey_events.json", read_file("journey_events"))
    logging.info("Uploaded Journey event mapping")

    upload_file(client, "mollee_events.json", read_file("mollee_events"))
    logging.info("Uploaded Mollee event mapping")

    upload_file(client, "days_events.json", read_file("days_events"))
    logging.info("Uploaded days events mapping")

    upload_file(client, "tasks_events.json", read_file("tasks_events"))
    logging.info("Uploaded tasks events mapping")

    # sync tokens
    upload_file(client, "journey_event_tokens.json", read_file("journey_event_tokens"))
    logging.info("Uploaded Journey event tokens")

    upload_file(client, "mollee_event_tokens.json", read_file("mollee_event_tokens"))
    logging.info("Uploaded Mollee event tokens")

    upload_file(client, "tasks_sync_time.json", read_file("tasks_sync_time"))
    logging.info("Uploaded tasks sync time")