import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly"]

def authenticate(name):
    creds = None

    if os.path.exists(f"token_{name}.json"):
        creds = Credentials.from_authorized_user_file(f"token_{name}.json")
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open(f"token_{name}.json", "w") as token:
            token.write(creds.to_json())

    return creds