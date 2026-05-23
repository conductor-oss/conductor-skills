<p align="center">
  <img src="assets/conductor.png" alt="Conductor" width="120">
</p>

<h1 align="center">Conductor Skills</h1>

<p align="center">
  Teach your AI coding agent to create, run, monitor, and manage
  <a href="https://github.com/conductor-oss/conductor">Conductor</a> workflow orchestrations.
</p>

<p align="center">
  <a href="https://github.com/conductor-oss/conductor">
    <img src="https://img.shields.io/github/stars/conductor-oss/conductor?style=social" alt="Star Conductor">
  </a>
  &nbsp;&middot;&nbsp;
  <a href="https://join.slack.com/t/orkes-conductor/shared_invite/zt-3dpcskdyd-W895bJDm8psAV7viYG3jFA">
    <img src="https://img.shields.io/badge/Slack-Join%20Community-4A154B?logo=slack" alt="Join Slack">
  </a>
  &nbsp;&middot;&nbsp;
  <a href="https://github.com/conductor-oss/conductor-skills/blob/main/LICENSE.txt">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License">
  </a>
</p>

---

## What You Get

Once installed, your AI agent can:

- **Create** workflow definitions with any task type (HTTP, SWITCH, FORK, WAIT, AI/LLM, MCP, etc.)
- **Run** workflows synchronously or asynchronously
- **Monitor** executions and search by status, time, or correlation ID
- **Manage** workflows — pause, resume, terminate, retry, restart, rerun, skip-task, jump
- **Signal** WAIT and HUMAN tasks for human-in-the-loop patterns
- **Schedule** workflows on cron — schedules are part of OSS
- **Write workers** in Python, JavaScript, Java, Go, C#, Ruby, or Rust
- **Visualize** workflows as Mermaid diagrams
- **Review & optimize** existing workflows against a checklist of 19 reliability / performance / security / structure rules
- **Manage** secrets and webhooks (Orkes)

On Claude Code, four slash commands give you direct entry points:

| Command | Purpose |
|---------|---------|
| `/conductor` | Menu — lists subcommands and natural-language examples |
| `/conductor-setup` | First-time setup (CLI, server, auth) |
| `/conductor-optimize` | Review a workflow against the optimization checklist |
| `/conductor-scaffold-worker` | Generate a worker stub in your language |

Everything else (run, status, schedule, retry, signal, visualize, create) works through plain English — no command needed.

---

## Quick Install

### Claude Code Plugin (recommended for Claude users)

Install as a Claude Code plugin from the marketplace:

```shell
/plugin marketplace add conductor-oss/conductor-skills
/plugin install conductor@conductor-skills
```

Or test against a local checkout during development:

```shell
/plugin marketplace add /path/to/conductor-skills
/plugin install conductor@conductor-skills
```

### Install via npm

If you have Node.js, you can install through npm — useful in CI and dev containers:

```bash
# One-off, no global install
npx @conductor-oss/conductor-skills --agent claude
npx @conductor-oss/conductor-skills --all

# Or globally
npm install -g @conductor-oss/conductor-skills
conductor-skills --agent cursor
conductor-skills --all --upgrade
conductor-skills --agent cline --uninstall
```

The npm package bundles all skill content, so it works offline once installed.

### Install for all detected agents

One command to auto-detect every supported agent on your system and install globally where possible. Re-run anytime — it only installs for newly detected agents.

**macOS / Linux**
```bash
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --all
```

**Windows (PowerShell)**
```powershell
irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -All
```

**Windows (cmd)**
```cmd
powershell -c "irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -All"
```

### Install for a specific agent

These agents don't support global install — run the command from your project directory.

**macOS / Linux**

