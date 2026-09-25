"""Run the software society once from a short requirement."""

from __future__ import annotations

import argparse
from pathlib import Path

from conductor.ai.agents import AgentRuntime

from software_society import SOFTWARE_SOCIETY


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--brief", help="Two or three lines of software requirements")
    source.add_argument("--brief-file", type=Path, help="UTF-8 file containing the requirements")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    brief = args.brief if args.brief is not None else args.brief_file.read_text(encoding="utf-8")
    if not brief.strip():
        raise SystemExit("the requirement brief is empty")

    with AgentRuntime() as runtime:
        result = runtime.run(SOFTWARE_SOCIETY, brief.strip())
        result.print_result()
        print(f"execution_id={result.execution_id}")
        print("Observe: conductor agent stream " + result.execution_id)


if __name__ == "__main__":
    main()
