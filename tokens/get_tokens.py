import json
import os

from dataclasses import dataclass
from gcloud_storage import upload_file
from util import read_file
from google.auth.credentials import Credentials as AuthCredentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly",
          "https://www.googleapis.com/auth/cloud-platform"]

@dataclass
class Creds:
    journey_creds: Credentials | AuthCredentials
    mollee_creds: Credentials | AuthCredentials

def ensure_valid(creds: Credentials, name: str, client: storage.Client):
    if not creds.refresh_token:
        return get_refresh_token(name=name, client=client)
    
    if creds.expired:
        try:
            creds.refresh(Request())
        except RefreshError as e:
            print(f"Refresh token invalid for {name} ({e}); rauthorizing")
            return get_refresh_token(name, client)
        
    with open(f"tokens/{name}_creds.json", "w") as f:
        f.write(creds.to_json())

    upload_file(client, f"{name}_creds.json", read_file(f"{name}_creds", path="tokens/"))
        
    return creds

def get_refresh_token(name: str, client: storage.Client):
    client_secret = "tokens/client_secret.json"

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    
    print(f"Please login to the Google Account for {name}")
    creds = flow.run_local_server(
        port=0, 
        open_browser=False,
        prompt="consent",
        access_type="offline"
    )

    print("Access token:", creds.token)
    print("Refresh token:", creds.refresh_token)
    print("Client ID:", creds.client_id)
    print("Client Secret:", creds.client_secret)

    with open(f"tokens/{name}_creds.json", "w") as f:
        f.write(creds.to_json())

    return creds

def get_credentials(client: storage.Client):
    if not os.path.exists("tokens/journey_creds.json"):
        journey_creds = get_refresh_token("journey", client)
        upload_file(client, "journey_creds.json", read_file("journey_creds", path="tokens/"))
    else:
        journey_creds = Credentials.from_authorized_user_file(
            "tokens/journey_creds.json",
            SCOPES
        )
        journey_creds = ensure_valid(journey_creds, "journey", client)

    if not os.path.exists("tokens/mollee_creds.json"):
        mollee_creds = get_refresh_token("mollee", client)
        upload_file(client, "mollee_creds.json", read_file("mollee_creds", path="tokens/"))
    else:
        mollee_creds = Credentials.from_authorized_user_file(
            "tokens/mollee_creds.json",
            SCOPES
        )
        mollee_creds = ensure_valid(mollee_creds, "mollee", client)

    return Creds(journey_creds, mollee_creds)