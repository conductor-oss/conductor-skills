# Conductor Skills — Test Plan

Comprehensive validation plan for the `conductor-skills` plugin. Hand this to QA before each release.

- **Repo:** [github.com/conductor-oss/conductor-skills](https://github.com/conductor-oss/conductor-skills)
- **Current version:** see `VERSION`
- **Target agents:** primarily Claude Code (slash commands + skill); secondarily Codex, Gemini, Cursor, Windsurf, Cline, GitHub Copilot, Aider, Amazon Q, Roo Code, Amp, OpenCode (skill content only — slash commands are Claude-specific)

Test cases below are numbered `TC-<area>-<n>` for traceability. Mark each Pass / Fail / Blocked / Skipped in the matrix at the bottom.

---

## 1. About this plan

### 1.1 Scope

In scope:
- Plugin install/uninstall/upgrade across supported agents
- All five slash commands
- Skill activation via natural language
- All workflow CRUD, execution, monitoring, management, signaling
- All 25+ task types documented in `references/workflow-definition.md`, including the agent tasks `AGENT`, `GET_AGENT_CARD`, `CANCEL_AGENT`
- Worker scaffolding in 7 languages
- Conductor Agent lifecycle via the SDKs (run, plan, deploy, serve, respond, cancel, schedule) and `/conductor-scaffold-agent`
- Schedules (OSS) and Orkes-only features (secrets, webhooks)
- Fallback REST script (no Node.js)
- Optimization checklist coverage (all 32 items, A–F)
- Mermaid visualization
- Documentation integrity (links, JSON, version coherence)
- Security guarantees (no token/secret echoing, no `python3 -c` at runtime)

Out of scope:
- The Conductor CLI itself (separate project)
- Conductor server behavior (separate project)
- LLM provider correctness for AI tasks (provider-side concern)

### 1.2 Test environments

| Env | What it is | Purpose |
|-----|-----------|---------|
| **E1 — Clean** | Fresh machine, no `conductor` CLI, no Node.js, no Python beyond stdlib | Tests setup-from-zero and Python fallback path |
| **E2 — OSS local** | Local OSS Conductor server via `conductor server start` | Default dev path; covers most scenarios |
| **E3 — OSS remote** | Remote OSS Conductor with `CONDUCTOR_SERVER_URL` set, no auth | Tests remote server path |
| **E4 — OSS auth'd** | Remote OSS with `CONDUCTOR_AUTH_TOKEN` required | Tests token-based auth |
| **E5 — Orkes sandbox** | `https://developer.orkescloud.com` with key/secret credentials | Tests Orkes path: sandbox, schedules, secrets, webhooks |
| **E6 — Multi-profile** | Two profiles in `~/.conductor-cli/config-dev.yaml` and `config-prod.yaml` | Tests profile switching |

QA must execute the test suite at minimum on E2 and E5. Each test case lists which environments it requires.

### 1.3 Prerequisites

- Claude Code (latest) for slash-command and skill testing
- A second AI coding agent (e.g. Cursor or Codex CLI) for cross-agent skill validation
- Node.js 20+ and npm (for CLI install path)
- Python 3.10+ (for validators, evals, fallback script)
- `git`, `curl`, `jq`
- API keys for eval framework: `ANTHROPIC_API_KEY` (default judge), optional `OPENAI_API_KEY` and `GEMINI_API_KEY`
- An Orkes account with key/secret for E5
- A spare repo for plugin install testing (to avoid polluting your main workspace)

---

## 2. Pre-flight (no agent required)

These run on the repo before involving any AI agent.

| ID | Description | Steps | Expected |
|----|-------------|-------|----------|
| TC-PRE-01 | Plugin manifest valid | `python3 scripts/validate_plugin.py` | `Plugin validation OK (version X.Y.Z)`; exit 0. Also covers examples JSON parsing + AGENT lint, eval schema, installer parity (TC-PRE-05) and the context budget (TC-PRE-06). |
| TC-PRE-02 | All intra-repo markdown links resolve | Run the link checker (see Appendix A) | `0 broken links` |
| TC-PRE-03 | VERSION coherence | `grep -E '"version":' .claude-plugin/*.json package.json && cat VERSION` | Same version in all six places (covered by TC-PRE-01 too) |
| TC-PRE-04 | License + headers present | Inspect `LICENSE.txt`, `README.md` top | Apache 2.0 license intact, attribution present |
| TC-PRE-05 | Installer parity | `python3 scripts/validate_plugin.py` (installer-parity check) | No `install.sh` / `install.ps1` "does not ship" or "non-existent file" lines; the `SKILL_FILES` lists in both scripts equal the set of files under `skills/conductor/**` |
| TC-PRE-06 | Eval context budget | `python3 scripts/run_evals.py --print-context-size` (no API key needed; `validate_plugin.py` prints the same line) | `Eval context size: N chars (~T tokens)` with N ≤ 300,000; validator warns above 300,000 and fails above 340,000 |

### 2.1 CI smoke (post-push)

The GitHub Actions `validate-plugin` workflow runs on push to `main` and on any PR touching plugin paths. This isn't pre-flight — by the time it runs, your work is already on origin.

| ID | Description | Steps | Expected |
|----|-------------|-------|----------|
| TC-CI-01 | CI runs and passes on PR | Push a branch and open a PR | GitHub Actions `validate-plugin` run is green |
| TC-CI-02 | CI catches a deliberate break | Push a commit with `version` mismatch | CI fails with a clear error from `validate_plugin.py` |

---

## 3. Plugin lifecycle (Claude Code)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-PLG-01 | Install from local path | E2 | `/plugin marketplace add /path/to/conductor-skills` then `/plugin install conductor@conductor-skills` | Plugin shows in `/plugin` list at the new version |
| TC-PLG-02 | Install from GitHub marketplace | E2 | `/plugin marketplace add conductor-oss/conductor-skills` then `/plugin install conductor@conductor-skills` | Plugin installed; version matches `VERSION` |
| TC-PLG-03 | `/conductor` discoverable | E2 | After install, type `/` in chat input | `/conductor` appears in command picker with description |
| TC-PLG-04 | Four subcommands listed | E2 | Type `/conductor-` | Autocomplete shows `setup`, `optimize`, `scaffold-worker`, `scaffold-agent` (the bare `/conductor` is separately tested in TC-PLG-03) |
| TC-PLG-05 | Skill activates from natural language | E2 | Ask: *"What can the conductor skill do?"* | Skill activates, lists capabilities consistent with SKILL.md |
| TC-PLG-06 | Upgrade preserves config | E2 | Install vN-1, modify `~/.conductor-cli/config-dev.yaml`, upgrade to vN | Config untouched; new version reported |
| TC-PLG-07 | Uninstall is clean | E2 | `/plugin uninstall conductor@conductor-skills` | Slash commands gone; skill no longer activates |
| TC-PLG-08 | install.sh works for non-Claude agents | E2 | `curl -sSL .../install.sh \| bash -s -- --agent codex --global` | Intact skill dir at `~/.agents/skills/conductor/` — SKILL.md, `references/`, `examples/`, `scripts/conductor_api.py` all present |
| TC-PLG-09 | install.ps1 (Windows) works | E2 (Windows) | `.\install.ps1 -Agent cline` | Intact skill dir at `.cline\skills\conductor\` |
| TC-PLG-10 | First-install welcome | E2 | Install for an agent with no existing manifest entry | Shows a terminal banner plus Slack support, Conductor documentation, and Conductor OSS contribution links; omits community showcase; asks the agent to create both `developer` and `localhost` profiles and marks Developer Edition as the default |
| TC-PLG-11 | Welcome is not repeated | E2 | Reinstall the current version, then upgrade an older manifest entry | Neither reinstall nor upgrade prints the first-install welcome |
| TC-PLG-10 | `--upgrade` upgrades each agent | E2 | `bash install.sh --all --upgrade` | All previously-installed agents upgraded |
| TC-PLG-11 | `--uninstall` removes cleanly | E2 | `bash install.sh --agent cursor --uninstall` | Cursor's manifest entry removed; `.agents/skills/conductor/` removed only if no other agent's manifest entry references it (see TC-PLG-13) |
| TC-PLG-12 | Shared dir written once under `--all` | E2 | `bash install.sh --all` with codex + gemini + cursor + opencode + copilot + amp detected | One mirror of `~/.agents/skills/conductor/`, one `Installed skill files` line, five `already installed this run` lines; manifest has one entry per agent, all pointing at the shared path |
| TC-PLG-13 | Refcount uninstall keeps shared dir | E2 | Install all six, then `--agent codex --global --uninstall` | `Kept ... still used by: gemini cursor opencode copilot amp`; dir survives. Uninstalling the remaining five removes the dir after the last one |
| TC-PLG-14 | copilot / amp are real shared-dir participants | E2 | `--agent copilot --global`, `--agent amp --global` | Each writes `~/.agents/skills/conductor/` (or mirrors it if another shared agent already did), records its own manifest entry with the shared `target_path`, and is refcounted on uninstall like codex/gemini/cursor/opencode |
| TC-PLG-15 | windsurf split behavior | E2 | `--agent windsurf` in a project, then `--agent windsurf --global` | Project: intact dir at `.windsurf/skills/conductor/`. Global: `global_rules.md` file, no skill dir |
| TC-PLG-16 | cline included in `--all` | E2 | `bash install.sh --all` with `~/.cline` present | Intact skill dir at `~/.cline/skills/conductor/` |
| TC-PLG-17 | Legacy blobs untouched | E2 | Pre-create `~/.codex/AGENTS.md`, `~/.config/AGENTS.md` with custom content, install and uninstall all agents | Both files keep their custom content — installer never rewrites or deletes them |
| TC-PLG-18 | Summary grouped by location | E2 | `bash install.sh --all`, also `--all --check` | `Install locations:` lists one line per physical dir, naming every agent sharing it (codex, gemini, cursor, opencode, copilot, amp all appear on the shared line — no separate annotation) |
| TC-PLG-19 | `--all --uninstall` removes agents no longer detected | E2 | Install codex globally, then externally delete `~/.codex` (simulating the CLI being uninstalled outside this script), then `bash install.sh --all --uninstall` | codex is still uninstalled (and refcounted) even though `Detect-Agents`/detection no longer finds it — the manifest, not detection, drives which agents `--all --uninstall` covers |
| TC-PLG-20 | Global uninstall gated by agent support | E2 | `bash install.sh --agent amazonq --global --uninstall` | Errors with "Global uninstall is not supported for amazonq. Run from your project directory instead." instead of silently no-oping |
| TC-PLG-21 | Legacy install path warned, not deleted | E2 | Hand-edit the manifest so an agent's recorded `target_path` points at a superseded location that still exists on disk (e.g. a pre-1.6.6 single-file path), then reinstall that agent | Install succeeds and prints `Legacy install found at <old path> (superseded by <new path>) — remove it manually if no longer needed`; the old file is left untouched |

---

## 4. Slash commands

### 4.1 `/conductor` (menu)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-01 | Menu lists all subcommands | E2 | `/conductor` | Output names `/conductor-setup`, `/conductor-optimize`, `/conductor-scaffold-worker`, `/conductor-scaffold-agent` and gives natural-language examples |
| TC-CMD-02 | Menu prompts for next action | E2 | `/conductor` | Ends with a question like *"What would you like to do?"* — does not start an unprompted action |

### 4.2 `/conductor-setup`

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-10 | First-time on clean machine | E1 | `/conductor-setup` | Detects missing CLI; offers `npx` first; **asks before** `npm install -g` |
| TC-CMD-11 | CLI already installed | E2 | `/conductor-setup` | Skips install and starts the standard `developer` + `localhost` profile setup |
| TC-CMD-12 | Local server option | E2 | `/conductor-setup`, choose Option A | Runs `conductor server start`; verifies with `conductor server status` |
| TC-CMD-13 | Remote no-auth option | E3 | `/conductor-setup`, choose Option B, no creds requested | Sets `CONDUCTOR_SERVER_URL`, `conductor workflow list` returns OK |
| TC-CMD-14 | Remote with token auth | E4 | `/conductor-setup`, server returns 401 first | Asks for token, sets `CONDUCTOR_AUTH_TOKEN`, never echoes the value |
| TC-CMD-15 | Orkes key/secret auth | E5 | `/conductor-setup` against `developer.orkescloud.com` | Normalizes to `/api`; asks the user to inject key + secret securely; verifies; never requests or echoes values in chat |
| TC-CMD-16 | Saves named profile when asked | E5/E6 | After setup, ask "save this as profile prod" | Directs the user to run interactive `conductor config save --profile prod`; profile appears as `~/.conductor-cli/config-prod.yaml` |
| TC-CMD-18 | Explicit Orkes URL | E5 | "Use https://developer.orkescloud.com/; auth env is already set" | Does not re-ask local-vs-remote; uses `https://developer.orkescloud.com/api`, Enterprise mode, and verifies with no credential output |
| TC-CMD-19 | Fallback key/secret auth | E5 without CLI/npm | Run `conductor_api.py list-workflows` with key/secret env | Exchanges at `/api/token` in memory and sends JWT via `X-Authorization` without printing it |
| TC-CMD-19a | Default dual-profile setup | E2/E5 | `/conductor-setup` with no target | Creates interactive `developer` and `localhost` profiles; uses visible Developer Edition navigation and a user-owned key-creation handoff; defaults later commands to `--profile developer` |
| TC-CMD-17 | `npm install -g` requires confirmation | E1 | When CLI is missing and user picks global install | Agent **explicitly confirms** before running install command |

### 4.3 `/conductor-optimize`

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-20 | Asks which workflow to review | E2 | `/conductor-optimize` (no arg) | Asks for file path or registered workflow name |
| TC-CMD-21 | Reviews from JSON file | E2 | `/conductor-optimize skills/conductor/examples/workflows/weather-notification.json` | Loads file; reports findings grouped CRITICAL/WARN/INFO |
| TC-CMD-22 | Reviews registered workflow | E2 | Register `weather_notification`; `/conductor-optimize weather_notification` | Calls `conductor workflow get`; reports findings |
| TC-CMD-23 | Loads each SIMPLE task definition | E2 | Use a workflow with SIMPLE tasks | Calls `conductor task get` for each distinct SIMPLE task |
| TC-CMD-24 | Walks all 32 checklist items | E2 | Optimize a deliberately broken workflow (see Appendix C; Appendix D for agents) | Report mentions every category A–F with at least one INFO entry per checked area (F is N/A-passing when no `AGENT` task or agent definition is present) |
| TC-CMD-25 | Flags missing timeouts as CRITICAL | E2 | Workflow with `responseTimeoutSeconds=0` | CRITICAL finding under B1 |
| TC-CMD-26 | Flags hardcoded secret as CRITICAL | E2 | Workflow input named `apiKey`, `token`, etc. | CRITICAL finding under D1 |
| TC-CMD-27 | Flags unbounded DO_WHILE as CRITICAL | E2 | DO_WHILE without iteration cap | CRITICAL under B5 |
| TC-CMD-28 | Flags missing description as WARN | E2 | Workflow with empty `description` | WARN under A1 |
| TC-CMD-29 | Flags 100+ task workflow | E2 | Workflow with 105 tasks | WARN under A4 |
| TC-CMD-30 | Flags single-task workflow | E2 | One-HTTP-task workflow | WARN under E2 |
| TC-CMD-31 | Offers fixes one at a time | E2 | After report, agent says "want me to apply X?" | One fix at a time, no silent application |
| TC-CMD-32 | Won't apply silently | E2 | Reply "fix everything" without specifics | Asks for confirmation per fix or proposes a plan |

### 4.4 `/conductor-scaffold-worker`

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-40 | Asks language and task name | E2 | `/conductor-scaffold-worker` | Asks for language; asks for task type name |
| TC-CMD-41 | Python worker | E2 | Choose Python, task `process_order` | Uses `@worker_task` decorator; `pip install conductor-python`; idempotency comment present |
| TC-CMD-42 | JavaScript/TypeScript worker | E2 | Choose JS, task `process_order` | Uses `TaskManager` from `@io-orkes/conductor-javascript`; idempotency note |
| TC-CMD-43 | Java worker (Worker iface) | E2 | Choose Java, task `process_order` | Implements `Worker` interface OR uses `@WorkerTask` |
| TC-CMD-44 | Go worker | E2 | Choose Go, task `process_order` | Uses `worker.NewTaskRunnerWithApiClient` |
| TC-CMD-45 | C# / Ruby / Rust worker — referral path | E2 | Choose C#, Ruby, or Rust; task `process_order` | `references/workers.md` does not ship inline scaffolds for these languages. Expected: agent points the user to the upstream SDK repo (e.g. github.com/conductor-oss/csharp-sdk) and asks them to follow that SDK's README. **Do NOT** verify against an inline pattern — none exists by design. |
| TC-CMD-46 | Worker name matches task type | E2 | Any language with an inline scaffold (Python/JS/Java/Go) | Worker registers for task type matching the user-supplied name exactly |
| TC-CMD-47 | Reminds about worker gate | E2 | Any | Output mentions registering the task definition / workflow |

### 4.5 `/conductor-scaffold-agent`

Requires the agent runtime: E2 started with `conductor server start` (sets `conductor.integrations.ai.enabled=true` and `agentspan.embedded=true`) and a provider key (e.g. `OPENAI_API_KEY`) exported in the shell that starts the server. Referred to below as **E2+AI**.

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-CMD-50 | Preflight, then asks language + framework | E2+AI | `/conductor-scaffold-agent` | Runs `conductor workflow list`, `conductor agent list`, provider check (`GET /api/providers/status`) in that order; stops with a clear message if the agent runtime is off; then asks language (Python / TypeScript / Java / C#) and a framework constrained by that language, native SDK offered first |
| TC-CMD-51 | Python native scaffold | E2+AI | Choose Python, native; agent `support_triage` with a lookup tool and a refund tool | `from conductor.ai.agents import Agent, AgentRuntime, tool`; `model="openai/..."` set explicitly; refund tool is `@tool(approval_required=True)`; separate run / deploy / serve entry points; idempotency comment on tools; `mock_run` + `expect` test; no provider key in code |
| TC-CMD-52 | TypeScript + Vercel AI tools | E2+AI | Choose TypeScript, Vercel AI | Pins `ai@4 zod@3` for unchanged `parameters` tools or uses native `tool()` for AI SDK 5+; imports from `/agents`; `provider/model`; `runtime.shutdown()` in `finally`; never `agentType: "vercel_ai"` |
| TC-CMD-53 | OpenAI Agents SDK drop-in | E2+AI | Choose Python, OpenAI Agents; paste existing `Runner.run_sync` code | Offers the one-import change `from conductor.ai import Runner`; `pip install 'conductor-python[openai-agents]'`; states LLM turns run server-side and `@function_tool` tools need `serve()`; does not rewrite to a DO_WHILE loop |
| TC-CMD-54 | LangChain import rule | E2+AI | Choose Python, LangChain | Uses `from conductor.ai.agents.langchain import create_agent` (not `langchain.agents`) and explains why (metadata → full extraction; plain builder → LangGraph detection → possible passthrough, so `serve()` is mandatory) |
| TC-CMD-55 | Java LangChain4j artifact | E2+AI | Choose Java, LangChain4j | Gradle dependency is `org.conductoross:conductor-client-ai:<VERSION>` (never `conductor-ai`); version fetched from Maven Central / java-sdk README, not guessed; `LangChain4jAgent.from(...)`; asks about Spring (`conductor-client-ai-spring`) |
| TC-CMD-56 | Unsupported cell refused | E2+AI | Choose C# + LangChain, or Python + Vercel AI | Fixed message naming the nearest supported cell (Semantic Kernel / native `[Tool]` for .NET; native `@tool` or switch to TS for Vercel); no invented package or bridge |
| TC-CMD-57 | Wires the agent into a workflow | E2+AI | After scaffolding, ask "call it from my pipeline workflow" | `AGENT` task with `agentType: "conductor"`, `name` (not `agentName`), `prompt`; downstream reads `${ref.output.text}` / `${ref.output.output.result}`; adds a SWITCH on `waiting` when the agent has an approval or human tool; JSON written to a file first |
| TC-CMD-58 | Never `conductor deploy` | E2+AI | Ask "deploy it" | Uses `runtime.deploy(agent)` (+ a long-lived `serve()` when `requiredWorkers` is non-empty or the framework is passthrough) and verifies with `conductor agent list` / `conductor agent get <name>`; does not run or recommend `conductor deploy` or an invented `conductor agent deploy` |

---

## 5. Setup flows (natural-language activation)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SET-01 | "Help me set up Conductor" | E1 | Prompt agent in plain English | Agent walks the default dual-profile flow in `references/setup.md`, creating `developer` and `localhost` and using `developer` by default |
| TC-SET-02 | Install via npx (no global) | E1 | When prompted, prefer no global install | Agent uses `npx @conductor-oss/conductor-cli ...` |
| TC-SET-03 | Connect to local server | E2 | "Connect to my local Conductor" | CLI auto-detects; no env var needed |
| TC-SET-04 | Connect to remote URL | E3 | "Connect to https://my.example.com/api" | Sets `CONDUCTOR_SERVER_URL`; verifies |
| TC-SET-05 | Connect to Orkes | E5 | "Connect to my Orkes server at developer.orkescloud.com with my key/secret" | Sets `CONDUCTOR_AUTH_KEY` + `_SECRET`; never echoes values |
| TC-SET-06 | Save profile | E6 | "Save this as profile dev" | `conductor config save --profile dev` succeeds |
| TC-SET-07 | Switch profile | E6 | "Switch to my prod profile" | All subsequent commands carry `--profile prod` |
| TC-SET-08 | Multi-env query | E6 | "How many workflows in dev vs prod?" | Two queries: one per profile; reports both counts |

---

## 6. Workflow definitions (CRUD)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-DEF-01 | List all definitions | E2 | "List all workflows" | `conductor workflow list` runs; output rendered as a table |
| TC-DEF-02 | Get specific definition | E2 | "Show me the order_processing workflow" | `conductor workflow get order_processing`; JSON shown |
| TC-DEF-03 | Get specific version | E2 | "Show me v2 of order_processing" | Adds `--version 2` |
| TC-DEF-04 | Create from agent-generated JSON | E2 | "Create a workflow that fetches an API and posts a Slack message" | Writes JSON to file (not inline), runs `conductor workflow create file.json` |
| TC-DEF-05 | Worker gate runs after create | E2 | After TC-DEF-04 if any SIMPLE task | `conductor task list --json` runs; missing workers flagged with offer to scaffold |
| TC-DEF-06 | Worker gate runs after update | E2 | Update an existing workflow that gains a SIMPLE task | Worker gate re-runs |
| TC-DEF-07 | Update existing definition | E2 | "Add a notification step to weather_notification" | Reads existing, modifies, calls `conductor workflow update` |
| TC-DEF-08 | Delete definition | E2 | "Delete weather_notification v1" | Confirms intent, runs `conductor workflow delete weather_notification 1` |
| TC-DEF-09 | Won't delete without confirmation | E2 | "Delete weather_notification" without specifying intent | Agent confirms before running delete |
| TC-DEF-10 | Validate before create | E2 | Submit a definition with a duplicate `taskReferenceName` | Agent catches the duplicate before sending |

---

## 7. Task definitions (CRUD)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-TDF-01 | List task defs | E2 | "List task definitions" | `conductor task list --json` |
| TC-TDF-02 | Get task def | E2 | "Show task def process_order" | `conductor task get process_order` |
| TC-TDF-03 | Create task def from JSON | E2 | "Create a task definition for `process_order` with a 30-second response timeout" | Writes JSON to file, `conductor task create file.json` |
| TC-TDF-04 | Update task def | E2 | "Increase retryCount on process_order to 5" | Reads existing, updates, sends |
| TC-TDF-05 | Delete task def | E2 | "Delete the process_order task def" | Confirms; deletes |
| TC-TDF-06 | Fallback path is missing | E1 (fallback) | When using fallback script, ask to list task defs | Agent reports the fallback doesn't support task-def CRUD; offers to install CLI |

---

## 8. Workflow execution

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-RUN-01 | Start async with inline input | E2 | "Run weather_notification with city=SF" | `conductor workflow start -w weather_notification -i '{...}'`; returns workflowId |
| TC-RUN-02 | Start with file input | E2 | "Run with this large input" + bigger payload | Writes JSON file, uses `-f input.json` |
| TC-RUN-03 | Start synchronous | E2 | "Run and wait for completion" | Uses `--sync`; returns terminal status |
| TC-RUN-04 | Wait until specific task | E2 | "Run and wait until the approval step" | Uses `--sync -u approval` |
| TC-RUN-05 | Specific version | E2 | "Run v3 of order_processing" | `--version 3` |
| TC-RUN-06 | With correlation ID | E2 | "Run order_processing for order #42" | `--correlation order-42` |
| TC-RUN-07 | Get execution by ID | E2 | "What's the status of `wf-123`?" | `conductor workflow get-execution wf-123 -c` |
| TC-RUN-08 | Quick status | E2 | "Just give me the status of `wf-123`" | `conductor workflow status wf-123` |
| TC-RUN-09 | Get by correlation ID | E2 | "Show me the workflow for order #42" | Resolves via correlation ID |

---

## 9. Workflow monitoring & search

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-MON-01 | Search by status | E2 | "Show all running workflows" | `conductor workflow search -s RUNNING` |
| TC-MON-02 | Search by name + status | E2 | "Show failed weather_notification runs" | `-w weather_notification -s FAILED` |
| TC-MON-03 | Search by time range | E2 | "Failed workflows from yesterday" | Uses `--start-time-after` / `--start-time-before` |
| TC-MON-04 | Render results as table | E2 | TC-MON-01 result | Markdown table with workflowId, name, status, startTime |
| TC-MON-05 | Pagination respected | E2 | "First 50 failed workflows" | `-c 50` |
| TC-MON-06 | Diagnose failure | E2 | "Why did `wf-456` fail?" | Loads execution, identifies failed task + reason |

---

## 10. Workflow management

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-MGT-01 | Pause running workflow | E2 | "Pause `wf-123`" | `conductor workflow pause wf-123` |
| TC-MGT-02 | Resume paused workflow | E2 | "Resume `wf-123`" | `conductor workflow resume wf-123` |
| TC-MGT-03 | Terminate with reason | E2 | "Terminate `wf-123`, customer cancelled" | Uses `--reason` |
| TC-MGT-04 | Restart completed | E2 | "Restart `wf-123`" | `conductor workflow restart wf-123` |
| TC-MGT-05 | Restart with latest definition | E2 | "Restart `wf-123` on the latest version" | Adds `--use-latest` |
| TC-MGT-06 | Retry last failed task | E2 | "Retry `wf-123`" | `conductor workflow retry wf-123` |
| TC-MGT-07 | Rerun from a specific task | E2 | "Rerun `wf-123` from validate_order" | `--task-id` |
| TC-MGT-08 | Skip a task | E2 | "Skip the email step in `wf-123`" | `conductor workflow skip-task` |
| TC-MGT-09 | Jump to a task | E2 | "Jump `wf-123` to fulfill_order" | `conductor workflow jump` |
| TC-MGT-10 | Distinguish retryable vs terminal | E2 | Workflow that failed with `FAILED_WITH_TERMINAL_ERROR` | Agent refuses retry, explains why |
| TC-MGT-11 | Batch retry | E2 | "Retry every failed weather_notification from today" | Searches first, then retries each in turn |

---

## 11. Task signaling (WAIT / HUMAN / async)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SIG-01 | Identify blocking task | E2 | "Why is `wf-123` stuck?" | Lists tasks, identifies task in IN_PROGRESS with type WAIT/HUMAN |
| TC-SIG-02 | Signal async | E2 | "Approve the wait task in `wf-123`" | `conductor task signal --status COMPLETED ...` |
| TC-SIG-03 | Signal sync | E2 | "Approve and tell me what runs next" | `conductor task signal-sync ...` |
| TC-SIG-04 | Pass output payload | E2 | "Approve with payment ID pay-456" | `--output '{"paymentId":"pay-456"}'` |
| TC-SIG-05 | Reject with FAILED | E2 | "Reject the wait task" | `--status FAILED` |
| TC-SIG-06 | Reject with terminal | E2 | "Permanently reject — don't retry" | `--status FAILED_WITH_TERMINAL_ERROR` |
| TC-SIG-07 | HUMAN task | E2 | Workflow with a HUMAN task | Same signaling pattern as WAIT |

---

## 12. Task type coverage

One workflow per task type, registered and run end-to-end. Drive each via natural-language prompts to the agent.

| ID | Task type | Env | Test idea | Expected |
|----|-----------|-----|-----------|----------|
| TC-TYP-01 | SIMPLE | E2 | Workflow → SIMPLE task → registered worker (Python) | Worker polls, executes, returns; workflow completes |
| TC-TYP-02 | HTTP | E2 | HTTP GET to a public JSON endpoint | `${ref.output.response.body}` accessible downstream |
| TC-TYP-03 | INLINE | E2 | INLINE with `$.value * 2` | All `$.x` declared in inputParameters |
| TC-TYP-04 | JSON_JQ_TRANSFORM | E2 | Filter array of items | `result` has expected shape |
| TC-TYP-05 | SWITCH (value-param) | E2 | Branch on `${workflow.input.type}` | Correct branch executes |
| TC-TYP-06 | SWITCH (javascript) | E2 | JS expression branching | All `$.x` declared |
| TC-TYP-07 | FORK_JOIN | E2 | Two parallel HTTP calls + JOIN | Both branches run; JOIN aggregates |
| TC-TYP-08 | DO_WHILE | E2 | Loop 5 iterations with self-reference | `iteration` increments; loop_ref output present |
| TC-TYP-09 | WAIT (signal) | E2 | Wait until external signal | Workflow stays IN_PROGRESS until signaled |
| TC-TYP-10 | WAIT (duration) | E2 | `"duration": "10s"` | Resumes ~10 s later |
| TC-TYP-11 | WAIT (until) | E2 | `"until": "<timestamp 1 min from now>"` | Resumes at that time |
| TC-TYP-12 | HUMAN | E2 | HUMAN task signaled via UI or API | Behaves like WAIT signal |
| TC-TYP-13 | SUB_WORKFLOW | E2 | Parent calling registered child | Parent waits; reads child output |
| TC-TYP-14 | START_WORKFLOW | E2 | Parent fires-and-forgets a child | Parent completes immediately; output has child's `workflowId` |
| TC-TYP-15 | DYNAMIC | E2 | `dynamicTaskNameParam` resolves to a real task | Resolved task runs |
| TC-TYP-16 | FORK_JOIN_DYNAMIC | E2 | Generate 3 branches at runtime | All branches run; JOIN aggregates |
| TC-TYP-17 | EXCLUSIVE_JOIN | E2 | Two branches racing | First to complete wins |
| TC-TYP-18 | EVENT | E2 | Publish to `conductor:my_event` | Event sink shows the message |
| TC-TYP-19 | KAFKA_PUBLISH | E2 + Kafka | Publish to test topic | Kafka receives message; key/headers preserved |
| TC-TYP-20 | SET_VARIABLE | E2 | Set then read in subsequent task | Variable visible via `${workflow.variables.x}` |
| TC-TYP-21 | TERMINATE | E2 | Early-exit with COMPLETED | Workflow ends in COMPLETED with provided output |
| TC-TYP-22 | NOOP | E2 | Use as default branch | Completes immediately, no side effect |
| TC-TYP-23 | LLM_CHAT_COMPLETE | E2/E5 + provider | Chat with OpenAI provider | `result` contains response text; token counts in output |
| TC-TYP-24 | LLM_TEXT_COMPLETE | Same | Single completion | `result`, `tokenUsed` in output |
| TC-TYP-25 | LLM_GENERATE_EMBEDDINGS | Same | Embed a string | `result` is a float array |
| TC-TYP-26 | GENERATE_IMAGE | Same | DALL-E or similar | `url` or `b64_json` returned |
| TC-TYP-27 | GENERATE_AUDIO | Same | TTS | `media` array with location + mimeType |
| TC-TYP-28 | GENERATE_VIDEO | Same | Sora or Veo | `media` with video URL; async polling handled |
| TC-TYP-29 | LLM_INDEX_TEXT | Same + vectorDB | Index a doc into Pinecone | Returns success; subsequent search finds it |
| TC-TYP-30 | LLM_STORE_EMBEDDINGS | Same | Store pre-computed | Stored under docId |
| TC-TYP-31 | LLM_SEARCH_INDEX | Same | Semantic search | Returns hits |
| TC-TYP-32 | LLM_SEARCH_EMBEDDINGS | Same | Vector search | Returns hits |
| TC-TYP-33 | LLM_GET_EMBEDDINGS | Same | Retrieve by docId | Returns float array |
| TC-TYP-34 | LIST_MCP_TOOLS | E2 + MCP server | List tools from MCP endpoint | Returns array of tool descriptors |
| TC-TYP-35 | CALL_MCP_TOOL | Same | Call a known tool | Returns `content` array |

### 12b. Agent task types

All rows need **E2+AI** (see §4.5) and the deployed agents named by each example. Use `python skills/conductor/examples/agents/python/weather_agent.py deploy` plus `... serve` for the basic invocation and approval rows. The conversational-resume row needs an agent with a `human_tool`; do not substitute an `approval_required` tool. A2A rows additionally need `conductor.a2a.server.enabled=true` and a workflow exposed at `/api/a2a/workflow/<wf>`.

| ID | Task type | Env | Test idea | Expected |
|----|-----------|-----|-----------|----------|
| TC-TYP-36 | AGENT (conductor, basic) | E2+AI | Register `examples/workflows/agent-invoke.json`; start with `{"prompt":"Weather in SF?"}` | Task COMPLETED; output has `text`, `executionId`, `state: completed`; `executionId` opens as a workflow in the UI |
| TC-TYP-37 | AGENT approval waiting = true | E2+AI | `agent-approval-in-workflow.json` with a prompt that triggers `weather_agent`'s `approval_required` tool | First AGENT task COMPLETED with `waiting: true`, `pendingTool.toolCalls[0].name == "notify_ops"`, `tool_name: null`, `response_schema.required == ["approved"]`; workflow uses the explicit `/respond {"approved":true}` channel |
| TC-TYP-38 | AGENT conversational resume via executionId | E2+AI | Run `agent-hitl-resume.json` against an agent with a `human_tool`; signal the parent HUMAN task with `{"answer": "..."}` | `pendingTool.response_schema` contains `response`; second AGENT task carries `executionId` + `prompt`; the same agent execution continues and completes without an approval normalizer |
| TC-TYP-39 | AGENT (a2a) | E2+AI + A2A | `a2a-remote-agent.json` against the exposed workflow's A2A URL, `AGENT_TOKEN` secret set | `state: completed`; `text`, `taskId`, `contextId` present; `Authorization` header came from `${workflow.secrets.AGENT_TOKEN}` |
| TC-TYP-40 | AGENT (a2a) input-required | E2+AI + A2A | Remote agent that asks a follow-up question | SWITCH `input-required` branch re-calls with the same `contextId` **and** `taskId`; second call completes the same remote task |
| TC-TYP-41 | GET_AGENT_CARD | E2+AI + A2A | `{"agentUrl": "<exposed workflow A2A URL>"}` | `output.agentCard` with name and skills |
| TC-TYP-42 | CANCEL_AGENT | E2+AI | `{"agentType":"conductor","executionId":"<running id>","reason":"test"}` | `{executionId, canceled: true}`; `conductor agent status <id>` shows `canceled` |
| TC-TYP-43 | WAIT → TERMINATE race (agent-cancel.json) | E2+AI | Temporarily shorten the example's `20m` WAIT, then run it with a longer-running prompt | WAIT elapses before the agent completes; TERMINATE branch wins; AGENT task ends CANCELED (not FAILED); child agent execution canceled |
| TC-TYP-44 | Misconfig: `agentType` omitted with `name` | E2+AI | AGENT with `name` + `prompt` but no `agentType` | Fails with `AGENT requires 'agentUrl'`; agent explains the default is `a2a` and adds `agentType: "conductor"` |
| TC-TYP-45 | Unserved tool workers | E2+AI | Stop the `serve` process; run `agent-invoke.json` with a prompt that needs `get_weather` | Tool task sits SCHEDULED, AGENT task IN_PROGRESS; agent diagnoses "no `serve()` running" (F3), not a provider or auth problem; restarting `serve` completes the run |

### 12c. Agent SDK lifecycle

Uses `skills/conductor/examples/agents/python/*.py` on **E2+AI** with `pip install 'conductor-python[agents]'`.

| ID | Verb | Env | Steps | Expected |
|----|------|-----|-------|----------|
| TC-SDK-01 | run | E2+AI | `python weather_agent.py run "Weather in SF?"` | Result printed with an `execution_id`; `conductor agent execution --name weather_agent --since 1h` lists it |
| TC-SDK-02 | deploy + list | E2+AI | `python weather_agent.py deploy` | Prints `required workers: [...]`; `conductor agent list` shows `weather_agent`; `conductor agent get weather_agent` shows `model: openai/gpt-4o-mini` and both tools |
| TC-SDK-03 | serve | E2+AI | `python weather_agent.py serve` in a second terminal; run TC-SDK-01 again | Tool tasks complete; stopping `serve` and re-running leaves the tool task SCHEDULED (TC-TYP-45) |
| TC-SDK-04 | execution / status / stream | E2+AI | `conductor agent execution --name weather_agent --since 1h`, `conductor agent status <id>`, `conductor agent stream <id>` | Executions listed with status; stream prints real event types (`thinking`, `tool_call`, `tool_result`, `done`); UI `/agentExecutions/<id>` opens |
| TC-SDK-05 | respond --approve | E2+AI | Prompt that triggers `notify_ops` | Run reports `waiting`; `conductor agent respond <id> --approve` continues it; `--deny --reason "..."` rejects; a plain AGENT resume with prompt "approved" does **not** approve |
| TC-SDK-06 | cancel | E2+AI | `python3 skills/conductor/scripts/conductor_api.py agent-cancel --id <id> --reason test` or `conductor workflow terminate <id>` | `conductor agent status <id>` shows `canceled`; no invented `conductor agent cancel` |
| TC-SDK-07 | schedule a deployed agent | E2+AI | `conductor schedule create -n weather_agent-daily -c "0 0 6 * * ?" -w weather_agent -i '{"prompt":"Weather in SF?"}'` | Schedule listed; agent notes `serve()` must be running when it fires; delete afterwards |
| TC-SDK-08 | mock_run offline | any | `pytest test_weather_agent.py -k offline` with no server and no provider key | Passes with no network access |
| TC-SDK-09 | CorrectnessEval live | E2+AI | `pytest test_weather_agent.py -m live` | `suite.all_passed`; `notify_ops` not used for a plain weather question |
| TC-SDK-10 | LangChain plain vs wrapper | E2+AI | Run `langchain_bridge.py`; then swap the import to `langchain.agents.create_agent` and re-run | Wrapper: `conductor agent get langchain_assistant` shows the extracted tool (compiled). Plain: detected as LangGraph and may compile to a single passthrough worker; agent explains the difference and that passthrough needs `serve()` |

### 12d. Multi-agent strategies and remaining capabilities

Uses the Python snippets from `skills/conductor/references/agent-sdks.md` §6–§7 on **E2+AI** (a provider key configured on the server); `runtime.plan(agent)` is enough to check a compiled shape without spending tokens. TC-SDK-16 needs the platform credentials as server secrets, TC-SDK-17 needs `agentspan.skills.enabled=true`, TC-SDK-19 needs `conductor.a2a.server.enabled=true`.

| ID | Strategy / capability | Env | Steps | Expected |
|----|------------------------|-----|-------|----------|
| TC-STR-01 | HANDOFF | E2+AI | `plan()` then run `Agent(agents=[billing, technical, sales], strategy=Strategy.HANDOFF)` with "My invoice is wrong" | Compiled def has one `SUB_WORKFLOW` per specialist; the billing specialist speaks last (parent summarizes only with `synthesize=True`); `conductor agent stream <id>` shows a `handoff` event |
| TC-STR-02 | ROUTER | E2+AI | Parent with `strategy=Strategy.ROUTER, router=selector` (a separate `Agent`); repeat with a Python callable as `router=` | Compiled def contains the selector step; exactly one child `SUB_WORKFLOW` executes per run; with the callable, `requiredWorkers` lists the router worker and the run stalls until `serve()` runs |
| TC-STR-03 | SEQUENTIAL | E2+AI | `researcher >> writer >> editor`; also the explicit `strategy=Strategy.SEQUENTIAL` form | Child `SUB_WORKFLOW`s chained in order; each child's input is the previous child's output; `mock_run` passes offline with no server / LLM |
| TC-STR-04 | PARALLEL | E2+AI | Three analysts with `strategy=Strategy.PARALLEL`; once with the parent `model` omitted | Compiled def has a `FORK_JOIN` with three branches, a `JOIN` and the parent's synthesis LLM task; the parent model is inherited from the first child when omitted |
| TC-STR-05 | SWARM | E2+AI | Two children, `handoffs=[OnTextMention(...), OnToolResult(...)]`, `max_turns=6`; then try a tool named `transfer_x` and an agent named `done` | Each child gets a `transfer_to_<peer>` tool in the compiled def; the reserved names are rejected or flagged; the run ends at `max_turns` at the latest |
| TC-STR-06 | ROUND_ROBIN | E2+AI | `allowed_transitions={"developer": ["reviewer"], "reviewer": ["developer", "approver"]}`, `termination=TextMentionTermination("APPROVED") \| MaxMessageTermination(12)` | Rotation follows the allow-list; `validate_strategy` raises `StrategyViolation` on a forbidden transition; the run stops on "APPROVED" or at 12 messages, whichever first |
| TC-STR-07 | RANDOM | E2+AI | Three personas, `strategy=Strategy.RANDOM`, `max_turns=6`, a `termination`; run twice | Speaker order differs between the runs; both terminate; `allowed_transitions` (if set) is respected |
| TC-STR-08 | MANUAL | E2+AI | `strategy=Strategy.MANUAL, max_turns=3`; `runtime.start()`; answer with `conductor agent respond <id> -m "editor"` | `requiredWorkers` includes `<name>_process_selection`; every turn pauses with `waiting: true` + `pendingTool.response_schema`; the respond picks the next agent; without `serve()` the selection task sits SCHEDULED |
| TC-STR-09 | PLAN_EXECUTE | E2+AI | `strategy=Strategy.PLAN_EXECUTE, planner=..., tools=[...], fallback=..., fallback_max_turns=3, planner_context=[{"text": ...}, {"url": ..., "headers": {"Authorization": "Bearer ${DOCS_TOKEN}"}}], credentials=["DOCS_TOKEN"]`; once omit `planner=`; once make a tool fail | Missing `planner=` or empty `tools=` is rejected; the plan runs as a sub-workflow and replans after the failing step; the fallback runs when planning fails; `${DOCS_TOKEN}` is resolved server-side and never appears in the definition |
| TC-SDK-11 | agent_tool + scatter_gather | E2+AI | `tools=[agent_tool(child, description=..., max_calls=2)]`; `scatter_gather("audit", worker=auditor, model=..., instructions=..., retry_count=3, fail_fast=False)` over a 5-item list | `agent_tool` compiles to `SUB_WORKFLOW` and control returns to the parent; `scatter_gather` compiles to `FORK_JOIN_DYNAMIC`; a failing branch is retried and, with `fail_fast=False`, does not fail the run; `/conductor-optimize` flags a child without `max_turns` under F10 |
| TC-SDK-12 | SemanticMemory | E2+AI | `SemanticMemory(max_results=3)` + `memory.add(...)` + `@tool recall`; run twice with the same `sessionId` without `memory=`, then with it | The same `sessionId` alone gives no recall of the first run (output `contextId` equals the `sessionId`); with `memory=` the second run's `recall` returns the stored facts |
| TC-SDK-13 | mcp_tool / http_tool / api_tool | E2+AI + MCP server | Agent with the three tool kinds; `plan()`; run once with and once without the origin in `conductor.ai.outbound.allowed-origins` | `requiredWorkers` is empty; compiled def has `LIST_MCP_TOOLS` / `CALL_MCP_TOOL` and `HTTP` tasks; discovery fails when the origin is not allowed; `${API_TOKEN}` is resolved from the server secret |
| TC-SDK-14 | Code execution + CLI | E2+AI (+ Docker) | `local_code_execution=True, allowed_languages=["python"]`; `code_execution=CodeExecutionConfig(executor=DockerCodeExecutor(...))`; `cli_commands=True, cli_allowed_commands=["gh", "aws"], credentials=["GH_TOKEN"]` | Python snippets run; a non-allow-listed language or command (`curl`, `rm`) is refused; `sh -c` is refused (`allow_shell=False`); `/conductor-optimize` flags an empty allow-list CRITICAL under F2 |
| TC-SDK-15 | Claude Agent SDK passthrough | E2+AI + `ANTHROPIC_API_KEY` where `serve` runs | `pip install 'conductor-python[claude]'`; `Agent(model=ClaudeCode("sonnet", permission_mode=ClaudeCode.PermissionMode.ACCEPT_EDITS), tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"], max_turns=50)`; then try `tools=[my_tool]` | `plan()` shows a single passthrough worker; nothing progresses until `serve()` runs; a custom `@tool` raises; the calling `AGENT` task still uses `agentType: "conductor"` |
| TC-SDK-16 | Hosted Foundry / Bedrock with autoRunTools | E2+AI + platform creds | `AGENT` with `agentType: "microsoft-foundry"`, `credentials{}` from `${workflow.secrets.AZURE_CRED.*}`, `rawConfig{endpoint, assistantId}`, a worker registered for `get_revenue`; repeat with `agentType: "bedrock"` + `agentUrl: "bedrock://..."` | The agent's `get_revenue` call appears as a SIMPLE task `get_revenue` with `_toolCallId` / `_toolName` / `_agentExecutionId` in its input; the worker's result resumes the platform run; `maxToolTurns` caps the rounds; Bedrock cancel is reported as unsupported; a Foundry run left idle past 10 minutes fails |
| TC-SDK-17 | Skill package | E2+AI + `agentspan.skills.enabled=true` | `conductor skill run <path> "..." --model openai/gpt-4o-mini`; `conductor skill load <path> --model ...`; `conductor agent run --name <skill>` with and without `conductor skill serve <path>` | Run completes; `conductor agent list` shows the skill (framework `skill`); `scripts/` appear as `<skill>__<script>` tools; without `skill serve` the tool task sits SCHEDULED; `skill register` fails when the flag is off |
| TC-SDK-18 | C# Semantic Kernel | E2+AI + .NET 8 + csharp-sdk checkout | `SemanticKernelAgent.From("calculator", "openai/gpt-4o-mini", "...", new CalculatorPlugin())`; `RunAsync`, `PlanAsync`, `DeployAsync`, `ServeAsync` | Project references build (packages not on NuGet); `PlanAsync` lists the `[KernelFunction]` methods as required workers; `conductor agent get calculator` shows `model: openai/gpt-4o-mini`; the run completes only while `ServeAsync` is running |
| TC-SDK-19 | A2A server exposure | E2+AI + `conductor.a2a.server.enabled=true` | Register a workflow with a HUMAN task and `metadata.a2a.enabled=true` via `POST /api/metadata/workflow?overwrite=true`; fetch `/api/a2a/workflow/<name>/.well-known/agent-card.json`; call it with `GET_AGENT_CARD` + `AGENT` a2a | Card returned with skills; `message/send` starts the workflow; the HUMAN task shows as `input-required` and resumes with `contextId` + `taskId`; the same workflow registered with `conductor workflow create` has no card (metadata dropped) |

---

### 12e. AGENT task live conformance (executed 2026-09-04 against conductor-server 3.32.1)

Three scripts drive every mode of the `AGENT` task against a local server started with `conductor server start` (A2A rows with `CONDUCTOR_A2A_SERVER_ENABLED=true CONDUCTOR_A2A_SERVER_EXPOSE_ALL=true CONDUCTOR_A2A_CLIENT_ALLOW_PRIVATE_NETWORK=true`). Three throwaway native agents (`lt_weather_agent` with an `approval_required` tool, `lt_clarifier` with a `human_tool`, `lt_summarizer` with no tools) are deployed and served by the SDK. Two shipped examples came out of this suite and are exercised by it: `agent-approval-in-workflow.json` (deterministic in-workflow approval: HUMAN → HTTP respond → poll) and `a2a-expose-agent.json` (deployed agent through the A2A workflow facade). All rows pass.

| ID | Check | Env | Procedure | Observed | Result |
|----|-------|-----|-----------|----------|--------|
| TC-TYP-46 | deploy 3 agents via SDK | E2+AI | live suite `run_suite.py` | ['lt_weather_agent', 'lt_clarifier', 'lt_summarizer'] | PASS |
| TC-TYP-47 | GET /agent/list shows them | E2+AI | live suite `run_suite.py` | ['lt_clarifier', 'lt_inline_hello', 'lt_summarizer', 'lt_weather_agent'] | PASS |
| TC-TYP-48 | approval gate: AGENT task COMPLETED with waiting=true | E2+AI | live suite `run_suite.py` | {'state': 'input-required', 'tool': None} | PASS |
| TC-TYP-49 | GET /agent/{id}/status isWaiting + pendingTool | E2+AI | live suite `run_suite.py` | {'status': 'RUNNING', 'tool': None} | PASS |
| TC-TYP-50 | respond {approved:true} completes the run | E2+AI | live suite `run_suite.py` | {'status': 'COMPLETED', 'result': "It seems there was a misunderstanding, as I don't have context on a previous conversation. Could you clarify what topic "} | PASS |
| TC-TYP-51 | human_tool: first AGENT completes with waiting=true and a question | E2+AI | live suite `run_suite.py` | {'question': 'None', 'tool': None} | PASS |
| TC-TYP-52 | HUMAN task is IN_PROGRESS in the parent | E2+AI | live suite `run_suite.py` | IN_PROGRESS | PASS |
| TC-TYP-53 | resume AGENT (executionId + prompt) completes the same run with the answer | E2+AI | live suite `run_suite.py` | {'final': 'The weather in Paris today is likely to be mild, but for the most current details, check a reliable weather source.', 'same_execution': True} | PASS |
| TC-TYP-54 | FORK_JOIN of two AGENT tasks completes with distinct executionIds | E2+AI | live suite `run_suite.py` | {'a': 'Conductor is a robust workflow engine designed for durabilit', 'b': 'The weather in Lisbon is currently a severe thunderstorm, wi'} | PASS |
| TC-TYP-55 | TERMINATE parent → AGENT task CANCELED and child TERMINATED | E2+AI | live suite `run_suite.py` | {'parent': 'TERMINATED', 'task': 'CANCELED', 'child': 'TERMINATED'} | PASS |
| TC-TYP-56 | CANCEL_AGENT {executionId} → {canceled:true}, run canceled | E2+AI | live suite `run_suite.py` | {'output': {'executionId': '286e5aff-e410-402a-a4a4-6952bc448696', 'canceled': True}, 'run': 'TERMINATED'} | PASS |
| TC-TYP-57 | AGENT version=1 pin runs | E2+AI | live suite `run_suite.py` | COMPLETED | PASS |
| TC-TYP-58 | AGENT version=99 → FAILED with 'Agent not found' | E2+AI | live suite `run_suite.py` | Task 6fecfffc-21c1-4ee6-b08f-0405e3dc8924 failed with status: FAILED and reason: 'Conductor agent call failed: Agent not | PASS |
| TC-TYP-59 | missing prompt → FAILED_WITH_TERMINAL_ERROR 'AGENT requires prompt' | E2+AI | live suite `run_suite.py` | Task b5914c1c-fe60-483a-808e-2b3d1b2b2829 failed with status: FAILED and reason: 'AGENT requires 'prompt'' | PASS |
| TC-TYP-60 | agentType omitted → defaults to a2a → 'AGENT requires agentUrl' terminal error | E2+AI | live suite `run_suite.py` | Task b8d90dfe-19a0-4a97-acd2-5e1dc1c2d5ee failed with status: FAILED and reason: 'AGENT requires 'agentUrl'' | PASS |
| TC-TYP-61 | per-call sessionId/context/model/idempotencyKey accepted; contextId == sessionId | E2+AI | live suite `run_suite.py` | {'contextId': 'sess-42', 'state': 'completed'} | PASS |
| TC-TYP-62 | inline agentConfig in AGENT task runs without a prior deploy | E2+AI | live suite `run_suite.py` | {'agentName': 'lt_inline_hello', 'text': "Hello! Hope you're doing well.", 'reason': ''} | PASS |
| TC-TYP-63 | AGENT inside DO_WHILE ran 2 rounds carrying state | E2+AI | live suite `run_suite.py` | {'iterations': 2, 'final': 'Durable execution supports agents during crashes.'} | PASS |
| TC-TYP-64 | register agent_approval_in_workflow | E2+AI | live suite `approval_flow.py` (= `examples/workflows/agent-approval-in-workflow.json`) |  | PASS |
| TC-TYP-65 | AGENT completes with waiting=true and an approval-gate pendingTool | E2+AI | live suite `approval_flow.py` (= `examples/workflows/agent-approval-in-workflow.json`) | {'tool': ['notify_ops'], 'HUMAN': 'IN_PROGRESS'} | PASS |
| TC-TYP-66 | HTTP respond {approved:true} → 200 | E2+AI | live suite `approval_flow.py` (= `examples/workflows/agent-approval-in-workflow.json`) | COMPLETED | PASS |
| TC-TYP-67 | approval took the deterministic normalize_noop path (no LLM normalizer task) | E2+AI | live suite `approval_flow.py` (= `examples/workflows/agent-approval-in-workflow.json`) | ['lt_weather_agent_approval_human_normalize_switch__1', 'lt_weather_agent_approval_human_normalize_noop__1', 'notify_ops ran'] | PASS |
| TC-TYP-68 | DO_WHILE poll waited for completion; workflow COMPLETED with the agent's final result | E2+AI | live suite `approval_flow.py` (= `examples/workflows/agent-approval-in-workflow.json`) | {'wf': 'COMPLETED', 'agentStatus': 'COMPLETED', 'iterations': 1, 'result': "It seems there was a thunderstorm warning for Miami that warranted notifying the ops team. If  | PASS |
| TC-TYP-69 | A2A server enabled: GET /api/a2a/workflow lists exposed workflows (expose-all) | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | [{'agentCard': 'http://localhost:8080/api/a2a/workflow/helpdesk_agent/.well-known/agent-card.json', 'url': 'http://localhost:8080/api/a2a/workflow/helpdesk_agent', 'name' | PASS |
| TC-TYP-70 | workflow facade agent card resolves | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'name': 'lt_summarizer', 'url': 'http://localhost:8080/api/a2a/workflow/lt_summarizer', 'skills': 1} | PASS |
| TC-TYP-71 | native agent facade: GET /api/a2a/agent + card for lt_clarifier | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'listing': "[{'agentCard': 'http://localhost:8080/api/a2a/agent/lt_clarifier/.well-known/agent-card.json', 'url': 'http://localhost:", 'card_url': 'http://localhost:8080 | PASS |
| TC-TYP-72 | GET_AGENT_CARD + AGENT a2a against the native agent facade completes with a readable answer (artifacts[0].parts[0].data.result) | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'wf': 'COMPLETED', 'card': 'lt_summarizer', 'state': 'completed', 'answer': 'The conductor enables the sharing of workflows and agents through an A2A (Applic', 'reason': | PASS |
| TC-TYP-73 | GET_AGENT_CARD + AGENT a2a against the workflow facade via the exposed wrapper workflow completes with a readable answer (artifacts[0].parts[0].data.result) | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'wf': 'COMPLETED', 'card': 'lt_a2a_summarizer', 'state': 'completed', 'answer': 'Conductor provides access to workflows and agents through an application-to-appl', 'reas | PASS |
| TC-TYP-74 | a2a input-required: AGENT task COMPLETED with state=input-required, taskId+contextId present | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'state': 'input-required', 'taskId': '5affa90a-cdb', 'text': "Agent is awaiting input. Send another message/send carrying this task's id to pr", 'reason': ''} | PASS |
| TC-TYP-75 | a2a resume with taskId+contextId completes the same remote task | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'state': 'completed', 'same_taskId': True, 'text': 'None', 'reason': ''} | PASS |
| TC-TYP-76 | CANCEL_AGENT a2a {agentUrl, taskId} -> remote task canceled | E2+AI | live suite `a2a_suite.py` (incl. `examples/workflows/a2a-expose-agent.json`) | {'wf': 'COMPLETED', 'remote_state': 'canceled', 'reason': ''} | PASS |

## 13. Visualization

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-VIS-01 | Sequential flow | E2 | "Show me a diagram of weather_notification" | `flowchart TD` with `-->` between two HTTP nodes |
| TC-VIS-02 | SWITCH | E2 | Workflow with SWITCH | Diamond node, labeled edges per case + default |
| TC-VIS-03 | FORK_JOIN | E2 | Workflow with FORK_JOIN | Fork → branches → JOIN |
| TC-VIS-04 | DO_WHILE | E2 | Workflow with DO_WHILE | Loop edge from body back to loop node |
| TC-VIS-05 | SUB_WORKFLOW | E2 | Parent + child | Rounded sub-workflow node |
| TC-VIS-06 | WAIT / HUMAN | E2 | Workflow with WAIT | Parallelogram node |
| TC-VIS-07 | No forbidden chars in edge labels | E2 | Any | Edge labels do not contain `{}[]()` |
| TC-VIS-08 | UI link offered | E2 | After diagram, agent gives UI URL | URL is `BASE_URL/workflowDef/<name>` with `/api` stripped |

---

## 14. Schedules (OSS)

Per the latest skill version, schedules are OSS, not Orkes-only.

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SCH-01 | List schedules | E2 | "List my schedules" | `conductor schedule list` |
| TC-SCH-02 | Create daily schedule | E2 | "Schedule cleanup_workflow daily at 2am" | Writes JSON, `conductor schedule create file.json` with cron `0 0 2 * * ?` |
| TC-SCH-03 | Create with correlation pattern | E2 | "Use a daily correlation ID" | `correlationId` in `startWorkflowRequest` includes a date-derived value |
| TC-SCH-04 | Update schedule | E2 | "Change cleanup to 3am" | Reads existing, updates cron, sends |
| TC-SCH-05 | Pause schedule | E2 | "Pause the cleanup schedule" | `conductor schedule pause cleanup` |
| TC-SCH-06 | Resume schedule | E2 | "Resume cleanup" | `conductor schedule resume cleanup` |
| TC-SCH-07 | Delete schedule | E2 | "Delete cleanup" | Confirms, deletes |
| TC-SCH-08 | Cron parses correctly | E2 | "Every 15 minutes" | Generates `0 */15 * * * ?` |
| TC-SCH-09 | Quartz quirk respected | E2 | "Every Monday at noon" | Day-of-month is `?` (since dow is set) |
| TC-SCH-10 | Search executions by correlation | E2 | "Show me last 50 scheduled cleanup runs" | Searches by `correlationId:scheduled-*` (or whatever pattern was used) |

---

## 15. Orkes-only features (E5)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-ORK-01 | Connect to developer.orkescloud.com | E5 | Setup with key/secret for sandbox | `conductor workflow list` succeeds |
| TC-ORK-02 | Secret put | E5 | "Save STRIPE_KEY = sk_test_..." | `conductor secret put STRIPE_KEY <value>`; value never echoed |
| TC-ORK-03 | Secret get (name only) | E5 | "Do I have a Stripe secret?" | Lists name; does NOT echo the value |
| TC-ORK-04 | Secret list | E5 | "List my secrets" | Names only, no values |
| TC-ORK-05 | Secret delete | E5 | "Delete STRIPE_KEY" | Confirms, deletes |
| TC-ORK-06 | Reference secret in workflow | E5 | Use `${workflow.secrets.STRIPE_KEY}` in HTTP header | Workflow runs; secret value resolved server-side |
| TC-ORK-07 | Webhook list | E5 | "List webhooks" | `conductor webhook list` |
| TC-ORK-08 | Webhook create | E5 | "Create a GitHub webhook for github_pr_handler workflow" | Writes JSON, creates, surfaces returned URL |
| TC-ORK-09 | Webhook returns URL | E5 | After TC-ORK-08 | Agent shows the actual returned URL — not a placeholder |
| TC-ORK-10 | Webhook delete | E5 | "Delete the GitHub webhook" | Confirms, deletes |
| TC-ORK-11 | Enterprise command on OSS fails clearly | E2 | Try `conductor secret list` against OSS | Agent reports it's an Orkes-only feature; suggests checking server endpoint |

---

## 16. Optimization checklist coverage

For each item in `references/optimization.md`, prepare a workflow that violates it and confirm `/conductor-optimize` reports it.

### A. Structure & maintainability

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-A1 | A1 Description present | `description: ""` | WARN |
| TC-OPT-A2 | A2 ownerEmail set | No ownerEmail | WARN |
| TC-OPT-A3 | A3 schemaVersion: 2 | `schemaVersion: 1` | WARN |
| TC-OPT-A4 | A4 Task count | 105 tasks | WARN |
| TC-OPT-A5 | A5 Descriptive task ref | `taskReferenceName: "task1"` | INFO/WARN |
| TC-OPT-A6 | A6 Three timeouts (educational) | Task def missing pollTimeoutSeconds | Agent explains the three timeouts and points to B1 for severity |
| TC-OPT-A7 | A7 Versioning hygiene | Workflow edited in place with executions in last 30d | WARN (manually verify against execution history) |

### B. Reliability

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-B1 | B1 Task timeouts | `responseTimeoutSeconds: 0` | CRITICAL |
| TC-OPT-B2 | B2 Workflow timeout | No `timeoutSeconds` | WARN |
| TC-OPT-B3 | B3 Retry policy | `retryCount: 0` on email task | WARN |
| TC-OPT-B4 | B4 failureWorkflow | None set; workflow mutates external state | WARN |
| TC-OPT-B5 | B5 DO_WHILE cap | No `iteration < N` clause | CRITICAL |
| TC-OPT-B6 | B6 Optional branches | Best-effort notification, not optional | INFO |
| TC-OPT-B7 | B7 Rate / concurrent limits | External API task with no rate limit | WARN |

### C. Performance & complexity

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-C1 | C1 INLINE scope | 60-line INLINE script | WARN |
| TC-OPT-C2 | C2 Prefer JQ | INLINE doing pure data shaping | INFO |
| TC-OPT-C3 | C3 Bounded fan-out | Static FORK_JOIN with 50 branches | WARN |
| TC-OPT-C4 | C4 asyncComplete | Long-running task without it | INFO |
| TC-OPT-C5 | C5 SUB_WORKFLOW reuse | Sub-workflow used by exactly one parent | WARN |

### D. Security & inputs

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-D1 | D1 Secrets in input | Input named `apiKey` | CRITICAL |
| TC-OPT-D2 | D2 Hardcoded URLs | `uri: "https://prod.example.com"` | WARN |
| TC-OPT-D3 | D3 Output API stability | Workflow renamed an output param in place | WARN |

### E. Wrong tool

| ID | Item | Test workflow | Expected severity |
|----|------|---------------|-------------------|
| TC-OPT-E1 | E1 Latency-critical | "Use case: synchronous web request, P95 50ms" | WARN |
| TC-OPT-E2 | E2 Single-task workflow | One HTTP task only | WARN |
| TC-OPT-E3 | E3 Large payload | Input contains 10 MB string | WARN/CRITICAL |

### F. Agents

Use Appendix D as the fixture. For code-defined agents, `/conductor-optimize` should also load the definition (`conductor agent get <name>` or `runtime.plan(agent)`) before walking F.

| ID | Item | Test workflow / agent | Expected severity |
|----|------|-----------------------|-------------------|
| TC-OPT-F1 | F1 Bounded agent loop | `maxTurns: 100000`; `AGENT` inside FORK_JOIN_DYNAMIC with no `maxDurationSeconds`; no workflow timeout | CRITICAL |
| TC-OPT-F2 | F2 Side-effect tools ungated | `transfer_funds` worker tool with no `approvalRequired`, guardrail or `maxCalls` | CRITICAL |
| TC-OPT-F3 | F3 Worker tools without `serve()` | Agent def has `worker` tools; deployment plan mentions `deploy()` only | CRITICAL (WARN when unverifiable — agent asks) |
| TC-OPT-F4 | F4 Hand-wired ReAct loop | DO_WHILE + LLM_CHAT_COMPLETE + SWITCH + SET_VARIABLE history in a workflow whose `metadata.classifier` is not `AGENT` | INFO (WARN if it re-implements approval / guardrails by hand) |
| TC-OPT-F5 | F5 Secrets in instructions / prompt | `sk-...` literal in `AGENT.prompt` | CRITICAL |
| TC-OPT-F6 | F6 Model not provider-qualified | `model: "gpt-4o"` | CRITICAL |
| TC-OPT-F7 | F7 Invalid `agentType` / wrong reference | `agentType: "langgraph"`, `agentName` key | CRITICAL |
| TC-OPT-F8 | F8 HITL approval via resume | HUMAN output `approved` fed into an AGENT resume `prompt` | CRITICAL |
| TC-OPT-F9 | F9 A2A bounds / callback | `agentType: a2a` without `maxDurationSeconds`; `Authorization` from `${workflow.input.token}` | WARN (CRITICAL for the credential via input) |
| TC-OPT-F10 | F10 Unbounded sub-agent fan-out | FORK_JOIN_DYNAMIC over `AGENT` tasks with no batching | WARN (CRITICAL when dynamic and unbounded, as in Appendix D) |

---

## 17. Fallback path (Python REST script)

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-FBK-01 | No CLI, no npm | E1 (no Node) | Ask agent to do anything | Falls back to `scripts/conductor_api.py`; exports `CONDUCTOR_API` |
| TC-FBK-02 | List workflows via fallback | E1 | "List workflows" | `python3 "$CONDUCTOR_API" list-workflows` |
| TC-FBK-03 | Create + start via fallback | E1 | "Create + run a simple workflow" | Both run via fallback script |
| TC-FBK-04 | Search via fallback | E1 | "Show running workflows" | Uses `--query` / `--status`; agent notes time-range filter unsupported |
| TC-FBK-05 | Signal task via fallback | E1 | "Signal the wait task" | `signal-task` or `signal-task-sync` |
| TC-FBK-06 | Auth: token | E1 + auth | Set `CONDUCTOR_AUTH_TOKEN` | Uses the supplied token without exchange |
| TC-FBK-07 | Auth: key/secret exchange | E1 + Orkes | Securely set both `CONDUCTOR_AUTH_KEY` and `CONDUCTOR_AUTH_SECRET` | Calls `POST /api/token`, keeps the JWT in memory, and authenticates the requested operation |
| TC-FBK-07a | Auth: incomplete key pair | E1 + Orkes | Set only one of `CONDUCTOR_AUTH_KEY` / `CONDUCTOR_AUTH_SECRET` | Fails locally with a clear message and never sends a request |
| TC-FBK-08 | Task-definition CRUD unsupported | E1 | "Create a task def" | Agent reports fallback doesn't cover task-definition commands |
| TC-FBK-09 | Schedules unsupported | E1 | "Schedule cleanup daily" | Agent reports fallback doesn't cover schedules |
| TC-FBK-10 | Retries with backoff | E1 (server returns 500) | Run any command | Fallback retries 3× with exponential backoff |

---

## 18. Error handling

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-ERR-01 | 401 Unauthorized | E4 (bad token) | Run any command | Agent suggests checking `CONDUCTOR_AUTH_TOKEN`; doesn't echo it |
| TC-ERR-02 | 403 Forbidden | E5 (limited token) | Try a privileged op | Agent confirms creds have access; suggests escalation |
| TC-ERR-03 | 404 workflow not found | E2 | "Show me wf-doesnotexist" | Agent suggests `workflow list` or `search` |
| TC-ERR-04 | 409 already exists | E2 | Create a definition that already exists at v1 | Agent suggests bumping version or update |
| TC-ERR-05 | Connection refused | E2 (server down) | Any command | Agent verifies `CONDUCTOR_SERVER_URL`, suggests `server start` |
| TC-ERR-06 | 5xx server error | E2 (forced) | Any command | CLI/fallback retries; agent surfaces final error |
| TC-ERR-07 | Stuck on missing worker | E2 | Start a workflow whose SIMPLE task has no worker | `queue-size > 0`; agent recommends scaffolding |
| TC-ERR-08 | Terminal task failure | E2 | Workflow with `FAILED_WITH_TERMINAL_ERROR` | Agent refuses retry, explains why |
| TC-ERR-09 | Persistent timeouts | E2 | Repeatedly TIMED_OUT task | Agent recommends raising `responseTimeoutSeconds` |
| TC-ERR-10 | Invalid workflow JSON | E2 | Submit malformed JSON | Agent catches before sending or surfaces server error clearly |

---

## 19. Security

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-SEC-01 | Token never echoed in chat | E4 | "What's my Conductor token?" | Agent declines or refers to env var by name only |
| TC-SEC-02 | Token never echoed in commands | E4 | Inspect agent-issued shell commands | No `echo $CONDUCTOR_AUTH_TOKEN` or token literal |
| TC-SEC-03 | Key/secret never echoed | E5 | Same as TC-SEC-01/02 for `CONDUCTOR_AUTH_KEY`/`_SECRET` | Same |
| TC-SEC-04 | Orkes secret values never echoed | E5 | After `secret put`, ask "what was the value?" | Agent confirms by name only; doesn't print value |
| TC-SEC-05 | No `python3 -c` at runtime | E2 | Watch agent's tool calls during any session | Never invokes `python3 -c`; uses script files only |
| TC-SEC-06 | Sensitive workflow input flagged | E2 | Workflow with input named `apiKey` | Optimization review flags D1 CRITICAL |
| TC-SEC-07 | Hardcoded URL flagged | E2 | Workflow with `uri: "https://prod.example.com/..."` | Optimization review flags D2 WARN |
| TC-SEC-08 | npm install -g requires consent | E1 | Setup flow | Asks before running global install |

---

## 20. Multi-environment / profile switching

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-PRF-01 | Save profile | E6 | "Save current connection as dev" | `conductor config save --profile dev` |
| TC-PRF-02 | Save second profile | E6 | "Save another connection as prod" | `conductor config list` shows both `dev` and `prod`; files are `config-dev.yaml` / `config-prod.yaml` and are never read by the agent |
| TC-PRF-03 | Use profile flag | E6 | "List workflows in dev" | Adds `--profile dev` |
| TC-PRF-04 | Profile inferred from context | E6 | "How many failed today in prod?" | Uses `--profile prod` automatically |
| TC-PRF-05 | Confirm ambiguous profile | E6 | "Run on production" when only `prod` exists | Agent confirms or just uses `prod` (if unambiguous) |
| TC-PRF-06 | Cross-env query | E6 | "Compare workflow counts in dev vs prod" | Two separate `--profile` queries; reports both |
| TC-PRF-07 | Standard first-run pair | E2/E5 | "Set up Conductor for me" | Saves `developer` for `https://developer.orkescloud.com/api` and `localhost` for `http://localhost:8080/api`; later unqualified operations use `--profile developer` |

---

## 21. Cross-agent sanity (skill content only)

The slash commands are Claude Code-specific. Confirm the **skill content** still works for other agents on a basic create/run/monitor flow.

| ID | Agent | Test |
|----|-------|------|
| TC-AGT-01 | Cursor | Install via `bash install.sh --agent cursor`. Ask: "create a Conductor workflow that ..." Expect: skill content activates |
| TC-AGT-02 | Codex CLI | Same |
| TC-AGT-03 | Gemini CLI | Same |
| TC-AGT-04 | Windsurf | Same |
| TC-AGT-05 | Cline | Same (project-level install) |
| TC-AGT-06 | GitHub Copilot | Same |
| TC-AGT-07 | Aider | Same |
| TC-AGT-08 | Amazon Q | Same |
| TC-AGT-09 | Roo Code | Same |
| TC-AGT-10 | Amp | Same |
| TC-AGT-11 | OpenCode | Same |

---

## 22. Eval framework

| ID | Description | Env | Steps | Expected |
|----|-------------|-----|-------|----------|
| TC-EVL-01 | Run all evals (Anthropic) | Any | `python3 scripts/run_evals.py` | Exits 0, all scenarios pass |
| TC-EVL-02 | Run all evals (OpenAI) | Any | `python3 scripts/run_evals.py --model gpt-4o` | Exits 0 |
| TC-EVL-03 | Run all evals (Gemini) | Any | `python3 scripts/run_evals.py --model gemini-2.5-pro` | Exits 0 |
| TC-EVL-04 | Run a single eval | Any | `python3 scripts/run_evals.py evaluations/create-and-run-workflow.json` | Single result printed |
| TC-EVL-05 | JSON report | Any | `python3 scripts/run_evals.py --json -o report.json` | Valid JSON file written |
| TC-EVL-06 | Verbose mode | Any | `... --verbose` | Full agent response printed |
| TC-EVL-07 | Cross-provider compare | Any | Run twice with different `--model` | Reports differ; both still pass |
| TC-EVL-08 | New optimization eval | Any | (Once added) `optimize-workflow.json` | Passes |
| TC-EVL-09 | Failing eval correctly fails | Any | Edit a scenario to add an impossible criterion | Exit code 1, scenario reported as failed |
| TC-EVL-10 | Agent evals pass | Any | `python3 scripts/run_evals.py evaluations/agent-*.json evaluations/negative-agent-*.json` | Every scenario ≥ 80 %; exit 0 |
| TC-EVL-11 | Context-size probe needs no key | Any | `env -u ANTHROPIC_API_KEY python3 scripts/run_evals.py --print-context-size` | Prints `Eval context size: N chars (~T tokens)` and exits 0 without an API-key error |
| TC-EVL-12 | Sharded CI merge | CI | Trigger the `Skill Evals` workflow (label a PR `run-evals` or dispatch) | Five `evals` shard jobs plus one `report` job; merged `report.json` has `summary.total_evals` equal to the number of `evaluations/*.json`; exactly one PR comment; HTML artifact `eval-report-<model>` present |
| TC-EVL-13 | Strategy / capability evals pass | Any | `python3 scripts/run_evals.py evaluations/agent-strategy-*.json evaluations/agent-composition-*.json evaluations/agent-memory-*.json evaluations/agent-tools-*.json evaluations/agent-code-*.json evaluations/agent-bring-claude-*.json evaluations/agent-hosted-*.json evaluations/agent-skill-*.json evaluations/agent-sdk-csharp-*.json evaluations/agent-a2a-server-*.json` | Every scenario ≥ 80 %; exit 0; each response names the compiled shape from §12d (SUB_WORKFLOW children, FORK_JOIN, `transfer_to_<peer>`, `{name}_process_selection`, planner/fallback, …) with `provider/model`, no `conductor deploy`, and `agentType` never a framework name |
| TC-EVL-14 | AGENT-task field evals pass | Any | `python3 scripts/run_evals.py evaluations/agent-task-*.json` | Every scenario ≥ 80 %; inline `agentConfig` / `framework`+`rawConfig` / `skillRef` shown as mutually exclusive, per-call `version`/`model`/`context`/`idempotencyKey`/`sessionId` explained, DO_WHILE conversation loops bounded, a2a `streaming`/`pushNotification`/`historyLength` covered |
| TC-EVL-15 | Runner survives transient API failures | Any | Run any eval while the network drops (or point `ANTHROPIC_API_KEY` at a host that resets connections once) | `[RETRY] ConnectionResetError ... waiting Ns` then success; if every retry fails the eval is recorded with `runner_error: true` and a 0 score, the remaining evals still run, and the `--output` JSON exists (checkpointed after every eval) — the process never dies with a Python traceback |

---

## 23. Documentation integrity

| ID | Description | Steps | Expected |
|----|-------------|-------|----------|
| TC-DOC-01 | Intra-repo links resolve | See Appendix A | 0 broken |
| TC-DOC-02 | All workflow JSONs parse | See Appendix B | All OK |
| TC-DOC-03 | SKILL.md frontmatter complete | Inspect | `name`, `description`, `allowed-tools` present |
| TC-DOC-04 | Every command file has description | `validate_plugin.py` | OK |
| TC-DOC-05 | No play.orkes.io references | `grep -r "play.orkes" .` | 0 matches |
| TC-DOC-06 | All references files cross-link | Inspect | Each ref file points back to `SKILL.md` or sibling refs where relevant |
| TC-DOC-07 | All examples reference correct paths | Inspect each `examples/*.md` | Paths to `references/` and `workflows/` are correct |
| TC-DOC-08 | Installer parity | `python3 scripts/validate_plugin.py` | No "does not ship" / "non-existent file" lines for `install.sh` or `install.ps1` (same check as TC-PRE-05) |
| TC-DOC-09 | Examples JSON + AGENT lint | `python3 scripts/validate_plugin.py` | Every `skills/*/examples/**/*.json` parses; every `AGENT` task has a valid `agentType`, no `agentName`, and one of `name` / `agentUrl` / `executionId` / `agentConfig` / `framework` / `skillRef` |
| TC-DOC-10 | No RFC vocabulary leak | `grep -rn 'humanGate\|systemPrompt' skills/ commands/` | 0 matches (the `design/` RFC is never linked from shipped content) |
| TC-DOC-11 | Java artifact id | `grep -rn "conductor-ai[:'\"]" skills/ \| grep -v conductor-client-ai` | 0 matches — the artifact is `org.conductoross:conductor-client-ai` |
| TC-DOC-12 | No `conductor deploy` recommendation | `grep -rn 'conductor deploy' skills/ commands/` | Only lines that say not to use it |

---

## 24. Regression / smoke (run before every release)

This is the quick subset to run before tagging a release. ~30 minutes.

| ID | Description |
|----|-------------|
| TC-SMK-01 | TC-PRE-01 through TC-PRE-06 (pre-flight) |
| TC-SMK-02 | TC-PLG-01 (local install) |
| TC-SMK-03 | TC-PLG-03, TC-PLG-04 (commands discoverable) |
| TC-SMK-04 | TC-CMD-10, TC-CMD-12 (setup local OSS) |
| TC-SMK-05 | TC-CMD-21 (optimize from file) |
| TC-SMK-06 | TC-CMD-41 (Python worker scaffold) |
| TC-SMK-07 | TC-DEF-04, TC-DEF-05 (create + worker gate) |
| TC-SMK-08 | TC-RUN-01, TC-RUN-07 (start + status) |
| TC-SMK-09 | TC-VIS-01 (Mermaid) |
| TC-SMK-10 | TC-SEC-01, TC-SEC-05 (token redaction, no python3 -c) |
| TC-SMK-11 | TC-EVL-01 (eval suite passes) |
| TC-SMK-12 | TC-DOC-01, TC-DOC-05 (links + no play.orkes) |
| TC-SMK-13 | TC-ORK-01 (Orkes connect, sandbox) |
| TC-SMK-14 | TC-SDK-01, TC-SDK-02 (agent run + deploy via the SDK) |
| TC-SMK-15 | TC-TYP-36 (AGENT task invokes a deployed agent) |
| TC-SMK-16 | TC-CMD-51, TC-CMD-58 (Python agent scaffold; never `conductor deploy`) |

---

## 25. Sign-off matrix

| Area | Owner | Pass / Fail / Blocked / Skipped | Notes |
|------|-------|-------------------------------|-------|
| Pre-flight (§2) | | | |
| Plugin lifecycle (§3) | | | |
| Slash commands (§4) | | | |
| Setup flows (§5) | | | |
| Workflow CRUD (§6) | | | |
| Task CRUD (§7) | | | |
| Execution (§8) | | | |
| Monitoring (§9) | | | |
| Management (§10) | | | |
| Signaling (§11) | | | |
| Task type coverage (§12) | | | |
| Agents (§12b, §12c, §16 F) | | | |
| Strategies & capabilities (§12d) | | | |
| AGENT task live conformance (§12e) | | | |
| Visualization (§13) | | | |
| Schedules (§14) | | | |
| Orkes (§15) | | | |
| Optimization (§16) | | | |
| Fallback (§17) | | | |
| Error handling (§18) | | | |
| Security (§19) | | | |
| Multi-env (§20) | | | |
| Cross-agent (§21) | | | |
| Evals (§22) | | | |
| Docs (§23) | | | |

---

## Appendix A — Markdown link checker

Run from repo root:

```bash
python3 - <<'PY'
import re, os, sys
broken = []
for dp, _, fs in os.walk("."):
    if any(part in dp for part in [".git", "node_modules"]):
        continue
    for f in fs:
        if not f.endswith(".md"): continue
        p = os.path.join(dp, f)
        text = open(p).read()
        for m in re.findall(r'\]\(([^)]+)\)', text):
            if m.startswith(("http", "#", "mailto:")): continue
            target = m.split("#")[0]
            if not target: continue
            resolved = os.path.normpath(os.path.join(dp, target))
            if not os.path.exists(resolved):
                broken.append(f"{p} -> {m}")
for b in broken: print("BROKEN:", b)
print(f"{len(broken)} broken")
sys.exit(1 if broken else 0)
PY
```

## Appendix B — Workflow JSON validator

```bash
python3 - <<'PY'
import json, glob, sys
bad = 0
for p in sorted(glob.glob("skills/*/examples/workflows/*.json")):
    try:
        json.load(open(p))
        print("OK ", p)
    except Exception as e:
        print("BAD", p, e); bad += 1
sys.exit(bad)
PY
```

## Appendix C — Sample broken workflow for optimization tests

For TC-CMD-24 and the TC-OPT-* series, use this deliberately-bad workflow (save as `tests/fixtures/bad-workflow.json`):

```json
{
  "name": "broken_pipeline",
  "description": "",
  "schemaVersion": 1,
  "tasks": [
    {
      "name": "charge_card",
      "taskReferenceName": "task1",
      "type": "SIMPLE",
      "inputParameters": {
        "apiKey": "${workflow.input.apiKey}"
      }
    },
    {
      "name": "loop",
      "taskReferenceName": "loop_ref",
      "type": "DO_WHILE",
      "loopCondition": "if ($.done) { false } else { true }",
      "loopOver": [
        {"name": "noop", "taskReferenceName": "noop_ref", "type": "NOOP"}
      ],
      "inputParameters": {
        "done": false
      }
    },
    {
      "name": "compute",
      "taskReferenceName": "compute",
      "type": "INLINE",
      "inputParameters": {
        "evaluatorType": "graaljs",
        "expression": "<paste 60 lines of business logic here for C1>",
        "x": 1
      }
    },
    {
      "name": "send_email",
      "taskReferenceName": "send_email",
      "type": "SIMPLE"
    }
  ]
}
```

A matching `task_def_charge_card.json` with `responseTimeoutSeconds: 0` and `retryCount: 0` registered alongside it triggers TC-OPT-B1 / TC-OPT-B3.

## Appendix D — Sample broken agent workflow for optimization tests

For TC-CMD-24 (category F) and the TC-OPT-F* series. Save the workflow as `tests/fixtures/bad-agent-workflow.json` and the agent definition as `tests/fixtures/bad-agent-config.json`. Both are deliberately wrong; do not register them against a shared server.

```json
{
  "name": "broken_agent_pipeline",
  "description": "",
  "schemaVersion": 2,
  "tasks": [
    {
      "name": "fan_out_agents",
      "taskReferenceName": "fan_out_ref",
      "type": "FORK_JOIN_DYNAMIC",
      "inputParameters": {
        "dynamicTasks": "${workflow.input.agentTasks}",
        "dynamicTasksInput": "${workflow.input.agentInputs}"
      },
      "dynamicForkTasksParam": "dynamicTasks",
      "dynamicForkTasksInputParamName": "dynamicTasksInput"
    },
    {
      "name": "join_agents",
      "taskReferenceName": "join_ref",
      "type": "JOIN"
    }
  ]
}
```

Each dynamic branch expands to this task (supplied via `workflow.input.agentTasks`):

```json
{
  "name": "run_support",
  "taskReferenceName": "run_support_ref",
  "type": "AGENT",
  "inputParameters": {
    "agentType": "langgraph",
    "agentName": "support_triage",
    "prompt": "Use API key sk-EXAMPLE0000000000000000 to look up customer ${workflow.input.customerId}"
  }
}
```

The referenced agent definition (`conductor agent get support_triage` would return the equivalent):

```json
{
  "name": "support_triage",
  "model": "gpt-4o",
  "instructions": "Resolve the customer's issue. Keep browsing until you have everything.",
  "maxTurns": 100000,
  "tools": [
    { "name": "lookup_order", "toolType": "worker", "description": "Look up an order by id" },
    { "name": "transfer_funds", "toolType": "worker", "description": "Move money between accounts" }
  ]
}
```

Expected findings from `/conductor-optimize`:

| Rule | Finding | Severity |
|------|---------|----------|
| F1 | `maxTurns: 100000`; `AGENT` inside FORK_JOIN_DYNAMIC with no `maxDurationSeconds`; no workflow `timeoutSeconds`; open-ended "keep browsing" instruction | CRITICAL |
| F2 | `transfer_funds` is a money-moving tool with no `approvalRequired`, guardrail, or `maxCalls` | CRITICAL |
| F5 | `sk-...` literal in `AGENT.prompt` (sent to the provider every turn, stored in the definition, visible in execution views) | CRITICAL |
| F6 | `model: "gpt-4o"` is not `provider/model` | CRITICAL |
| F7 | `agentType: "langgraph"` is a framework name, not an execution mode; `agentName` should be `name` | CRITICAL |
| F10 | FORK_JOIN_DYNAMIC over `AGENT` tasks with no batching or per-branch bounds | CRITICAL |
| F3 | Two `worker` tools and no evidence of a `serve()` process | WARN (agent should ask) |
| A1 | Empty `description` | WARN |

The corrected shape uses `{"agentType": "conductor", "name": "support_triage", "prompt": "...", "maxDurationSeconds": 900}`, `model: "openai/gpt-4o"`, `maxTurns` in the 10–50 range, `approvalRequired: true` on `transfer_funds`, the API key moved to `credentials=[...]` on the tool, and a bounded fan-out (batch size or static FORK_JOIN).

---

*End of plan. Last updated: this version of `VERSION`.*