| Agent | Command |
|-------|---------|
| [Cline](https://github.com/cline/cline) | `curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh \| bash -s -- --agent cline` |
| [GitHub Copilot](https://github.com/features/copilot) | `curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh \| bash -s -- --agent copilot` |
| [Amazon Q](https://aws.amazon.com/q/developer/) | `curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh \| bash -s -- --agent amazonq` |

**Windows (PowerShell)**

| Agent | Command |
|-------|---------|
| [Cline](https://github.com/cline/cline) | `irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent cline` |
| [GitHub Copilot](https://github.com/features/copilot) | `irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent copilot` |
| [Amazon Q](https://aws.amazon.com/q/developer/) | `irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent amazonq` |

**Windows (cmd)**

| Agent | Command |
|-------|---------|
| [Cline](https://github.com/cline/cline) | `powershell -c "irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent cline"` |
| [GitHub Copilot](https://github.com/features/copilot) | `powershell -c "irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent copilot"` |
| [Amazon Q](https://aws.amazon.com/q/developer/) | `powershell -c "irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent amazonq"` |

> All other agents are installed globally via the [install all](#install-for-all-detected-agents) command above. You can also use `--agent <name>` for any agent to do a project-level install.

That's it — ask your agent to connect to your server (see [Try It](#try-it) below).

---


## Try It

After installing, try these prompts with your agent. Or run the slash command shown in brackets where one exists.

**Setup & configure** *(or `/conductor-setup`)*
- *"Set up Conductor — I want to start a local server"*
- *"Connect to my Conductor server at https://developer.orkescloud.com/api"*
- *"Save my Conductor server config as a profile called production"*
- *"Switch to my staging Conductor profile"*
- *"How many workflows in dev vs prod?"*

**Create & run**
- *"Create a workflow that calls the GitHub API to get open issues and sends a Slack notification"*
- *"Create a FORK_JOIN workflow that fetches inventory and pricing in parallel"*
- *"Run the my-workflow workflow with input {\"userId\": 123}"*
- *"Run order-processing synchronously and wait until the approval step"*
- *"Run cleanup-workflow with correlation id daily-2026-05-11"*

**Monitor & diagnose**
- *"Show me all failed workflow executions from the last hour"*
- *"What's the status of execution abc-123?"*
- *"Why did wf-789 fail?"*
- *"Show me the running executions of order-processing"*

**Manage**
- *"Retry all failed executions of my-workflow from today"*
- *"Pause the running execution xyz-456"*
- *"Terminate wf-123, customer cancelled"*
- *"Restart wf-456 on the latest workflow version"*
- *"Skip the email step in wf-789"*
- *"Jump wf-789 to fulfill_order"*

**Human-in-the-loop**
- *"Signal the wait task in execution abc-123 with approval: true"*
- *"Reject the wait task in wf-456 — don't retry"*
- *"What's blocking wf-789?"*

**Schedule** *(part of OSS)*
- *"Schedule cleanup-workflow to run daily at 2am"*
- *"Schedule order-report every Monday at 9:30 weekdays only"*
- *"Pause the cleanup schedule"*
- *"Show the last 50 scheduled cleanup runs"*

**Modify**
- *"Add an error-handling branch to the order-processing workflow"*
- *"Add a WAIT task before the payment step in my checkout workflow"*
- *"Convert the inline JS in compute_pricing to a worker"*
- *"Extract the fulfillment chunk into a sub-workflow"*

**Review & optimize** *(or `/conductor-optimize`)*
- *"Review the order-processing workflow"*
- *"Optimize this workflow JSON — what should I fix?"* *(attach a file)*
- *"Audit weather-notification for missing timeouts and retries"*
- *"Make this workflow simpler"*
- *"Are there any secrets being passed through workflow input that shouldn't be?"*

**Workers** *(or `/conductor-scaffold-worker`)*
- *"Write a Python worker that processes image thumbnails"*
- *"Write a TypeScript worker that validates email addresses"*
- *"Generate a Go worker that fetches data from a REST API and transforms the response"*
- *"Scaffold a Java worker for the charge_card task"*

**AI / LLM workflows**
- *"Create a workflow that summarizes text with Claude"*
- *"Build me an AI agent that lists MCP tools, picks one, and calls it"* — the canonical first-agent flow ([example](skills/conductor/examples/ai-agent-mcp.md))
- *"Create a RAG workflow that searches my Pinecone index and answers questions with sources"* ([example](skills/conductor/examples/llm-rag.md))
- *"Build an autonomous agent loop that runs up to 10 think/act/observe iterations"* ([example](skills/conductor/examples/ai-agent-loop.md))
- *"Add a HUMAN approval step before the agent calls any tool"*
- *"Create a workflow that classifies support tickets with GPT-4o-mini and routes to the right queue"*
- *"Index this document into the knowledge base"* — using `LLM_INDEX_TEXT`
- *"Generate an image from a prompt with DALL-E"* — using `GENERATE_IMAGE`

**Visualize**
- *"Show me a diagram of the order-processing workflow"*
- *"Render the FORK_JOIN flow as a Mermaid chart"*

**Orkes only** — secrets, webhooks (Orkes Conductor required)
- *"Save STRIPE_KEY as a secret"*
- *"Create a GitHub webhook that triggers github_pr_handler"*
- *"List my webhooks"*

---

## Examples

Operational:

| Example | Description |
|---------|-------------|
| [Create and Run a Workflow](skills/conductor/examples/create-and-run-workflow.md) | Define a workflow, register it, and execute it end-to-end |
| [Monitor and Retry](skills/conductor/examples/monitor-and-retry.md) | Search executions, diagnose failures, and batch-retry |
| [Signal a Wait Task](skills/conductor/examples/signal-wait-task.md) | Human-in-the-loop with WAIT tasks and external signals |
| [Review and Optimize](skills/conductor/examples/review-workflow.md) | Apply the optimization checklist to an existing workflow |

Design patterns:

| Example | Description |
|---------|-------------|
| [FORK_JOIN Parallel Branches](skills/conductor/examples/fork-join.md) | Run independent tasks in parallel and converge with JOIN |
| [DO_WHILE Loop](skills/conductor/examples/do-while-loop.md) | Iteration counter via the self-reference pattern |
| [SUB_WORKFLOW Composition](skills/conductor/examples/sub-workflow.md) | Compose reusable child workflows under a parent |

AI / LLM patterns:

| Example | Description |
|---------|-------------|
| [Minimum LLM Workflow](skills/conductor/examples/llm-chat.md) | Single `LLM_CHAT_COMPLETE` — building block |
| [AI Agent with MCP Tools](skills/conductor/examples/ai-agent-mcp.md) | List tools → plan → call → summarize (the canonical first-AI-agent tutorial) |
| [Autonomous Agent Loop](skills/conductor/examples/ai-agent-loop.md) | ReAct-pattern `DO_WHILE` loop until the LLM decides it's done |
| [RAG — Retrieval Augmented Generation](skills/conductor/examples/llm-rag.md) | Vector search + grounded LLM answer with sources |

Raw JSON workflow definitions live in [skills/conductor/examples/workflows/](skills/conductor/examples/workflows/) — pass any directly to `conductor workflow create`.

## References

| Reference | Description |
|-----------|-------------|
| [Setup](skills/conductor/references/setup.md) | Install the CLI, choose a server, configure auth, named profiles |
| [CLI Index](skills/conductor/references/cli-index.md) | Verb → CLI command lookup, grouped by lifecycle / intervention / tasks |
| [Workflow Definition Schema](skills/conductor/references/workflow-definition.md) | Full JSON schema, every task type, expression syntax |
| [GraalJS Gotchas](skills/conductor/references/graaljs-gotchas.md) | JS-evaluated task pitfalls — Java-Map proxies, `$.varName` rule, scope rules, IIFE convention for DO_WHILE |
| [Template Resolution](skills/conductor/references/template-resolution.md) | `${...}` resolution pitfalls — missing-field-returns-parent, object → string `toString`, iteration paths |
| [Writing Workers](skills/conductor/references/workers.md) | SDK examples in Python, JavaScript, Java, Go, C#, Ruby, Rust |
| [API Reference](skills/conductor/references/api-reference.md) | REST endpoints for direct API access |
| [Visualization](skills/conductor/references/visualization.md) | Mermaid mappings for every Conductor construct + UI link |
| [Schedules](skills/conductor/references/schedules.md) | Cron schedules (OSS) — schema, format, idempotency patterns |
| [Optimization Checklist](skills/conductor/references/optimization.md) | 22 review rules across structure, reliability (incl. LLM-specific gotchas), performance, security |
| [Troubleshooting](skills/conductor/references/troubleshooting.md) | Common errors, diagnosis flow, stuck-workflow recovery |
| [Orkes Enterprise](skills/conductor/references/orkes.md) | Secrets, webhooks (Orkes Conductor only) |
| [Fallback CLI](skills/conductor/references/fallback-cli.md) | Python REST script equivalents when the CLI isn't available |

## Evaluations

The `evaluations/` directory contains automated test scenarios to validate the skill works correctly with your agent. See [evaluations/README.md](evaluations/README.md) for details.

```bash
python3 scripts/run_evals.py --verbose
```

---

## Upgrade

Check for a newer version and upgrade all installed agents:

**macOS / Linux**
```bash
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --all --upgrade
```

**Windows**
```powershell
irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -All -Upgrade
```

Or upgrade a single agent: `--agent <name> --upgrade`

---

## Supported Agents

| Agent | Flag | Global install | Project install |
|-------|------|---------------|-----------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `claude` | Plugin (via `/plugin marketplace add` + `/plugin install`) — also adds `/conductor*` slash commands | — |
| [Codex CLI](https://github.com/openai/codex) | `codex` | `~/.codex/AGENTS.md` | `AGENTS.md` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `gemini` | `~/.gemini/GEMINI.md` | `GEMINI.md` |
| [Cursor](https://cursor.com) | `cursor` | `~/.cursor/skills/conductor/SKILL.md` | `.cursor/rules/conductor.mdc` |
| [Windsurf](https://codeium.com/windsurf) | `windsurf` | `~/.codeium/windsurf/memories/global_rules.md` | `.windsurfrules` |
| [Cline](https://github.com/cline/cline) | `cline` | — | `.clinerules` |
| [GitHub Copilot](https://github.com/features/copilot) | `copilot` | — | `.github/copilot-instructions.md` |
| [Aider](https://aider.chat) | `aider` | `~/.conductor-skills/` + `~/.aider.conf.yml` | `.conductor-skills/` + `.aider.conf.yml` |
| [Amazon Q](https://aws.amazon.com/q/developer/) | `amazonq` | — | `.amazonq/rules/conductor.md` |
| [Roo Code](https://github.com/RooVetGit/Roo-Code) | `roo` | `~/.roo/rules/conductor.md` | `.roo/rules/conductor.md` |
| [Amp](https://ampcode.com) | `amp` | `~/.config/AGENTS.md` | `.amp/instructions.md` |
| [OpenCode](https://opencode.ai) | `opencode` | `~/.config/opencode/skills/conductor/SKILL.md` | `AGENTS.md` |

---
## Uninstall

**macOS / Linux**
```bash
# Remove a global install
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --agent <name> --global --uninstall

# Remove a project-level install
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --agent <name> --uninstall
```

**Windows (PowerShell)**
```powershell
# Remove a global install
irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent <name> -Global -Uninstall

# Remove a project-level install
irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent <name> -Uninstall
```

**Windows (cmd)**
```cmd
powershell -c "irm https://conductor-oss.github.io/conductor-skills/install.ps1 -OutFile install.ps1; .\install.ps1 -Agent <name> -Global -Uninstall"
```

---

## License

Apache 2.0 — see [LICENSE.txt](LICENSE.txt).

Built for [Conductor OSS](https://github.com/conductor-oss/conductor). Enterprise features powered by [Orkes](https://orkes.io).
