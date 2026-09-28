"""LangChain agent on Conductor.

Install: pip install 'conductor-python[langchain]' langchain-openai  (pin from the SDK README you fetched)
Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required)

Why `conductor.ai.agents.langchain.create_agent` and NOT `langchain.agents.create_agent`:
the Conductor drop-in stamps metadata (model, tools, system prompt) on the graph so the server can
extract it fully and COMPILE it into a Conductor graph. The plain LangChain builder returns a
CompiledStateGraph that is detected as LangGraph and may fall back to PASSTHROUGH -- the whole agent
loop then runs inside one worker task. Passthrough agents progress ONLY while `runtime.serve(graph)`
is running; for them serve() is mandatory, not optional.
"""
from conductor.ai.agents import AgentRuntime
from conductor.ai.agents.langchain import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


@tool
def get_weather(city: str) -> str:
    """Return the current weather for a city."""
    # Idempotent: safe for Conductor to retry on failure or timeout.
    return f"{city}: Sunny, 21C"


graph = create_agent(
    ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=[get_weather],
    name="langchain_assistant",
    system_prompt="You are a concise assistant. Use get_weather for weather questions.",
)

with AgentRuntime() as runtime:
    result = runtime.run(graph, "What is the weather in San Francisco?")
    result.print_result()
