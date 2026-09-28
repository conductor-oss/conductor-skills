"""Start the durable writers' room workflow from a mission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--mission")
    source.add_argument("--mission-file", type=Path)
    parser.add_argument("--conductor-api", default="http://localhost:8080/api")
    args = parser.parse_args()
    mission = args.mission or args.mission_file.read_text(encoding="utf-8")
    if not mission.strip():
        raise SystemExit("mission must not be empty")
    workflow_input = json.dumps(
        {"mission": mission.strip(), "conductorApi": args.conductor_api.rstrip("/")}
    )
    subprocess.run(
        [
            "conductor",
            "workflow",
            "start",
            "-w",
            "bengaluru_writers_room_delivery",
            "-i",
            workflow_input,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
