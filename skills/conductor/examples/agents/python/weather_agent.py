"""Native Conductor Agent scaffold: one read-only tool, one approval-gated tool.

Prerequisites
  Server: conductor.integrations.ai.enabled=true (set automatically by `conductor server start`)
          and OPENAI_API_KEY exported where the server runs. Provider keys live on the server.
  Client: pip install 'conductor-python[agents]' -- pin versions from the SDK README you fetched.
  Env:    CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if the server requires auth).

Usage
  python weather_agent.py run "Weather in SF?"  # register-if-needed + execute once
  python weather_agent.py plan                   # compile only: workflowDef + requiredWorkers
  python weather_agent.py deploy                 # register the named agent; nothing executes
  python weather_agent.py serve                  # long-lived worker process for the @tool functions
"""
import sys

from conductor.ai.agents import Agent, AgentRuntime, tool


@tool
def get_weather(city: str) -> dict:
    """Return the current weather for a city. Read-only."""
    # Tool workers must be idempotent: Conductor retries a tool task on failure or timeout.
    return {"city": city, "condition": "Sunny", "temperature_c": 21}


@tool(approval_required=True)
def notify_ops(message: str) -> dict:
    """Page the on-call operator. Side effect: a human approves each call."""
    # The run reports waiting=true with pendingTool.toolCalls[0].name == "notify_ops" (tool_name is null
    # for compiled agents) until an operator approves (`conductor agent respond <id> --approve`) or rejects.
    # Resume-with-prompt is only LLM-interpreted at a gate — not the approval channel.
    return {"sent": True, "message": message}


agent = Agent(
    name="weather_agent",
    model="openai/gpt-4o-mini",  # always provider/model; the SDK core does not read CONDUCTOR_AGENT_LLM_MODEL
    instructions="Answer weather questions with get_weather. Call notify_ops only for severe conditions.",
    tools=[get_weather, notify_ops],
    max_turns=10,
)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "run"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "What is the weather in San Francisco?"

    with AgentRuntime() as runtime:
        if command == "run":
            result = runtime.run(agent, prompt)
            result.print_result()
            print(result.execution_id)  # a workflow id: `conductor workflow get-execution <id>`
        elif command == "plan":
            print(runtime.plan(agent))  # {"workflowDef": {...}, "requiredWorkers": [...]}
        elif command == "deploy":
            runtime.deploy(agent)  # registers only; tool tasks sit SCHEDULED until something serves them
            print("required workers:", runtime.plan(agent).get("requiredWorkers", []))
        elif command == "serve":
            runtime.serve(agent)  # blocks; run as a long-lived process (container, systemd, ...)
        else:
            raise SystemExit(f"unknown command {command!r}; use run|plan|deploy|serve")


if __name__ == "__main__":
    main()
