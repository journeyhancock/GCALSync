# GCALSync

A python app to sync events across a user's different google calendars into one calendar for easy sharing.

## Setup

If using yourself, you'll need to create a project in the Google API dashboard and enable the Calendar API and Tasks API. Then download your client secret and move it into the project as `tokens/client_secret.json`. Run:

```
python -m tokens.get_tokens --account <name>
```

to create a refresh token so you only have to do the OAuth login once. Make sure the OAuth consent screen is set to "In production" - refresh tokens issued while it is in "Testing" expire after 7 days.

After that, edit the config in `config.py`:
- `sync_from` - the names of the calendars you want to pull events from
- `sync_to` - the name of the calendar you want events to go in to (task TODO events go here too, if you use tasks)

If syncing issues arise, edit the wipe if-statements in `main.py` to be `True`. Run `main.py` and then everything should be resynced. Change all the wipe if-statements back to `False` and continue as normal.

I would recommend running the pruning every couple days just to make sure the mapping json files don't get oversized.

Sync tokens and event/task ids are useless without an OAuth token.

## Running it

`python main.py` does a single full sync and exits. Good for testing and for the wipe/prune operations.

`python daemon.py` runs forever, polling calendars every `CALENDAR_INTERVAL` seconds (default 300) and tasks every `TASKS_INTERVAL` seconds (default 300). Tasks has no push API, and sync tokens make each calendar poll cheap, so polling both is simpler than a webhook - no public endpoint, no certificate, no notification channels to renew.

Both jobs run on a single thread. Never run `daemon.py` and `main.py` at the same time against the same calendars: they share every state file in `storage/` and would race each other's mappings.

## Dashboard

`daemon.py` also starts a small in-process web dashboard (see `dashboard.py`) so you can check the daemon's health without SSHing in and grepping logs.

- Listens on the host's `wlan0` IP (Linux only - it shells out to `ip addr show wlan0`), on port `DASHBOARD_PORT` (default `2727`).
- Shows the status (`OK` / `ERROR` / `STALE`) and log output of the most recent poll cycle, refreshing every 30s.
- If the dashboard fails to bind, the whole daemon fails to start and systemd restarts it, rather than running silently without a dashboard - an unreachable dashboard is meant to read as "service down".
- If you're running `daemon.py` somewhere without a `wlan0` interface (e.g. not a Raspberry Pi), you'll need to change how the bind address is resolved in `daemon.py`/`dashboard.py`.

## State

Local disk is the source of truth. The `gcalsync-storage` bucket is a backup that is only read back when a local file is missing, so a stale or empty bucket copy can never overwrite good local state. That means two hosts running against the same calendars will diverge - pick one.

Credentials are the exception: if a refresh token stops working, the daemon checks the bucket for a different one before giving up. So to fix a dead token, reauthorize on a machine with a browser (`python -m tokens.get_tokens --account NAME`), which uploads it, and the Pi picks it up on its next attempt.

## Headless hosts (Raspberry Pi)

Set `HEADLESS=1`. Any reauthorization then raises instead of blocking forever on a local OAuth server nothing can reach, and `daemon.py` exits 1 so systemd retries.

Bucket access uses Application Default Credentials, not the user's OAuth token. Create a service account, grant it Storage Object Admin on the `gcalsync-storage` bucket only, put the key at `tokens/service_account.json`, and point `GOOGLE_APPLICATION_CREDENTIALS` at it. Service account keys don't expire.

### Setup

```
git clone <repo> /home/user/GCALSync
cd /home/user/GCALSync
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# copy these over from a machine that has already authorized:
#   tokens/client_secret.json
#   tokens/service_account.json
# the creds themselves come down from the bucket on first run

sudo cp gcalsync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gcalsync

journalctl -u gcalsync -f
```

Edit `gcalsync.service` first if your user or path is not `/home/user`.

Once it's running, the dashboard is reachable at `http://<pi's wlan0 ip>:2727` (or whatever `DASHBOARD_PORT` you set) from any device on the same network.

### To change an already registered service

```
sudo cp gcalsync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart gcalsync
```
