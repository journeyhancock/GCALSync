import argparse
import json
import logging
import os
import stat

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from gcloud_storage import get_client, upload_file
from google.auth.credentials import Credentials as AuthCredentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.external_account_authorized_user import Credentials as UserCredentials

# cloud-platform is deliberately absent: the bucket is reached through
# Application Default Credentials, never through the user's token.
SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/tasks.readonly"]

ACCOUNTS = ("journey", "mollee")

# Re-authorizing needs a browser. On the Pi there isn't one, so fail loudly
# instead of blocking forever on a local server nobody can reach.
HEADLESS = os.getenv("HEADLESS", "").lower() in ("1", "true", "yes")

# Fixed so it can be registered as a redirect URI and forwarded over SSH,
# rather than landing on a random port each time.
OAUTH_PORT = 8080

# Refresh a little early so a long run can't expire mid-sync.
REFRESH_MARGIN = timedelta(minutes=10)

logger = logging.getLogger(__name__)

class ReauthRequired(Exception):
    """Consent is needed but no browser is available."""

@dataclass
class Creds:
    journey_creds: Credentials | AuthCredentials | UserCredentials
    mollee_creds: Credentials | AuthCredentials | UserCredentials

def creds_path(name: str) -> str:
    return f"tokens/{name}_creds.json"

def save_creds(creds: Credentials | UserCredentials, name: str, client: storage.Client) -> None:
    data = creds.to_json()
    path = creds_path(name)

    with open(path, "w") as f:
        f.write(data)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    upload_file(client, f"{name}_creds.json", json.loads(data))
    logger.info(f"Saved credentials for {name}")

def needs_refresh(creds: Credentials) -> bool:
    if not creds.token or creds.expiry is None:
        return True

    # google-auth stores expiry as a naive UTC datetime.
    expiry = creds.expiry.replace(tzinfo=timezone.utc)

    return expiry - datetime.now(timezone.utc) < REFRESH_MARGIN

def ensure_valid(creds: Credentials, name: str, client: storage.Client) -> Credentials | UserCredentials:
    if not creds.refresh_token:
        logger.warning(f"No refresh token stored for {name}; reauthorizing")
        return get_refresh_token(name, client)

    if not needs_refresh(creds):
        return creds

    logger.info(f"Refreshing access token for {name}")
    try:
        creds.refresh(Request())
    except RefreshError as e:
        logger.warning(f"Refresh token invalid for {name} ({e}); reauthorizing")
        return get_refresh_token(name, client)

    # Google can rotate the refresh token on refresh, so persist right away
    # instead of waiting for the upload at the end of the run.
    save_creds(creds, name, client)

    return creds

def get_refresh_token(name: str, client: storage.Client) -> Credentials | UserCredentials:
    if HEADLESS:
        raise ReauthRequired(
            f"{name} needs to reauthorize, but this host is headless. Run "
            f"'python -m tokens.get_tokens --account {name}' on a machine with "
            f"a browser; the Pi will pick up the new token from the bucket."
        )

    flow = InstalledAppFlow.from_client_secrets_file("tokens/client_secret.json", SCOPES)

    print(f"Please login to the Google Account for {name}")

    try:
        creds = flow.run_local_server(
            port=OAUTH_PORT,
            open_browser=False,
            prompt="consent",
            access_type="offline"
        )
    except OSError:
        # If port in use, re-run with no specified port
        creds = flow.run_local_server(
            open_browser=False,
            prompt="consent",
            access_type="offline"
        )

    save_creds(creds, name, client)

    return creds

def load_creds(name: str, client: storage.Client) -> Credentials | UserCredentials:
    path = creds_path(name)

    try:
        with open(path, "r") as f:
            info = json.load(f)
    except FileNotFoundError:
        logger.info(f"No stored credentials for {name}")
        return get_refresh_token(name, client)
    except json.JSONDecodeError:
        logger.warning(f"Credentials for {name} are not valid JSON; reauthorizing")
        return get_refresh_token(name, client)

    if not info.get("refresh_token"):
        logger.warning(f"Credentials for {name} have no refresh token; reauthorizing")
        return get_refresh_token(name, client)

    # A scope added to SCOPES later needs fresh consent; catch it here rather
    # than as a confusing 403 partway through a sync.
    missing = set(SCOPES) - set(info.get("scopes", []))
    if missing:
        logger.warning(f"Credentials for {name} are missing {sorted(missing)}; reauthorizing")
        return get_refresh_token(name, client)

    return ensure_valid(Credentials.from_authorized_user_info(info, SCOPES), name, client)

def get_credentials(client: storage.Client) -> Creds:
    return Creds(
        journey_creds=load_creds("journey", client),
        mollee_creds=load_creds("mollee", client)
    )

def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="Authorize a Google account for GCALSync")
    parser.add_argument("--account", choices=ACCOUNTS, required=True)
    args = parser.parse_args()

    if HEADLESS:
        raise SystemExit("HEADLESS is set; unset it to authorize interactively")

    get_refresh_token(args.account, get_client())

if __name__ == "__main__":
    main()
