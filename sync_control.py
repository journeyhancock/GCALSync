"""Hand state between the Pi and a local dev machine.

daemon.py never touches the bucket for state - only for credential
refresh/recovery. Use this to move state through it deliberately:

  pause   push local state to the bucket and stop the systemd service
          (run this on the Pi before syncing/testing from another machine)
  resume  pull state back down from the bucket and start the service
          (run this on the Pi to hand control back to it)

main.py already downloads on start and uploads on exit, so a normal
"python main.py" run on your dev machine is the other half of the handoff.
"""

import argparse
import logging
import subprocess

from gcloud_storage import get_client, update_cloud_files, update_local_files

SERVICE = "gcalsync"

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def systemctl(action: str) -> None:
    subprocess.run(["sudo", "systemctl", action, SERVICE], check=True)


def pause() -> None:
    client = get_client()

    logger.info("Uploading local state to the bucket")
    update_cloud_files(client=client)

    logger.info(f"Stopping {SERVICE}")
    systemctl("stop")


def resume() -> None:
    client = get_client()

    logger.info("Downloading state from the bucket")
    update_local_files(client=client)

    logger.info(f"Starting {SERVICE}")
    systemctl("start")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["pause", "resume"])
    args = parser.parse_args()

    {"pause": pause, "resume": resume}[args.action]()


if __name__ == "__main__":
    main()
