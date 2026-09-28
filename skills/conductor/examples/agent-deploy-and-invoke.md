# Example: Build, deploy, and invoke a Conductor Agent (default agent path)

The end-to-end default path from [../references/agents.md](../references/agents.md): write an agent with the SDK, run it once, deploy it, serve its tools, call it from a workflow with the `AGENT` task, handle a human pause, observe it, schedule it, cancel it. Python shown; the TypeScript / Java / C# equivalents are in [../references/agent-sdks.md](../references/agent-sdks.md).

## 0. Prerequisites

```bash
conductor agent list                              # agent runtime on (table or "No agents found.")
python3 "$CONDUCTOR_API" providers-status         # openai.configured must be true (OPENAI_API_KEY on the server)
pip install 'conductor-python[agents]'
export CONDUCTOR_SERVER_URL=http://localhost:8080/api
```

## 1. Write and run once

[agents/python/weather_agent.py](agents/python/weather_agent.py) defines `get_weather` (`@tool`) and `notify_ops` (`@tool(approval_required=True)` — a side-effect tool that a human must approve) on `Agent(name="weather_agent", model="openai/gpt-4o-mini", ..., max_turns=10)`.

```bash
python weather_agent.py run       # runtime.run(agent, prompt) → prints the result and execution_id
```

`run()` compiles, registers if needed, executes once and polls its own tool workers until it returns. It is **not** a deployment — the workers die with the script.

## 2. Plan, deploy, serve

```bash
python weather_agent.py plan      # runtime.plan(agent) → {workflowDef, requiredWorkers: ["get_weather", "notify_ops"]}
python weather_agent.py deploy    # runtime.deploy(agent) → registers weather_agent v1; no execution
conductor agent get weather_agent # model: openai/gpt-4o-mini, tools, maxTurns
python weather_agent.py serve     # second terminal — runtime.serve(agent) polls the two tool workers forever
```

**Agent worker gate:** `requiredWorkers` is non-empty, so `serve` must be running before any workflow calls the agent; otherwise the tool task sits SCHEDULED and the run never finishes.

Ad-hoc run of the deployed agent: `conductor agent run --name weather_agent "Weather in SF, then notify ops"` (streams `[thinking]`, `[tool]`, `[waiting]`, `[done]`).

## 3. Invoke from a workflow

[workflows/agent-invoke.json](workflows/agent-invoke.json) calls a deployed agent by name. Edit `"name": "planner"` to `weather_agent`:

```
run_agent (AGENT, agentType conductor, name, prompt)
```

```bash
conductor workflow create examples/workflows/agent-invoke.json
conductor workflow start -w conductor_agent_basic --sync -i '{"prompt":"Weather in SF?"}'
```

Outputs to read downstream: `${run_agent_ref.output.text}`, `${run_agent_ref.output.output.result}`, `${run_agent_ref.output.state}`, `${run_agent_ref.output.executionId}`.

## 4. Answer the pause — approve vs resume

When a prompt asks `weather_agent` to call `notify_ops`, the `AGENT` task **completes** with `waiting: true`, `pendingTool.toolCalls[0].name == "notify_ops"` and `pendingTool.response_schema.required == ["approved"]` (`tool_name` is `null` for compiled agents). Decide by `pendingTool.response_schema`:

- **Approval gate** (this case): `conductor agent respond <executionId> --approve` (or `--deny --reason "..."`, `POST /api/agent/{id}/respond {"approved": true}`, SDK `approve()`). A resume `AGENT` task is not the approval channel (its `{"result": prompt}` only reaches the gate via an LLM normalizer). In-workflow approval: [workflows/agent-approval-in-workflow.json](workflows/agent-approval-in-workflow.json) — HUMAN → `HTTP` respond → `DO_WHILE` polling `/status` (verified, deterministic).
- **Conversational question** (`human_tool`): use [workflows/agent-hitl-resume.json](workflows/agent-hitl-resume.json). Complete its HUMAN task with `conductor task update-execution --workflow-id <parentWfId> --task-ref-name collect_answer_ref --status COMPLETED --output '{"answer":"Use Celsius"}'`; the next AGENT task resumes the run. Do not use this flow for `approval_required` tools.

## 5. Observe

```bash
conductor agent execution --name weather_agent --since 1h        # ID, AGENT, STATUS, START TIME, DURATION
conductor agent status <executionId>
conductor agent stream <executionId>                             # thinking / tool_call / tool_result / waiting / done
conductor workflow get-execution <executionId> -c                # the compiled tasks: weather_agent_loop, weather_agent_llm, tool tasks
```

UI: `{BASE_URL}/agents`, `{BASE_URL}/agentExecutions/<executionId>`. Hang triage: `waiting: true` = a pause (answer it); a tool task stuck SCHEDULED = nobody is serving; the LLM task failing = provider not configured (`providers-status`).

## 6. Schedule and cancel

```bash
conductor schedule create -n weather_agent-nightly -c "0 0 2 * * ?" -w weather_agent -i '{"prompt":"Weather in SF?"}'
python3 "$CONDUCTOR_API" agent-cancel --id <executionId> --reason "superseded" # DELETE /api/agent/{id}/cancel
conductor workflow terminate <executionId>                                       # same effect — the executionId is a workflow id
```

From a workflow: [workflows/agent-cancel.json](workflows/agent-cancel.json) races the `AGENT` task against a `WAIT 20m → TERMINATE` branch (termination propagates), or use `CANCEL_AGENT {agentType: "conductor", executionId, reason}`. Parallel specialists: [workflows/agent-fork-specialists.json](workflows/agent-fork-specialists.json).

## Tests

[agents/python/test_weather_agent.py](agents/python/test_weather_agent.py): offline `mock_run(agent, prompt, events=[...])` + `expect(result).completed().used_tool("get_weather").no_errors()` (no server, no LLM), and a live `CorrectnessEval(runtime).run([EvalCase(...)])` marked for nightly CI with `runtime.serve(agent, blocking=False)` in the fixture.
