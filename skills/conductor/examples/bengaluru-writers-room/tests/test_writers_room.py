"""Offline contracts for the 120-specialist society."""

from __future__ import annotations

import json
from pathlib import Path

from conductor.ai.agents import Strategy
from conductor.ai.agents.config_serializer import AgentConfigSerializer
from conductor.ai.agents.tool import get_tool_def

from writers_room.agents import (
    DEPARTMENT_AGENTS,
    ORIGINALITY_CHARTER,
    WRITERS_ROOM_PHASES,
    all_agent_objects,
    specialist_agents,
)
from writers_room.tools import safe_artifact_path, write_story_package


def test_society_has_at_least_one_hundred_specialists() -> None:
    specialists = specialist_agents()
    assert len(specialists) == 120
    assert len(DEPARTMENT_AGENTS) == 12
    assert all(len(department.agents) == 10 for department in DEPARTMENT_AGENTS)
    all_agents = all_agent_objects()
    assert len({agent.name for agent in all_agents}) == len(all_agents)


def test_both_model_families_are_materially_represented() -> None:
    models = [agent.model for agent in specialist_agents()]
    assert sum(model.startswith("openai/") for model in models) == 60
    assert sum(model.startswith("anthropic/") for model in models) == 60
    assert "openai/gpt-6-astra" in models
    assert "anthropic/claude-fable-5-1" in models
    assert all("/" in model for model in models)


def test_all_agents_and_tools_are_bounded() -> None:
    for agent in all_agent_objects():
        assert agent.max_turns > 0
        assert agent.timeout_seconds > 0
        for worker in agent.tools:
            definition = get_tool_def(worker)
            assert definition.max_calls is not None and definition.max_calls > 0
            assert definition.timeout_seconds is not None and definition.timeout_seconds > 0


def test_phase_graph_and_originality_contract() -> None:
    assert len(WRITERS_ROOM_PHASES) == 6
    assert all(agent.strategy == Strategy.PARALLEL for agent in WRITERS_ROOM_PHASES[:4])
    assert all(department.strategy == Strategy.PARALLEL for department in DEPARTMENT_AGENTS)
    assert "Never copy" in ORIGINALITY_CHARTER
    assert "HBO's Silicon Valley" in ORIGINALITY_CHARTER


def test_agent_tree_serializes_to_conductor_config() -> None:
    encoded = "\n".join(
        json.dumps(AgentConfigSerializer().serialize(agent)) for agent in WRITERS_ROOM_PHASES
    )
    assert encoded.count('"strategy": "parallel"') >= 16
    assert '"requiredTools": ["write_story_package"]' in encoded
    assert all(agent.include_contents == "none" for agent in all_agent_objects())


def test_publisher_is_approval_gated() -> None:
    definition = get_tool_def(write_story_package)
    assert definition.approval_required is True
    assert definition.max_calls == 3


def test_artifact_paths_and_writes_are_safe_and_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WRITERS_ROOM_WORKSPACE", str(tmp_path))
    try:
        safe_artifact_path("../escape.md")
    except ValueError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("path traversal was accepted")

    payload = [{"path": "episodes/pilot.md", "content": "# Pilot\n"}]
    first = write_story_package(payload)
    second = write_story_package(payload)
    assert first["written"] == ["episodes/pilot.md"]
    assert second["unchanged"] == ["episodes/pilot.md"]


def _task_types(tasks: list[dict]) -> list[str]:
    found = []
    for task in tasks:
        found.append(task["type"])
        found.extend(_task_types(task.get("loopOver", [])))
        for branch in task.get("decisionCases", {}).values():
            found.extend(_task_types(branch))
        found.extend(_task_types(task.get("defaultCase", [])))
    return found


def test_workflow_isolates_phases_and_owns_publisher_approval() -> None:
    path = Path(__file__).parents[1] / "workflows" / "bengaluru-writers-room.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    assert workflow["schemaVersion"] == 2
    types = _task_types(workflow["tasks"])
    assert types.count("AGENT") == 6
    assert "HUMAN" in types
    assert "DO_WHILE" in types
    assert "SIMPLE" not in types
    agent_inputs = [task["inputParameters"] for task in workflow["tasks"] if task["type"] == "AGENT"]
    assert [item["name"] for item in agent_inputs] == [agent.name for agent in WRITERS_ROOM_PHASES]
    assert all(item["agentType"] == "conductor" for item in agent_inputs)
    assert "research_phase_ref.output.text" not in agent_inputs[2]["prompt"]
    loop = next(task for task in workflow["tasks"] if task["type"] == "DO_WHILE")
    assert "< 1680" in loop["loopCondition"]
