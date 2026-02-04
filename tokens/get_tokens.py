import json
import os

from dataclasses import dataclass
from google.auth.credentials import Credentials as AuthCredentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly",
          "https://www.googleapis.com/auth/cloud-platform"]

@dataclass
class Creds:
    journey_creds: Credentials | AuthCredentials
    mollee_creds: Credentials | AuthCredentials

def ensure_valid(creds: Credentials, name: str):
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(f"tokens/{name}_creds.json", "w") as f:
            f.write(creds.to_json())

def get_refresh_token(name: str):
    client_secret = "tokens/client_secret.json"

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
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

def get_credentials():
    if not os.path.exists("tokens/journey_creds.json"):
        journey_creds = get_refresh_token("journey")
    else:
        journey_creds = Credentials.from_authorized_user_file(
            "tokens/journey_creds.json",
            SCOPES
        )
        ensure_valid(journey_creds, "journey")

    if not os.path.exists("tokens/mollee_creds.json"):
        mollee_creds = get_refresh_token("mollee")
    else:
        mollee_creds = Credentials.from_authorized_user_file(
            "tokens/mollee_creds.json",
            SCOPES
        )
        ensure_valid(mollee_creds, "mollee")

    return Creds(journey_creds, mollee_creds)