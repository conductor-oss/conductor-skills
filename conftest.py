"""Make the standalone Python examples importable from a repository-level test run."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
for relative in (
    "skills/conductor/examples/agent-society",
    "skills/conductor/examples/bengaluru-writers-room",
    "skills/conductor/examples/agents/python",
):
    sys.path.insert(0, str(ROOT / relative))
