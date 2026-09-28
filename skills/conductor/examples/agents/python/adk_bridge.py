"""Google ADK agent on Conductor (verbatim from the server UI quickstart).

Install: pip install 'conductor-python[adk]'  (pin versions from the SDK README you fetched)
Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required)

The ADK model name is normalized to the provider-qualified form `google_gemini/gemini-2.0-flash`
on the server, so the server needs GEMINI_API_KEY (not this process). Execution model: COMPILED;
ADK function tools become worker tasks that need runtime.serve(agent).
"""
from conductor.ai.agents import AgentRuntime
from google.adk.agents import Agent

agent = Agent(
    name="adk_greeter",
    model="gemini-2.0-flash",
    instruction="You are friendly and concise.",
)

with AgentRuntime() as runtime:
    result = runtime.run(agent, "Say hello and share an ML fact.")
    result.print_result()
