#!/usr/bin/env python3
"""Validate the Claude Code plugin/marketplace manifest.

Checks:
  1. JSON syntax for plugin.json and marketplace.json.
  2. Required top-level fields present.
  3. Plugin version matches between plugin.json, marketplace.json, and VERSION.
  4. Each plugin's `source` path resolves and contains a SKILL.md.
  5. Frontmatter `name` in SKILL.md matches the plugin entry name.

Exits non-zero on any failure. No third-party dependencies.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_FILE = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_FILE = ROOT / ".claude-plugin" / "marketplace.json"
VERSION_FILE = ROOT / "VERSION"

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


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

    # install.sh / install.ps1 VERSION constants
    for script_name, pattern in (
        ("install.sh", r'VERSION="([^"]+)"'),
        ("install.ps1", r'\$SCRIPT_VERSION = "([^"]+)"'),
    ):
        script = ROOT / script_name
        if script.exists():
            import re
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

        # `source` is a relative path string ("./" means the repo itself).
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

    # Workflow JSON examples — every file under skills/*/examples/workflows/ must parse.
    for wf_file in sorted(ROOT.glob("skills/*/examples/workflows/*.json")):
        try:
            json.loads(wf_file.read_text())
        except json.JSONDecodeError as e:
            fail(f"workflow example {wf_file.relative_to(ROOT)}: invalid JSON: {e}")

    if errors:
        print("Plugin validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"Plugin validation OK (version {file_version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
