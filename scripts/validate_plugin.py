#!/usr/bin/env python3
"""Validate the Claude Code plugin/marketplace manifest.

Checks:
  1. JSON syntax for plugin.json and marketplace.json.
  2. Required top-level fields present.
  3. Plugin version matches VERSION across every file that duplicates it:
     .claude-plugin/plugin.json, .claude-plugin/marketplace.json,
     package.json, install.sh, install.ps1, root plugin.json,
     .cursor-plugin/plugin.json, .cursor-plugin/marketplace.json,
     .openai/plugin.json.
  4. Each plugin's `source` path resolves and contains a SKILL.md.
  5. Frontmatter `name` in SKILL.md matches the plugin entry name.
  6. Installer parity: the SKILL_FILES lists in install.sh and install.ps1 ship
     every file under skills/conductor/** (no missing, no phantom entries).
  7. Every JSON under skills/*/examples/** parses; AGENT tasks inside
     examples/workflows/*.json follow the shipped AGENT contract.
  8. Eval schema for evaluations/*.json (warns when a cited optimization rule
     id has no heading in references/optimization.md).
  9. Eval context-size budget — the bytes run_evals.py puts in the system prompt.

Exits non-zero on any failure. No third-party dependencies.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_FILE = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_FILE = ROOT / ".claude-plugin" / "marketplace.json"
VERSION_FILE = ROOT / "VERSION"
SKILL_ROOT = ROOT / "skills" / "conductor"
INSTALL_SH = ROOT / "install.sh"
INSTALL_PS1 = ROOT / "install.ps1"
EVAL_DIR = ROOT / "evaluations"
OPTIMIZATION_MD = SKILL_ROOT / "references" / "optimization.md"

# Eval context budget (chars). run_evals.py sends SKILL.md + references/*.md +
# examples/*.md as one system prompt; keep it well inside every provider's window.
CONTEXT_WARN_CHARS = 300_000
CONTEXT_FAIL_CHARS = 340_000

# Shipped AGENT task contract (see references/workflow-definition.md).
VALID_AGENT_TYPES = {
    "conductor",
    "a2a",
    "microsoft-foundry",
    "azure-foundry",
    "openai-assistants",
    "bedrock",
}
AGENT_TARGET_KEYS = ("name", "agentUrl", "executionId", "agentConfig", "framework", "skillRef")

REQUIRED_EVAL_KEYS = ("name", "skills", "query", "expected_behavior", "success_criteria")
RULE_ID = re.compile(r"\b([A-F]\d{1,2})\b")
EMPHASIS = re.compile(r"`([^`]*)`|\*\*([^*]*)\*\*")

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing: {path.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {e}")
        return {}


def require(obj: dict, key: str, where: str) -> None:
    if key not in obj:
        fail(f"{where} missing required field: {key!r}")


def read_skill_name(skill_md: Path) -> str | None:
    """Extract `name:` from YAML frontmatter."""
    if not skill_md.exists():
        return None
    text = skill_md.read_text()
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for line in text[3:end].splitlines():
        line = line.strip()
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


# ---------------------------------------------------------------------------
# Installer parity
# ---------------------------------------------------------------------------

def parse_installer_list(path: Path, opener: str) -> list[str] | None:
    """Return the quoted entries of the SKILL_FILES array in an installer script."""
    if not path.exists():
        fail(f"missing: {path.relative_to(ROOT)}")
        return None
    m = re.search(re.escape(opener) + r"(.*?)\n\)", path.read_text(), re.S)
    if not m:
        fail(f"{path.name}: could not find the {opener!r} ... ) block")
        return None
    return re.findall(r'"([^"]+)"', m.group(1))


def check_installer_parity() -> None:
    shipped = {
        str(p.relative_to(ROOT))
        for p in SKILL_ROOT.rglob("*")
        if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts
    }
    lists = {
        "install.sh": parse_installer_list(INSTALL_SH, "SKILL_FILES=("),
        "install.ps1": parse_installer_list(INSTALL_PS1, "$SKILL_FILES = @("),
    }
    for script, entries in lists.items():
        if entries is None:
            continue
        listed = set(entries)
        for dupe in sorted({e for e in entries if entries.count(e) > 1}):
            fail(f"{script}: duplicate SKILL_FILES entry {dupe}")
        for missing in sorted(shipped - listed):
            fail(f"{script}: SKILL_FILES does not ship {missing}")
        for phantom in sorted(listed - shipped):
            fail(f"{script}: SKILL_FILES lists non-existent file {phantom}")
    sh, ps1 = lists["install.sh"], lists["install.ps1"]
    if sh is not None and ps1 is not None and set(sh) != set(ps1):
        fail(
            "install.sh and install.ps1 SKILL_FILES lists differ: "
            + ", ".join(sorted(set(sh) ^ set(ps1)))
        )


# ---------------------------------------------------------------------------
# Example JSON + AGENT lint
# ---------------------------------------------------------------------------

def iter_tasks(tasks):
    """Yield every task in a workflow, descending into container task bodies."""
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        yield task
        for branch in task.get("forkTasks") or []:
            yield from iter_tasks(branch)
        for case in (task.get("decisionCases") or {}).values():
            yield from iter_tasks(case)
        yield from iter_tasks(task.get("defaultCase") or [])
        yield from iter_tasks(task.get("loopOver") or [])


def lint_workflow_example(rel: Path, data) -> None:
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list) or not tasks:
        fail(f"workflow example {rel}: 'tasks' must be a non-empty array")
        return
    has_agent_task = False
    for task in iter_tasks(tasks):
        ref = task.get("taskReferenceName") or task.get("name") or "<unnamed>"
        for key in ("name", "taskReferenceName", "type"):
            if not task.get(key):
                fail(f"workflow example {rel}: task {ref!r} missing {key!r}")
        if task.get("type") != "AGENT":
            continue
        has_agent_task = True
        params = task.get("inputParameters") or {}
        agent_type = params.get("agentType")
        if agent_type is not None and agent_type not in VALID_AGENT_TYPES:
            fail(
                f"workflow example {rel}: AGENT {ref!r} has invalid agentType {agent_type!r} "
                f"(valid: {', '.join(sorted(VALID_AGENT_TYPES))})"
            )
        if "agentName" in params:
            fail(f"workflow example {rel}: AGENT {ref!r} uses 'agentName' — the input field is 'name'")
        if not any(k in params for k in AGENT_TARGET_KEYS):
            fail(
                f"workflow example {rel}: AGENT {ref!r} needs one of "
                + "/".join(AGENT_TARGET_KEYS)
            )
        if agent_type == "conductor" and not params.get("prompt"):
            fail(f"workflow example {rel}: AGENT {ref!r} conductor mode requires 'prompt'")
        max_duration = params.get("maxDurationSeconds")
        if not isinstance(max_duration, int) or isinstance(max_duration, bool) or max_duration <= 0:
            fail(
                f"workflow example {rel}: AGENT {ref!r} needs a positive integer "
                "maxDurationSeconds (optimization rule F1)"
            )

    if has_agent_task:
        timeout = data.get("timeoutSeconds")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
            fail(
                f"workflow example {rel}: workflows containing AGENT tasks need a positive "
                "timeoutSeconds (optimization rules F1/B2)"
            )
        if data.get("timeoutPolicy") not in {"TIME_OUT_WF", "ALERT_ONLY"}:
            fail(
                f"workflow example {rel}: workflows containing AGENT tasks need timeoutPolicy "
                "TIME_OUT_WF or ALERT_ONLY (optimization rules F1/B2)"
            )


def check_example_json() -> None:
    for json_file in sorted(ROOT.glob("skills/*/examples/**/*.json")):
        rel = json_file.relative_to(ROOT)
        is_workflow = json_file.parent.name == "workflows"
        label = "workflow example" if is_workflow else "example"
        try:
            data = json.loads(json_file.read_text())
        except json.JSONDecodeError as e:
            fail(f"{label} {rel}: invalid JSON: {e}")
            continue
        if is_workflow:
            lint_workflow_example(rel, data)


def check_fallback_command_syntax() -> None:
    """Keep documented conductor_api.py calls aligned with its argparse contract."""
    files = [
        *sorted(SKILL_ROOT.rglob("*.md")),
        *sorted((ROOT / "commands").glob("*.md")),
        *sorted(EVAL_DIR.glob("*.json")),
        ROOT / "TESTING.md",
    ]
    command_patterns = {
        "agent-deploy-config": "--file",
        "agent-cancel": "--id",
    }
    prefix = r'(?:python3\s+["\']?\$CONDUCTOR_API["\']?\s+|conductor_api\.py\s+)'
    for path in files:
        if not path.exists():
            continue
        contents = path.read_text()
        for command, required_flag in command_patterns.items():
            pattern = re.compile(
                prefix + re.escape(command) + r"\s+(?!" + re.escape(required_flag) + r"\b)"
            )
            if pattern.search(contents):
                fail(
                    f"{path.relative_to(ROOT)}: documented {command} call must use "
                    f"{required_flag}"
                )


def check_remote_setup_contract() -> None:
    """Reject remote-setup instructions that expose secrets or use obsolete CLI syntax."""
    files = [
        SKILL_ROOT / "SKILL.md",
        *sorted((SKILL_ROOT / "references").glob("*.md")),
        *sorted((ROOT / "commands").glob("*.md")),
        *sorted(EVAL_DIR.glob("*.json")),
        ROOT / "TESTING.md",
    ]
    forbidden = {
        "conductor config save --server": (
            "config save is interactive; use `conductor config save --profile <name>`"
        ),
        "~/.conductor-cli/config.yaml": (
            "profiles use config-<profile>.yaml and raw credential files must not be read"
        ),
        "key/secret auth (token only)": (
            "the fallback supports Orkes key/secret exchange"
        ),
        "Auth: token only": (
            "the fallback supports Orkes key/secret exchange"
        ),
    }
    for path in files:
        if not path.exists():
            continue
        contents = path.read_text()
        for stale, correction in forbidden.items():
            if stale in contents:
                fail(f"{path.relative_to(ROOT)}: stale remote setup text {stale!r}; {correction}")

    setup = SKILL_ROOT / "references" / "setup.md"
    if setup.exists():
        contents = setup.read_text()
        for required in (
            "conductor config save --profile developer",
            "conductor config save --profile localhost",
            "conductor --profile developer workflow list --json",
            "Access Control → Applications",
        ):
            if required not in contents:
                fail(
                    f"{setup.relative_to(ROOT)}: default dual-profile setup missing "
                    f"{required!r}"
                )

    for installer in (ROOT / "install.sh", ROOT / "install.ps1"):
        if not installer.exists():
            continue
        contents = installer.read_text()
        for required in (
            "both my Conductor profiles: developer and localhost",
            "[default] developer",
        ):
            if required not in contents:
                fail(
                    f"{installer.relative_to(ROOT)}: first-install welcome missing "
                    f"{required!r}"
                )

    fallback = SKILL_ROOT / "scripts" / "conductor_api.py"
    if fallback.exists():
        contents = fallback.read_text()
        for required in ("normalize_server_url", "exchange_auth_token", '"/token"'):
            if required not in contents:
                fail(f"{fallback.relative_to(ROOT)}: remote auth support missing {required!r}")

    remote_eval = EVAL_DIR / "remote-orkes-auth.json"
    if not remote_eval.exists():
        fail("missing evaluations/remote-orkes-auth.json regression scenario")


# ---------------------------------------------------------------------------
# Eval schema
# ---------------------------------------------------------------------------

def iter_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from iter_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_strings(v)


def known_rule_ids() -> set[str]:
    if not OPTIMIZATION_MD.exists():
        return set()
    return set(re.findall(r"\*\*([A-F]\d{1,2})\.", OPTIMIZATION_MD.read_text()))


def check_eval_schema() -> None:
    rules = known_rule_ids()
    for eval_file in sorted(EVAL_DIR.glob("*.json")):
        rel = eval_file.relative_to(ROOT)
        try:
            data = json.loads(eval_file.read_text())
        except json.JSONDecodeError as e:
            fail(f"eval {rel}: invalid JSON: {e}")
            continue
        if not isinstance(data, dict):
            fail(f"eval {rel}: top level must be an object")
            continue
        for key in REQUIRED_EVAL_KEYS:
            if key not in data:
                fail(f"eval {rel}: missing required key {key!r}")
        skills = data.get("skills")
        if not isinstance(skills, list) or "conductor" not in skills:
            fail(f"eval {rel}: 'skills' must be a list containing \"conductor\"")
        criteria = data.get("success_criteria")
        if (
            not isinstance(criteria, list)
            or not criteria
            or not all(isinstance(c, str) and c.strip() for c in criteria)
        ):
            fail(f"eval {rel}: 'success_criteria' must be a non-empty list of strings")

        # Rule ids cited in backticks or bold must exist in optimization.md.
        cited: set[str] = set()
        for text in iter_strings(data):
            for m in EMPHASIS.finditer(text):
                cited.update(RULE_ID.findall(m.group(1) or m.group(2) or ""))
        for rule in sorted(cited - rules):
            warn(f"eval {rel}: cites rule {rule} but optimization.md has no **{rule}.** heading")


# ---------------------------------------------------------------------------
# Eval context budget
# ---------------------------------------------------------------------------

def check_ci_shards() -> None:
    """Every evaluations/*.json must match exactly one shard of the CI matrix in
    .github/workflows/evals.yml (each shard is a space-separated list of glob
    prefixes expanded as evaluations/<prefix>*.json)."""
    import fnmatch
    import re

    wf = ROOT / ".github" / "workflows" / "evals.yml"
    if not wf.exists():
        warn("no .github/workflows/evals.yml — skipping shard check")
        return
    m = re.search(r"^\s*shard:\s*\[(.*?)\]\s*$", wf.read_text(), re.M)
    if not m:
        fail("evals.yml: could not find the `shard: [...]` matrix line")
        return
    shards = [x.strip().strip('"').strip("'") for x in m.group(1).split(",") if x.strip()]
    evals = sorted(p.name for p in (ROOT / "evaluations").glob("*.json"))
    for name in evals:
        hits = [sh for sh in shards if any(fnmatch.fnmatchcase(name, prefix + "*.json") for prefix in sh.split())]
        if not hits:
            fail(f"evaluations/{name} matches no CI shard in evals.yml ({shards})")
        elif len(hits) > 1:
            fail(f"evaluations/{name} matches {len(hits)} CI shards: {hits}")


def eval_context_size() -> int:
    """Size of the skill context run_evals.py sends as the agent's system prompt.

    Prefers the real loader so the two never drift; falls back to the same
    globs (SKILL.md + references/*.md + examples/*.md) if the import fails.
    """
    try:
        sys.dont_write_bytecode = True  # do not litter scripts/__pycache__ in the repo
        sys.path.insert(0, str(ROOT / "scripts"))
        import run_evals  # noqa: WPS433 — local module, stdlib only

        return len(run_evals.load_skill_context())
    except Exception:
        files = [
            SKILL_ROOT / "SKILL.md",
            *sorted((SKILL_ROOT / "references").glob("*.md")),
            *sorted((SKILL_ROOT / "examples").glob("*.md")),
        ]
        return sum(len(f.read_text()) for f in files if f.exists())


def main() -> int:
    plugin = load_json(PLUGIN_FILE)
    marketplace = load_json(MARKETPLACE_FILE)

    if plugin:
        for k in ("name", "version", "description"):
            require(plugin, k, "plugin.json")

    if marketplace:
        for k in ("name", "plugins"):
            require(marketplace, k, "marketplace.json")
        if not isinstance(marketplace.get("plugins"), list) or not marketplace["plugins"]:
            fail("marketplace.json: 'plugins' must be a non-empty array")

    # Version coherence
    file_version = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else None
    if file_version is None:
        fail("missing VERSION file")
    plugin_version = plugin.get("version")
    if plugin_version and file_version and plugin_version != file_version:
        fail(f"version mismatch: plugin.json={plugin_version} VERSION={file_version}")
    for entry in marketplace.get("plugins", []) or []:
        v = entry.get("version")
        if v and file_version and v != file_version:
            fail(
                f"version mismatch: marketplace.json plugin {entry.get('name')!r}={v} VERSION={file_version}"
            )

    # package.json version (npm distribution)
    pkg_json_path = ROOT / "package.json"
    if pkg_json_path.exists():
        try:
            pkg_json = json.loads(pkg_json_path.read_text())
            npm_version = pkg_json.get("version")
            if npm_version and file_version and npm_version != file_version:
                fail(f"version mismatch: package.json={npm_version} VERSION={file_version}")
        except json.JSONDecodeError as e:
            fail(f"invalid JSON in package.json: {e}")

    # Other per-agent plugin/marketplace manifests that duplicate the version.
    for rel_path in (
        "plugin.json",
        ".cursor-plugin/plugin.json",
        ".openai/plugin.json",
    ):
        path = ROOT / rel_path
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            fail(f"invalid JSON in {rel_path}: {e}")
            continue
        v = data.get("version")
        if v and file_version and v != file_version:
            fail(f"version mismatch: {rel_path}={v} VERSION={file_version}")

    cursor_marketplace_path = ROOT / ".cursor-plugin" / "marketplace.json"
    if cursor_marketplace_path.exists():
        try:
            cursor_marketplace = json.loads(cursor_marketplace_path.read_text())
        except json.JSONDecodeError as e:
            fail(f"invalid JSON in .cursor-plugin/marketplace.json: {e}")
        else:
            meta_version = cursor_marketplace.get("metadata", {}).get("version")
            if meta_version and file_version and meta_version != file_version:
                fail(
                    f"version mismatch: .cursor-plugin/marketplace.json metadata.version="
                    f"{meta_version} VERSION={file_version}"
                )
            for entry in cursor_marketplace.get("plugins", []) or []:
                v = entry.get("version")
                if v and file_version and v != file_version:
                    fail(
                        f"version mismatch: .cursor-plugin/marketplace.json plugin "
                        f"{entry.get('name')!r}={v} VERSION={file_version}"
                    )

    # install.sh / install.ps1 VERSION constants
    for script_name, pattern in (
        ("install.sh", r'VERSION="([^"]+)"'),
        ("install.ps1", r'\$SCRIPT_VERSION = "([^"]+)"'),
    ):
        script = ROOT / script_name
        if script.exists():
            m = re.search(pattern, script.read_text())
            if m and file_version and m.group(1) != file_version:
                fail(f"version mismatch: {script_name}={m.group(1)} VERSION={file_version}")

    # Source path + SKILL.md per marketplace entry
    for entry in marketplace.get("plugins", []) or []:
        name = entry.get("name")
        source = entry.get("source", "")
        if not name:
            fail("marketplace.json: a plugin entry has no 'name'")
            continue

        # `source` is relative to the marketplace root. "./" means the repo itself.
        source_dir = (ROOT / source).resolve() if source else ROOT
        if not source_dir.exists() or not source_dir.is_dir():
            fail(f"plugin {name!r}: source {source!r} does not resolve to a directory")
            continue

        # Find the matching SKILL.md. Try the conventional location first
        # (`skills/<name>/SKILL.md`); if not present, walk the source dir for
        # any SKILL.md whose frontmatter `name:` matches. This keeps the
        # validator working when future plugins use a different layout.
        skill_md = source_dir / "skills" / name / "SKILL.md"
        if not skill_md.exists():
            skill_md = None
            # Skip noisy / unrelated subtrees.
            for candidate in source_dir.rglob("SKILL.md"):
                rel = candidate.relative_to(source_dir).parts
                if rel and rel[0] in {".git", "node_modules", ".github", "evaluations"}:
                    continue
                if read_skill_name(candidate) == name:
                    skill_md = candidate
                    break
            if skill_md is None:
                fail(
                    f"plugin {name!r}: no SKILL.md found under {source_dir.relative_to(ROOT)} "
                    f"with frontmatter name={name!r}"
                )
                continue

        skill_name = read_skill_name(skill_md)
        if skill_name is None:
            fail(f"plugin {name!r}: SKILL.md has no 'name:' frontmatter")
        elif skill_name != name:
            fail(
                f"plugin {name!r}: SKILL.md frontmatter name={skill_name!r} does not match marketplace entry"
            )

    # Slash commands — every .md under commands/ must have frontmatter with description
    commands_dir = ROOT / "commands"
    if commands_dir.is_dir():
        for cmd_file in sorted(commands_dir.rglob("*.md")):
            text = cmd_file.read_text()
            rel = cmd_file.relative_to(ROOT)
            if not text.startswith("---"):
                fail(f"command {rel}: missing YAML frontmatter")
                continue
            end = text.find("\n---", 3)
            if end == -1:
                fail(f"command {rel}: malformed frontmatter (no closing ---)")
                continue
            fm = text[3:end]
            if not any(line.strip().startswith("description:") for line in fm.splitlines()):
                fail(f"command {rel}: frontmatter missing 'description:'")

    # Installer parity — every shipped skill file is in both installer lists.
    check_installer_parity()

    # Example JSON — every file under skills/*/examples/** must parse; AGENT lint for workflows.
    check_example_json()

    # Fallback command examples must match conductor_api.py's required flags.
    check_fallback_command_syntax()

    # Remote setup docs must match the current CLI and fallback auth contract.
    check_remote_setup_contract()

    # Eval schema — every evaluations/*.json has the keys run_evals.py relies on.
    check_eval_schema()

    # CI shards — every eval file lands in exactly one shard of the evals.yml matrix.
    check_ci_shards()

    # Eval context budget.
    size = eval_context_size()
    print(f"Eval context size: {size} chars (~{size // 4} tokens)")
    if size > CONTEXT_FAIL_CHARS:
        fail(f"eval context size {size} chars exceeds hard budget {CONTEXT_FAIL_CHARS}")
    elif size > CONTEXT_WARN_CHARS:
        warn(f"eval context size {size} chars exceeds soft budget {CONTEXT_WARN_CHARS}")

    if warnings:
        print("Plugin validation warnings:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    if errors:
        print("Plugin validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Plugin validation OK (version {file_version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
