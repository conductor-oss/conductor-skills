# Changelog

All notable changes to the Conductor Skills plugin are documented here. Versions
correspond to the shared `VERSION` file (see [PUBLISHING.md](PUBLISHING.md) for
what that means across the three distribution channels).

## Unreleased

### Added

- `orkes login` (OAuth device flow to Orkes Conductor Developer Edition) is the
  default first-run path: no keys to paste, signup is implicit, the CLI writes
  and activates the `developer` profile plus the `conductor --profile developer`
  shim. The skill then runs a sub-30-second hello world before the user's real
  goal and starts that goal from the closest starter. Commands run as
  `orkes conductor …` when `orkes` is on PATH.
- `references/orkes-dev-edition.md` — the Developer Edition journey (web →
  terminal handoff, login, hello world, starters, worker credentials via
  `orkes conductor keys create --name <app> --save`, upgrade paths incl. a
  Foundry placeholder) and an `orkes` CLI cheat-sheet.
- `references/orkes-use-cases.md` — verified index of orkes.io use-case pages
  by pattern / industry, Enterprise documentation (secrets, webhooks, RBAC,
  integrations, agents, human tasks, schedules, SDKs), starters, and the
  Enterprise-docs-vs-OSS-docs rule, with the live `llms.txt` preferred online.
- Agent-friendly two-step login: `orkes login --no-wait` exits 7 (= pending,
  not failure) after printing `Open <url>` / `Code XXXX-XXXX`; the agent relays
  both verbatim, waits for the user or polls `orkes login --timeout 30s`, and
  never asks them to paste anything back. Documented in
  `references/orkes-dev-edition.md` § Agent login, `setup.md`, Rule 15 and
  the setup evals.
- Device-login failure modes in `references/troubleshooting.md`, including
  the exit-7 row.
