"""Offline contract tests; no Conductor server or model key required."""

from __future__ import annotations

import json
from pathlib import Path

from conductor.ai.agents import Strategy
from conductor.ai.agents.config_serializer import AgentConfigSerializer
from conductor.ai.agents.tool import get_tool_def

from software_society.agents import (
    SOFTWARE_SOCIETY,
    development_swarm,
    planning_council,
)
from software_society.tools import (
    apply_change_set,
    inspect_workspace,
    read_workspace_file,
    run_quality_checks,
    safe_path,
)


def walk_agents(agent):
    yield agent
    for child in agent.agents:
        yield from walk_agents(child)


def test_society_has_nested_bounded_strategies() -> None:
    assert SOFTWARE_SOCIETY.strategy == Strategy.SEQUENTIAL
    assert SOFTWARE_SOCIETY.max_turns == 3
    assert SOFTWARE_SOCIETY.timeout_seconds == 2400

    assert planning_council.strategy == Strategy.PARALLEL
    assert len(planning_council.agents) == 4
    assert all(agent.max_turns > 0 and agent.timeout_seconds > 0 for agent in planning_council.agents)

    assert development_swarm.strategy == Strategy.SWARM
    assert development_swarm.max_turns == 16
    assert development_swarm.termination is not None
    assert len(development_swarm.agents) == 5
    assert all(agent.max_turns > 0 and agent.timeout_seconds > 0 for agent in development_swarm.agents)


def test_mutating_and_execution_tools_require_approval() -> None:
    apply_def = get_tool_def(apply_change_set)
    checks_def = get_tool_def(run_quality_checks)
    assert apply_def.approval_required is True
    assert apply_def.max_calls == 8
    assert checks_def.approval_required is True
    assert checks_def.max_calls == 10


def test_every_callable_tool_is_bounded_and_agent_tree_serializes() -> None:
    for agent in walk_agents(SOFTWARE_SOCIETY):
        assert agent.max_turns > 0
        assert agent.timeout_seconds > 0
        for worker in agent.tools:
            definition = get_tool_def(worker)
            assert definition.max_calls is not None and definition.max_calls > 0
            assert definition.timeout_seconds is not None and definition.timeout_seconds > 0

    config = AgentConfigSerializer().serialize(SOFTWARE_SOCIETY)
    encoded = json.dumps(config)
    assert '"strategy": "sequential"' in encoded
    assert '"strategy": "parallel"' in encoded
    assert '"strategy": "swarm"' in encoded


def test_paths_cannot_escape_workspace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOFTWARE_SOCIETY_WORKSPACE", str(tmp_path))
    try:
        safe_path("../outside.txt")
    except ValueError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("path traversal was accepted")


def test_change_set_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOFTWARE_SOCIETY_WORKSPACE", str(tmp_path))
    first = apply_change_set([{"path": "src/app.py", "content": "print('hello')\n"}])
    second = apply_change_set([{"path": "src/app.py", "content": "print('hello')\n"}])
    assert first["written"] == ["src/app.py"]
    assert second["unchanged"] == ["src/app.py"]
    assert read_workspace_file("src/app.py")["content"] == "print('hello')\n"


def test_change_set_rejects_oversized_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOFTWARE_SOCIETY_WORKSPACE", str(tmp_path))
    try:
        apply_change_set([{"path": "huge.txt", "content": "x" * 200_001}])
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("oversized file was accepted")


def test_workspace_inspection_ignores_git_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOFTWARE_SOCIETY_WORKSPACE", str(tmp_path))
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret-ish metadata", encoding="utf-8")
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    listing = inspect_workspace()
    assert listing["files"] == ["README.md"]


def test_workflow_invokes_society_with_builtin_agent_task_only() -> None:
    workflow_path = Path(__file__).parents[1] / "workflows" / "software-society.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert workflow["schemaVersion"] == 2
    assert workflow["timeoutSeconds"] > workflow["tasks"][0]["inputParameters"]["maxDurationSeconds"]
    assert [task["type"] for task in workflow["tasks"]] == ["AGENT", "DO_WHILE", "HTTP"]
    assert workflow["tasks"][0]["inputParameters"]["agentType"] == "conductor"
    assert workflow["tasks"][0]["inputParameters"]["name"] == SOFTWARE_SOCIETY.name
    loop = workflow["tasks"][1]
    assert loop["evaluatorType"] == "graaljs"
    assert "< 480" in loop["loopCondition"]
    assert any(task["type"] == "HUMAN" for task in loop["loopOver"][1]["decisionCases"]["true"])
