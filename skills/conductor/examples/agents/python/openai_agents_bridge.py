"""OpenAI Agents SDK on Conductor: change one import.

Install: pip install 'conductor-python[openai-agents]'  (pin versions from the SDK README you fetched)
Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required)

Execution model: COMPILED -- the server maps the OpenAI Agent onto a Conductor graph, so LLM turns
run on the server (OPENAI_API_KEY belongs on the server, not in this process). Any @function_tool
tools become worker tasks and need a serve() process (AgentRuntime().serve(agent)) to execute.
Alternative to the drop-in Runner: pass the OpenAI `Agent` straight to AgentRuntime().run(agent, prompt).
"""
from conductor.ai import Runner
from agents import Agent

agent = Agent(
    name="haiku_agent",
    model="gpt-4o-mini",
    instructions="Answer only in haiku.",
)

result = Runner.run_sync(agent, "Write about durable execution.")
print(result.final_output)
print(result.execution_id)
