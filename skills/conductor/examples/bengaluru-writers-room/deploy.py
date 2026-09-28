"""Compile or deploy the Bengaluru writers' room."""

from __future__ import annotations

import argparse
import json

from conductor.ai.agents import AgentRuntime

from writers_room import WRITERS_ROOM_PHASES
from writers_room.agents import all_agent_objects, specialist_agents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    with AgentRuntime() as runtime:
        plans = {agent.name: runtime.plan(agent) for agent in WRITERS_ROOM_PHASES}
        summary = {
            "agents": list(plans),
            "totalAgentObjects": len(all_agent_objects()),
            "specialists": len(specialist_agents()),
            "requiredWorkers": sorted(
                {
                    worker
                    for plan in plans.values()
                    for worker in plan.get("requiredWorkers", [])
                }
            ),
        }
        print(json.dumps(summary, indent=2))
        if not args.plan_only:
            print(runtime.deploy(*WRITERS_ROOM_PHASES))


if __name__ == "__main__":
    main()
