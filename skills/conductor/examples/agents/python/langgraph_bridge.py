"""LangGraph graph on Conductor (verbatim from the server UI quickstart).

Install: pip install 'conductor-python[langgraph]'  (pin versions from the SDK README you fetched)
Env:     CONDUCTOR_SERVER_URL (+ CONDUCTOR_AUTH_KEY/SECRET if required)

Execution model: a `create_react_agent(...)` graph whose model can be read is COMPILED into a Conductor
graph (LLM turns on the server; tool functions become worker tasks served by runtime.serve(graph)).
Complex or opaque graphs fall back to PASSTHROUGH: the whole loop runs inside one worker, so
runtime.serve(graph) must be running or the agent never progresses.
"""
from conductor.ai.agents import AgentRuntime
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

graph = create_react_agent(
    ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=[],
    name="langgraph_assistant",
)

with AgentRuntime() as runtime:
    result = runtime.run(graph, "What makes a workflow durable?")
    result.print_result()
