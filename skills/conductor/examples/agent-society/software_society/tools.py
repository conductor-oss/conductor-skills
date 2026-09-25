"""Workspace tools used by the software society.

Every path is constrained to ``SOFTWARE_SOCIETY_WORKSPACE``. Mutations are
idempotent and approval-gated because Conductor may retry tool tasks.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from conductor.ai.agents import tool


MAX_FILE_BYTES = 200_000
MAX_OUTPUT_CHARS = 12_000
IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}


def workspace_root() -> Path:
    """Return the configured workspace without creating it."""
    configured = os.environ.get("SOFTWARE_SOCIETY_WORKSPACE", "society-workspace")
    return Path(configured).expanduser().resolve()


def safe_path(relative_path: str) -> Path:
    """Resolve a relative path and reject traversal outside the workspace."""
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("path must be a non-empty path relative to the society workspace")

    root = workspace_root()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes society workspace: {relative_path}") from exc

    if ".git" in candidate.parts:
        raise ValueError("direct access to .git is not allowed")
    return candidate


def _iter_files(start: Path):
    if not start.exists():
        return
    for candidate in start.rglob("*"):
        if any(part in IGNORED_DIRECTORIES for part in candidate.parts):
            continue
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        try:
            resolved.relative_to(workspace_root())
        except ValueError:
            continue
        yield resolved


@tool(timeout_seconds=30, max_calls=8)
def inspect_workspace(max_files: int = 200) -> dict[str, Any]:
    """List the software workspace so an agent can understand the existing project. Read-only."""
    root = workspace_root()
    if not root.exists():
        return {"workspace": str(root), "exists": False, "files": [], "truncated": False}

    files: list[str] = []
    for candidate in _iter_files(root):
        files.append(str(candidate.relative_to(root)))
        if len(files) >= max(1, min(max_files, 500)):
            break
    return {
        "workspace": str(root),
        "exists": True,
        "files": files,
        "truncated": len(files) >= max(1, min(max_files, 500)),
    }


@tool(timeout_seconds=30, max_calls=30)
def read_workspace_file(path: str, max_bytes: int = MAX_FILE_BYTES) -> dict[str, Any]:
    """Read one UTF-8 text file from the software workspace. Read-only."""
    target = safe_path(path)
    if not target.is_file():
        return {"path": path, "found": False, "content": ""}

    limit = max(1, min(max_bytes, MAX_FILE_BYTES))
    raw = target.read_bytes()
    truncated = len(raw) > limit
    return {
        "path": path,
        "found": True,
        "content": raw[:limit].decode("utf-8", errors="replace"),
        "truncated": truncated,
        "sizeBytes": len(raw),
    }


@tool(timeout_seconds=30, max_calls=20)
def search_workspace(pattern: str, path: str = ".", max_results: int = 100) -> dict[str, Any]:
    """Regex-search text files inside the software workspace. Read-only."""
    expression = re.compile(pattern)
    start = safe_path(path)
    root = workspace_root()
    results: list[dict[str, Any]] = []
    limit = max(1, min(max_results, 200))

    for candidate in _iter_files(start):
        if candidate.stat().st_size > MAX_FILE_BYTES:
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if expression.search(line):
                results.append(
                    {
                        "path": str(candidate.relative_to(root)),
                        "line": line_number,
                        "text": line[:500],
                    }
                )
                if len(results) >= limit:
                    return {"matches": results, "truncated": True}
    return {"matches": results, "truncated": False}


@tool(
    approval_required=True,
    timeout_seconds=90,
    max_calls=8,
    retry_count=2,
    retry_delay_seconds=2,
)
def apply_change_set(changes: list[dict[str, str]]) -> dict[str, Any]:
    """Create or replace a batch of workspace files after human approval.

    Each change must contain ``path`` and full ``content``. Repeating the same
    call is safe: files whose content already matches are left untouched.
    Deletion and access outside the configured workspace are not supported.
    """
    if not changes:
        raise ValueError("changes must contain at least one file")
    if len(changes) > 40:
        raise ValueError("one change set may contain at most 40 files")

    written: list[str] = []
    unchanged: list[str] = []
    for change in changes:
        path = change.get("path", "")
        if "content" not in change:
            raise ValueError(f"change for {path!r} is missing content")
        content = change["content"]
        if not isinstance(content, str):
            raise ValueError(f"content for {path!r} must be text")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"content for {path!r} exceeds {MAX_FILE_BYTES} bytes")

        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8", errors="replace") == content:
            unchanged.append(path)
            continue

        # Atomic replacement makes a Conductor retry safe from partial writes.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, delete=False
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, target)
        written.append(path)

    return {"written": written, "unchanged": unchanged, "workspace": str(workspace_root())}


def _detect_check_profile(root: Path) -> str | None:
    candidates = (
        ("python", ("pyproject.toml", "pytest.ini", "setup.cfg", "requirements.txt")),
        ("node", ("package.json",)),
        ("go", ("go.mod",)),
        ("rust", ("Cargo.toml",)),
        ("gradle", ("gradlew", "build.gradle", "build.gradle.kts")),
        ("maven", ("mvnw", "pom.xml")),
        ("dotnet", ("*.sln", "*.csproj")),
    )
    for profile, markers in candidates:
        for marker in markers:
            if "*" in marker and next(root.glob(marker), None) is not None:
                return profile
            if "*" not in marker and (root / marker).exists():
                return profile
    return None


def _check_command(profile: str, root: Path) -> list[str]:
    commands = {
        "python": [sys.executable, "-m", "pytest", "-q"],
        "node": ["npm", "test", "--silent"],
        "go": ["go", "test", "./..."],
        "rust": ["cargo", "test"],
        "gradle": [str(root / "gradlew"), "test"],
        "maven": [str(root / "mvnw"), "test"] if (root / "mvnw").exists() else ["mvn", "test"],
        "dotnet": ["dotnet", "test"],
    }
    if profile not in commands:
        raise ValueError(f"unsupported check profile {profile!r}; choose one of {sorted(commands)}")
    return commands[profile]


@tool(approval_required=True, timeout_seconds=360, max_calls=10, retry_count=0)
def run_quality_checks(profile: str = "auto") -> dict[str, Any]:
    """Run one fixed, allow-listed project test command after human approval.

    Profiles: auto, python, node, go, rust, gradle, maven, or dotnet. Arbitrary
    commands and shell interpretation are intentionally unsupported.
    """
    root = workspace_root()
    if not root.is_dir():
        return {"profile": profile, "exitCode": None, "error": "workspace does not exist"}

    selected = _detect_check_profile(root) if profile == "auto" else profile
    if selected is None:
        return {
            "profile": profile,
            "exitCode": None,
            "error": "no supported project marker found",
        }
    command = _check_command(selected, root)
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        output = (completed.stdout + "\n" + completed.stderr).strip()
        return {
            "profile": selected,
            "command": command,
            "exitCode": completed.returncode,
            "passed": completed.returncode == 0,
            "output": output[:MAX_OUTPUT_CHARS],
            "truncated": len(output) > MAX_OUTPUT_CHARS,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"profile": selected, "command": command, "exitCode": None, "error": str(exc)}


@tool(timeout_seconds=30, max_calls=12)
def workspace_diff() -> dict[str, Any]:
    """Return the current Git diff and status for the workspace. Read-only."""
    root = workspace_root()
    if not (root / ".git").exists():
        return {"gitRepository": False, "diff": "", "status": ""}

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    diff = subprocess.run(
        ["git", "diff", "--"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "gitRepository": True,
        "status": status.stdout[:MAX_OUTPUT_CHARS],
        "diff": diff.stdout[:MAX_OUTPUT_CHARS],
        "truncated": len(status.stdout) > MAX_OUTPUT_CHARS or len(diff.stdout) > MAX_OUTPUT_CHARS,
    }
