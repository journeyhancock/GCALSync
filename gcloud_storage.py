import json

from google.cloud import storage
from google.api_core.exceptions import NotFound
from typing import Any, Dict

BUCKET = "gcalsync-storage"

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