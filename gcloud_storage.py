import json
import logging
import os

from google.cloud import storage
from google.api_core.exceptions import NotFound
from typing import Any, Dict
from util import write_file, read_file

PROJECT = "quiet-engine-471620-s7"
BUCKET = "gcalsync-storage"

# Local disk is the source of truth
STATE_FILES = ("journey_events",
               "mollee_events",
               "days_events",
               "tasks_events",
               "journey_event_tokens",
               "mollee_event_tokens",
               "tasks_sync_time")

CRED_FILES = ("journey_creds", "mollee_creds")

logger = logging.getLogger(__name__)

def get_client() -> storage.Client:
    return storage.Client(project=PROJECT)

def download_file(client: storage.Client, file: str) -> Dict[str, Any]:
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(file)

    try:
        data = blob.download_as_text()
        return json.loads(data)
    except NotFound:
        return {}
    except json.JSONDecodeError:
        logger.warning(f"Stored {file} is not valid JSON; ignoring it")
        return {}

def upload_file(client: storage.Client, file: str, data: Dict[str, Any]) -> None:
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(file)

    blob.upload_from_string(
        json.dumps(data, indent=2),
        content_type="application/json"
    )

def has_refresh_token(data: Dict[str, Any]) -> bool:
    return bool(data.get("refresh_token"))

def _state_is_usable(name: str, path: str) -> bool:
    # An empty mapping written by a wipe is meaningful, so existence is the test.
    return os.path.exists(f"{path}{name}.json")

def _creds_are_usable(name: str, path: str) -> bool:
    return has_refresh_token(read_file(name, path=path))

def _restore(client: storage.Client, name: str, path: str, is_creds: bool) -> None:
    if (_creds_are_usable if is_creds else _state_is_usable)(name, path):
        logger.debug(f"Keeping local {name}")
        return

    remote = download_file(client, f"{name}.json")

    if is_creds and not has_refresh_token(remote):
        logger.warning(f"No usable stored credentials for {name} in the bucket")
        return

    write_file(name, remote, path=path)
    logger.info(f"Restored {name} from the bucket")

def _backup(client: storage.Client, name: str, path: str, is_creds: bool) -> None:
    if not (_creds_are_usable if is_creds else _state_is_usable)(name, path):
        logger.warning(f"Local {name} is missing or invalid; skipping upload")
        return

    upload_file(client, f"{name}.json", read_file(name, path=path))
    logger.info(f"Uploaded {name}")

def update_local_files(client: storage.Client):
    logger.info("Updating local files")

    for name in STATE_FILES:
        _restore(client, name, "storage/", is_creds=False)

    for name in CRED_FILES:
        _restore(client, name, "tokens/", is_creds=True)

def update_cloud_files(client: storage.Client):
    logger.info("Updating cloud files")

    for name in STATE_FILES:
        _backup(client, name, "storage/", is_creds=False)

    for name in CRED_FILES:
        _backup(client, name, "tokens/", is_creds=True)
