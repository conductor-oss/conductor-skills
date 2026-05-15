# Conductor Skill Evaluations

Evaluation scenarios for testing the Conductor workflow skill end-to-end.

## Purpose

These evaluations ensure the Conductor skill:
- Installs the CLI and connects to servers (local or remote, with or without auth)
- Creates valid workflow definitions with proper JSON schema
- Checks for missing workers before running workflows
- Monitors, manages, signals, and retries workflow executions
- Switches between environments using CLI profiles
- Generates Mermaid visualizations of workflow definitions
- Falls back to the Python script when the CLI cannot be installed
- Reviews existing workflows against the optimization checklist and grades findings CRITICAL / WARN / INFO
- Activates from natural language (no slash command needed) to discover its own capabilities
- Walks first-time setup safely (asks before `npm install -g`, never echoes secrets)
- Scaffolds workers in the language the user names
- Builds AI / LLM workflows (single-shot LLM, MCP agent, RAG, autonomous agent loop)
- Schedules workflows on Quartz cron (an OSS feature)
- Handles Orkes-only features (secrets, webhooks) without echoing secret values

## Evaluation Files

### install-and-connect.json
Tests first-time setup: CLI installation, server choice (local vs remote), auth detection, profile saving.

### local-server-setup.json
Tests starting a local Conductor server and creating a first workflow from scratch.

### connect-remote-server.json
Tests connecting to a remote server URL, detecting auth requirements (401/403), setting credentials, and saving as a profile.

### profile-switching.json
Tests multi-environment queries (e.g. "how many workflows in dev vs prod?") using `--profile` to route to the correct server.

### create-and-run-workflow.json
Tests full workflow lifecycle: JSON creation, registration, worker check against task definitions, execution, and status monitoring.

### monitor-and-signal.json
Tests searching running workflows, identifying pending WAIT/HUMAN tasks, signaling them, and verifying progression.

### manage-failed-workflow.json
Tests finding failed workflows, diagnosing root causes from task details, and retrying them.

### visualize-workflow.json
Tests fetching a workflow definition and generating a Mermaid flowchart with correct construct mapping.

### write-worker.json
Tests scaffolding a worker for a SIMPLE task using the appropriate SDK.

### fallback-no-cli.json
Tests the fallback path when Node.js/npm cannot be installed, using the bundled `conductor_api.py` script.

### optimize-workflow.json
Tests review/optimization of an existing workflow — loading the workflow + each SIMPLE task's task def, walking the 19-rule checklist in `references/optimization.md`, grouping findings by CRITICAL/WARN/INFO, and offering fixes one at a time without applying silently.

### discover-capabilities.json
Tests natural-language activation — when a user asks "what can you help me do with Conductor?" the agent should activate from the skill description (no slash command needed) and summarize the major capability areas, including that schedules are OSS.

### setup-flow.json
Tests first-time setup — checking for the CLI, preferring `npx`, asking before `npm install -g`, presenting local-vs-remote options, never echoing auth secrets, and verifying with `conductor workflow list`.

### scaffold-worker.json
Tests worker scaffolding in the user's language — using the correct SDK pattern from `references/workers.md`, matching the `task_definition_name` to the workflow's SIMPLE task name, and including the idempotency note.

### schedule-workflow.json
Tests scheduling a workflow on cron — recognizing that schedules are OSS (not Orkes), writing the JSON to a file, using correct Quartz cron syntax (including the day-of-month vs day-of-week `?` quirk), and registering via `conductor schedule create`.

### ai-agent-mcp.json
Tests building the canonical first-AI-agent workflow — 4 tasks (LIST_MCP_TOOLS → LLM_CHAT_COMPLETE plan → CALL_MCP_TOOL → LLM_CHAT_COMPLETE summarize), low-temperature planning that emits JSON, and correct wiring of `${plan.output.result.method}` into the tool call.

### llm-rag.json
Tests building a RAG workflow — `LLM_SEARCH_INDEX` followed by a grounded `LLM_CHAT_COMPLETE`, including a system prompt that instructs the model to answer only from context, low temperature, and returning sources alongside the answer.

### agent-loop.json
Tests building a ReAct-pattern autonomous agent loop — DO_WHILE with a hard iteration cap (per optimization rule B5), the canonical self-reference pattern (`loop: ${loop.output}`), workflow-level timeout, and a SWITCH branching on the model's `done` flag.

