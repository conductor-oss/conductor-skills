"""Compile and deploy the software society; run once in CI/release automation."""

from __future__ import annotations

import argparse
import json

from conductor.ai.agents import AgentRuntime

from software_society import SOFTWARE_SOCIETY


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true", help="Compile without registering")
    args = parser.parse_args()

    with AgentRuntime() as runtime:
        plan = runtime.plan(SOFTWARE_SOCIETY)
        required_workers = plan.get("requiredWorkers", [])
        print(json.dumps({"agent": SOFTWARE_SOCIETY.name, "requiredWorkers": required_workers}, indent=2))
        if args.plan_only:
            return
        deployment = runtime.deploy(SOFTWARE_SOCIETY)
        print(f"deployed={SOFTWARE_SOCIETY.name}")
        print(f"deployment={deployment}")


if __name__ == "__main__":
    main()
