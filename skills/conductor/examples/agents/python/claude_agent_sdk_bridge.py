"""Claude Agent SDK on Conductor (verbatim from the server UI quickstart).

Install: pip install 'conductor-python[claude]'  (pin versions from the SDK README you fetched)
Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required); ANTHROPIC_API_KEY where
         this process runs, because the loop executes here (see below).

PASSTHROUGH: the whole agent loop runs inside runtime.serve(); the server sees a single worker task.
Nothing progresses unless a serve() process is running. `tools` must be built-in Claude tool names
(Read, Glob, Grep, ...), not Python functions.
"""
from conductor.ai.agents import Agent, AgentRuntime, ClaudeCode

agent = Agent(
    name="claude_code_assistant",
    model=ClaudeCode("sonnet"),
    instructions="Inspect the repository and answer concisely.",
    tools=["Read", "Glob", "Grep"],
)

with AgentRuntime() as runtime:
    result = runtime.run(agent, "Summarize this repository.")
    result.print_result()
