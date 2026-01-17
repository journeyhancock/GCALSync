import json
import os

from dataclasses import dataclass
from google.auth.credentials import Credentials as AuthCredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly"]

@dataclass
class Creds:
    journey_creds: Credentials | AuthCredentials
    mollee_creds: Credentials | AuthCredentials

def get_refresh_token(name: str):
    client_secret = "tokens/client_secret.json"

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=False)

    print("Access token:", creds.token)
    print("Refresh token:", creds.refresh_token)
    print("Client ID:", creds.client_id)
    print("Client Secret:", creds.client_secret)

    creds_dict = {
        "Access Token": creds.token,
        "Refresh Token": creds.refresh_token,
        "Client ID": creds.client_id,
        "Client Secret": creds.client_secret 
    }

    with open(f"tokens/{name}_creds.json", "w") as f:
        json.dump(creds_dict, f)

    return creds

def get_credentials():
    if not os.path.exists("tokens/journey_creds.json"):
        journey_creds = get_refresh_token("journey")
    else:
        with open("tokens/journey_creds.json", "r") as f:
            creds_dict = json.load(f)
            journey_creds = Credentials(
                token=creds_dict["Access Token"],
                token_uri="https://oauth2.googleapis.com/token",
                refresh_token=creds_dict["Refresh Token"],
                client_id=creds_dict["Client ID"],
                client_secret=creds_dict["Client Secret"]
            )

    if not os.path.exists("tokens/mollee_creds.json"):
        mollee_creds = get_refresh_token("mollee")
    else:
        with open("tokens/mollee_creds.json", "r") as f:
            creds_dict = json.load(f)
            mollee_creds = Credentials(
                token=creds_dict["Access Token"],
                token_uri="https://oauth2.googleapis.com/token",
                refresh_token=creds_dict["Refresh Token"],
                client_id=creds_dict["Client ID"],
                client_secret=creds_dict["Client Secret"]
            )

    return Creds(journey_creds, mollee_creds)