### orkes-secrets.json
Tests Orkes secrets handling — recognizing the feature is Orkes-only, never echoing the secret value in chat or shell commands, confirming by name only, and showing the `${workflow.secrets.X}` reference syntax for use in workflow tasks.

## Running Evaluations

### Automated (recommended)

The eval runner supports multiple LLM providers: **Anthropic**, **OpenAI**, and **Google Gemini**. The provider is auto-detected from the model name, or can be set explicitly with `--provider`.

```bash
# Run all evals with Anthropic (default)
python3 scripts/run_evals.py

# Run with OpenAI
python3 scripts/run_evals.py --model gpt-4o

# Run with Google Gemini
python3 scripts/run_evals.py --model gemini-2.5-pro

# Explicit provider (for custom/fine-tuned models)
python3 scripts/run_evals.py --provider openai --model ft:gpt-4o:my-org

# Use different providers for agent vs judge
python3 scripts/run_evals.py --model gpt-4o --judge-model claude-sonnet-4-20250514

# Run a specific eval
python3 scripts/run_evals.py evaluations/profile-switching.json

# Verbose output (shows agent response)
python3 scripts/run_evals.py --verbose

# Save JSON report
python3 scripts/run_evals.py --json --output report.json

# Compare across providers
python3 scripts/run_evals.py --model claude-sonnet-4-20250514 -o anthropic.json
python3 scripts/run_evals.py --model gpt-4o -o openai.json
python3 scripts/run_evals.py --model gemini-2.5-pro -o gemini.json
```

Exit code is `0` if all evals pass, `1` if any fail — suitable for CI/CD gates.

### Manual

1. Enable the `conductor` skill
2. Submit the `query` from the evaluation JSON file to the agent
3. Verify each step in `expected_behavior` is followed in order
4. Check all items in `success_criteria` pass
5. Test across models and providers

### Prerequisites

- **Anthropic**: `ANTHROPIC_API_KEY` env var (get at https://console.anthropic.com/)
- **OpenAI**: `OPENAI_API_KEY` env var (get at https://platform.openai.com/api-keys)
- **Gemini**: `GEMINI_API_KEY` env var (get at https://aistudio.google.com/apikey)
- **Local server evals**: No prerequisites — the agent should install CLI and start the server
- **Remote server evals**: Need a running Conductor server URL
- **Profile switching evals**: Need at least two profiles saved in `~/.conductor-cli/config.yaml`
- **Worker evals**: Need Python, JavaScript, or Java SDK environment available
- **Fallback evals**: Run in an environment without Node.js/npm

## Expected Skill Behaviors

### CLI Setup
- CLI is installed automatically if missing (`npm install -g @conductor-oss/conductor-cli`)
- Node.js is installed if npm is unavailable
- Fallback script is used only as last resort

### Server Connection
- Local server started with `conductor server start` when no server exists
- Remote servers tested for auth before requesting credentials
- Connections saved as named profiles for reuse

### Workflow Lifecycle
- JSON written to file before registration (never inline)
- SIMPLE tasks checked against task definitions after registration
- Missing workers flagged with offer to scaffold one
- Execution status monitored and reported clearly

### Security
- Auth tokens, keys, and secrets are never echoed in output
- `python3 -c` is never used for any purpose

## Creating New Evaluations

When adding Conductor evaluations:

1. **Use realistic scenarios** — real workflow patterns (ETL, approval, notification)
2. **Test the full chain** — setup → create → run → monitor → manage
3. **Include error paths** — auth failures, missing workers, failed tasks
4. **Test environment routing** — queries mentioning "dev", "prod", "staging"
5. **Vary complexity** — simple 2-task workflows to complex FORK_JOIN + SWITCH patterns

## Example Success Criteria

**Good** (specific, testable):
- "CLI is installed automatically if missing, not just suggested"
- "SIMPLE tasks are checked against task definitions before starting"
- "Profile names are inferred from context ('dev' and 'prod')"
- "Mermaid diagram uses diamond nodes for SWITCH tasks"
- "Every $.varName in JS scripts (INLINE, DO_WHILE, SWITCH) is declared as an inputParameters key"

**Bad** (vague, untestable):
- "Workflow is created correctly"
- "Agent handles auth properly"
- "Visualization looks good"