- `evaluations/orkes-login-device-flow.json`.
- **Anonymous sessions for unattended runs.** `orkes login --anonymous` (or
  `ORKES_ANONYMOUS=1`, which makes `orkes conductor …` start one itself) mints
  a guest session bound to a key on the machine — no browser, no human — and
  prints a `Claim it <url>` + code; it activates profile `developer` and
  writes the `conductor --profile developer` shim with the guest token. The skill relays that link to the person
  exactly once, verbatim, and never blocks on it; treats exit 9 (`this action
  needs a claimed account … Run orkes claim`; today `keys create`) as a
  step-up — stop, name the action, give the link again, `orkes claim
  --timeout 60s` or carry on — never a retry; never runs `orkes logout` on an
  unclaimed session; and skips all of it when `orkes identity show` already
  reports a signed-in account. `orkes claim` keeps the same session and
  profile (level 1, the person's email); exit 5 means the server's identity
  provider has no token-exchange grant → device flow. Documented in
  `references/orkes-dev-edition.md` (journey step 1 / 1b, § Agent login,
  cheat-sheet rows for `--anonymous`, `ORKES_ANONYMOUS`, `claim`, exit 5 / 7 /
  9), `setup.md`, `troubleshooting.md` (exit-9 step-up, "not enabled", lost
  key / new machine) and Rule 15.
- `evaluations/orkes-anonymous-claim.json`.

### Changed

- Rule 15 / `setup.md`: anonymous session is the default for unattended agent
  runs; the device flow stays the path when a person is present and prefers
  to sign in first.
- Default setup no longer creates `localhost` unless the user wants a local
  server; key + secret (`conductor config save --profile developer`) is the
  fallback for CI and clusters without device login. `/conductor-setup`, the
  eval harness system prompt, and the setup evals follow the new default.
- The `orkes` install page is referenced as `https://orkes.io/cli`
  (placeholder — TODO: confirm the install URL before release).
- Eval-context hard budget in `scripts/validate_plugin.py` raised 340k → 360k
  chars to fit the new references (the 300k soft budget was already exceeded).

## 1.8.0

### Added

- End-to-end Conductor Agent guidance for Python, TypeScript, Java, and C#,
  including native agents, supported third-party SDK bridges, remote A2A and
  hosted agents, tools, guardrails, memory, HITL, testing, deployment, serving,
  scheduling, observation, and workflow `AGENT` tasks.
- `/conductor-scaffold-agent`, agent-focused workflow examples, framework
  bridge samples, fallback REST operations, and 40 new agent evaluation cases.
- Deployable software-society and 120-specialist Bengaluru writers' room
  examples. Both use bounded tools and deterministic workflow-owned approval;
  the writers' room isolates phase executions to stay below payload limits.

### Fixed

- Installer verification now tests the native shared skill directories used by
  Codex, Gemini, Cursor, OpenCode, Copilot, Amp, Cline, and Windsurf.
- Task-definition commands now match the current CLI (`conductor task ...`).
- Eval report merging rejects missing shards, missing results, and duplicates.
- Generated SQLite, Python bytecode, coverage, and pytest artifacts are ignored
  and excluded from published packages.

### Changed

- All published manifests and installers are versioned consistently at 1.8.0.
- Plugin CI now runs the 428-check installer/package matrix and all offline
  Python agent example tests in addition to manifest validation.
- Vercel AI examples pin the compatible AI SDK 4 tool shape and document the
  native adapter required for AI SDK 5+.
- First-time setup now creates `developer` and `localhost` profiles, defaults
  skill operations to Developer Edition, and keeps access-key creation and
  one-time secret entry under direct user control.

## 1.7.0

### Added

- Native skill-directory installs: Codex, Gemini, Cursor, and OpenCode now get
  an intact copy of the skill directory at `~/.agents/skills/conductor/`
  (global) or `.agents/skills/conductor/` (project), instead of a single
  assembled markdown file. Cline and Windsurf projects got the same treatment.
  The shared directory is physically written once per run and reused by every
  agent that points at it.
- GitHub Copilot and Amp are now real participants in that shared install
  rather than a hardcoded no-op: installing either one for the first time
  writes the shared directory itself if nothing else has yet, and both get
  their own manifest entry, upgrade path, and refcounted uninstall — the same
  as Codex/Gemini/Cursor/OpenCode. Previously, running the installer for
  copilot or amp alone (with no other shared-dir agent already installed)
  printed a misleading "already covered" message without actually installing
  anything.
- `.openai/plugin.json` for the OpenAI Apps SDK plugin manifest.
- Install summary output is now grouped by physical install location (one
  line per directory, listing every agent that shares it) instead of one line
  per agent.

### Fixed

- `--all --uninstall` now also removes agents whose manifest entry is still
  present but whose CLI/config the installer can no longer detect (e.g. the
  tool itself was uninstalled outside this script) — previously those agents'
  files were silently orphaned because `--all` only looked at what it could
  currently detect.
- `--global --uninstall` for an agent that doesn't support a global install
  (e.g. Amazon Q) now errors explicitly instead of silently doing nothing.
- Reinstalling/upgrading an agent whose files previously lived at a different
  path (e.g. a pre-1.6.6 single-file install) now prints a one-time warning
  naming the old path so it can be cleaned up by hand. The installer never
  auto-deletes it — we can't tell whether the user has since edited that file.
- `--check` now resolves the manifest path the same way install/uninstall do,
  so check-mode output can't disagree with what a real run would do.

### Changed

- `scripts/validate_plugin.py` (the CI version-consistency check) now also
  checks the four files it previously missed: root `plugin.json`,
  `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json`, and
  `.openai/plugin.json` — nine files plus `VERSION` in total, up from six.
  `PUBLISHING.md`'s release checklist and "what CI validates" section were
  updated to match.
- `README.md` and `TESTING.md` updated to describe Copilot/Amp as real
  shared-directory participants rather than passive no-ops.

### Considered, not changed

- A separate review flagged that the manifest (`~/.conductor-skills/manifest.json`,
  or `$project_dir/.conductor-skills/manifest.json`) lives inside Aider's own
  install directory, and Aider's uninstall does `rm -rf` on that directory —
  so uninstalling Aider alone, after installing it alongside other agents,
  deletes everyone else's manifest entries too. This requires installing
  Aider plus at least one other agent into the same manifest and then
  uninstalling only Aider, which is a real but narrow path. Given the low
  likelihood versus the risk of moving where the manifest lives, this was
  deliberately left unfixed in this release.
