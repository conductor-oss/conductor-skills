# Publishing

Maintainer-facing notes for releasing a new version of the Conductor Skills marketplace.

## Distribution channels

The plugin ships through three channels:

1. **Claude Code marketplace** — `/plugin install conductor@conductor-skills` (this repo's `.claude-plugin/marketplace.json`).
2. **install.sh / install.ps1** — `curl ... | bash` for any of the 12 supported AI agents (downloads from GitHub raw).
3. **npm** — `npm install -g @conductor-oss/conductor-skills` then `conductor-skills --agent <name>`. The npm package bundles all the same files and invokes the bundled `install.sh` / `install.ps1` with `CONDUCTOR_SKILLS_LOCAL_DIR=<package-root>` so the install scripts copy from the bundle instead of downloading.

All three channels share the same `VERSION` — bump it in one place; CI fails if any of `plugin.json`, `marketplace.json`, `package.json`, or the `VERSION` constants in the install scripts drift.

## Repo layout

```
.claude-plugin/
  plugin.json          # plugin manifest (single plugin)
  marketplace.json     # marketplace registry that lists this plugin
commands/
  conductor.md                  # /conductor menu
  conductor-setup.md            # /conductor-setup
  conductor-optimize.md         # /conductor-optimize
  conductor-scaffold-worker.md  # /conductor-scaffold-worker
skills/conductor/
  SKILL.md             # the skill itself; frontmatter `name:` must match plugin name
  references/          # lazy-loaded reference docs
  examples/            # narrative examples + raw JSON definitions
  scripts/             # bundled fallback REST script
VERSION                # source-of-truth version string
scripts/validate_plugin.py   # CI validator
.github/workflows/validate-plugin.yml
```

A user installs via:

```
/plugin marketplace add conductor-oss/conductor-skills
/plugin install conductor@conductor-skills
```

## Release checklist

1. **Pick a version** — semver. Follow the rules:
   - **Patch (1.1.0 → 1.1.1)** — wording fixes, doc-only changes, fallback script bug fixes that don't change CLI flags.
   - **Minor (1.1.0 → 1.2.0)** — new task-type docs, new examples, new reference files, additive command coverage.
   - **Major (1.1.0 → 2.0.0)** — restructured file paths users may have linked to, removed commands, breaking schema changes.

2. **Bump the version in six places** (they must agree, and CI enforces it):
   - `VERSION`
   - `.claude-plugin/plugin.json` → `version`
   - `.claude-plugin/marketplace.json` → `plugins[0].version`
   - `package.json` → `version`
   - `install.sh` → `VERSION="..."` constant near the top
   - `install.ps1` → `$SCRIPT_VERSION = "..."` constant near the top

3. **Run validation locally**:
   ```bash
   python3 scripts/validate_plugin.py
   ```
   Confirms JSON syntax, version coherence, and that each marketplace plugin entry resolves to a SKILL.md whose frontmatter name matches.

4. **Run evaluations** (if applicable):
   ```bash
   python3 scripts/run_evals.py --verbose
   ```

5. **Commit and push to `main`**. CI re-runs validation.

6. **Tag the release**:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

7. **Create a GitHub Release** off the tag with a short changelog. The install scripts (`install.sh` / `install.ps1`) read the latest tag for `--upgrade`, so the tag is what users actually pull.

8. **Publish to npm** (after the GitHub tag/release is up):
   ```bash
   # First time only — log in with the @conductor-oss org account:
   npm login --scope=@conductor-oss

   # Sanity check what would be published:
   npm pack --dry-run

   # Publish (the package.json already has publishConfig.access = public):
   npm publish

   # Verify:
   npm view @conductor-oss/conductor-skills version
   ```

9. **Smoke-test the install** in a clean environment, hitting all three channels:
   ```bash
   # 1) Claude Code plugin path
   /plugin marketplace add conductor-oss/conductor-skills
   /plugin install conductor@conductor-skills

   # 2) install-all script (any agent)
   curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --all --upgrade

   # 3) npm path
   npx @conductor-oss/conductor-skills --agent claude
   # or global:
   npm install -g @conductor-oss/conductor-skills && conductor-skills --agent cursor
   ```
   Then in a Claude Code session: `/plugin` should list `conductor` at the new version, and `conductor-skills --version` (npm path) should print the same.

## What CI validates

`scripts/validate_plugin.py`, run by `.github/workflows/validate-plugin.yml`, checks:

- `plugin.json` and `marketplace.json` parse as JSON.
- Both have required fields (`name`, `version`, `description`, `plugins`).
- `VERSION`, `plugin.json:version`, every `marketplace.json:plugins[*].version`, `package.json:version`, and the `VERSION` constants in `install.sh` and `install.ps1` all agree.
- Each marketplace plugin entry resolves to a directory containing `skills/<name>/SKILL.md`.
- Each SKILL.md has YAML frontmatter with a `name:` matching the plugin entry.
- Every file under `commands/` has YAML frontmatter with a `description:`.

It also validates that every JSON file under `skills/*/examples/workflows/` parses. Those files are loaded by users via `conductor workflow create` — broken JSON would surface only at install time, so we catch it at CI time.

## Skill evals (separate workflow)

`.github/workflows/evals.yml` runs the agent eval suite — 19 natural-language scenarios judged by an LLM. It's separate from `validate-plugin.yml` because it costs real API tokens.

### Triggers

- **`workflow_dispatch`** — run on demand. Inputs let you pick the agent model and judge model.
- **`schedule`** — Sundays 08:00 UTC against `claude-sonnet-4-6`. Weekly regression check.
- **`pull_request`** labeled `run-evals` — apply the `run-evals` label to a PR to trigger a run. Skipped on every other PR (cost control).
- **`push` to `main`** — only when files under `skills/`, `commands/`, `evaluations/`, or the eval scripts change.

### Required repository secrets

Set these under **Settings → Secrets and variables → Actions**:

| Secret | Required for | Used by |
|--------|--------------|---------|
| `ANTHROPIC_API_KEY` | All runs (default agent + default judge) | Always |
| `OPENAI_API_KEY` | Runs against `gpt-*` models | Only when model starts with `gpt-` |
| `GEMINI_API_KEY` | Runs against `gemini-*` models | Only when model starts with `gemini-` |

For PR comments on private repos, the default `GITHUB_TOKEN` is sufficient — no extra config needed.

### Outputs

Every run uploads an artifact named `eval-report-<model>` containing:
- `report.json` — machine-readable per-criterion results
- `report.html` — self-contained HTML report (open locally)

On PR runs, the workflow also posts a summary comment with totals + any failed scenarios + partial-pass deltas.

### Approximate cost per run (one model, 19 scenarios)

- Claude-Sonnet-4.6: ~$1 (agent) + ~$1 (judge) = **~$2**
- GPT-5.4: ~$2 (agent) + ~$1 (judge) = **~$3**
- Gemini-3-Flash-Preview: ~$0.20 (agent) + ~$1 (judge) = **~$1.20**

Weekly scheduled runs against the default model cost ~$2/week (~$100/year).

### Running multi-model comparisons

Two paths:

**Option A — one-click via `eval-compare.yml`.** A second workflow at `.github/workflows/eval-compare.yml` runs the suite against three models in parallel (matrix) and produces a single side-by-side HTML report. Triggers:
- `workflow_dispatch` with comma-separated `models` input
- `pull_request` labeled `run-eval-compare`

Cost: ~$6–7 per matrix run. Outputs an `eval-comparison` artifact with the combined HTML. On PR runs, posts one combined summary comment.

**Option B — manual local merge.** Run `workflow_dispatch` on `evals.yml` three times with different `model` inputs, download the three JSON artifacts, then:

```bash
python3 scripts/render_evals_html.py \
  claude-report.json gpt-report.json gemini-report.json \
  -o compare.html --title "3-model comparison"
```

## Adding a new plugin to the marketplace

1. Create `skills/<new-plugin>/SKILL.md` with frontmatter `name: <new-plugin>`.
2. Append an entry to `.claude-plugin/marketplace.json` → `plugins`:
   ```json
   {
     "name": "<new-plugin>",
     "source": "./",
     "description": "...",
     "version": "0.1.0",
     "category": "...",
     "tags": ["..."]
   }
   ```
3. Bump `VERSION` and the existing plugin's version per the rules above (or treat the new plugin's `0.1.0` as independent — see semver guidance).
4. Run `python3 scripts/validate_plugin.py` — should print `Plugin validation OK`.

> **Note:** the current setup assumes one VERSION across all plugins. If we ever publish independently versioned plugins, refactor `validate_plugin.py` to compare `marketplace.json:plugins[*].version` to a per-plugin source instead of one shared VERSION.
