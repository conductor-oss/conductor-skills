"""Serve the society's Python tools as a long-lived worker process."""

from conductor.ai.agents import AgentRuntime

from software_society import SOFTWARE_SOCIETY


def main() -> None:
    with AgentRuntime() as runtime:
        runtime.serve(SOFTWARE_SOCIETY)


if __name__ == "__main__":
    main()
