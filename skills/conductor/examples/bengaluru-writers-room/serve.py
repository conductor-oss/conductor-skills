"""Serve the writers' room research and publishing workers."""

from conductor.ai.agents import AgentRuntime

from writers_room import WRITERS_ROOM_PHASES


def main() -> None:
    with AgentRuntime() as runtime:
        runtime.serve(*WRITERS_ROOM_PHASES)


if __name__ == "__main__":
    main()
