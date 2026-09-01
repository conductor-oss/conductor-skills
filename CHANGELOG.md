# Changelog

All notable changes to the Conductor Skills plugin are documented here. Versions
correspond to the shared `VERSION` file (see [PUBLISHING.md](PUBLISHING.md) for
what that means across the three distribution channels).

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
