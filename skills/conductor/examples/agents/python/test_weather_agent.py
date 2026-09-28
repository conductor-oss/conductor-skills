"""Tests for weather_agent.py.

Offline test: mock_run replays scripted events -- no server, no LLM, no provider key.
Live test (opt-in, `pytest -m live`): needs a reachable Conductor server with the agent runtime
enabled and OPENAI_API_KEY configured on the server. Register the `live` marker in pytest.ini.

Install: pip install 'conductor-python[agents]' pytest
Confirm the MockEvent factory names (thinking / tool_call / done) against the SDK docs you fetched
(python-sdk/docs/agents/); they may change between releases.
"""
import pytest

from conductor.ai.agents import AgentRuntime
from conductor.ai.agents.testing import CorrectnessEval, EvalCase, MockEvent, expect, mock_run

from weather_agent import agent


def test_uses_weather_tool_offline():
    result = mock_run(
        agent,
        "Weather in SF?",
        events=[
            MockEvent.tool_call("get_weather", {"city": "San Francisco"}),
            MockEvent.done("Sunny."),
        ],
    )
    expect(result).completed().used_tool("get_weather").no_errors()


@pytest.mark.live
def test_correctness_live():
    # Worker tools must be served for the run to progress; blocking=False keeps the test moving.
    with AgentRuntime() as runtime:
        runtime.serve(agent, blocking=False)
        suite = CorrectnessEval(runtime).run(
            [
                EvalCase(
                    name="weather_lookup_does_not_page",
                    agent=agent,
                    prompt="What is the weather in San Francisco?",
                    expect_tools=["get_weather"],
                    expect_tools_not_used=["notify_ops"],
                )
            ]
        )
    assert suite.all_passed
