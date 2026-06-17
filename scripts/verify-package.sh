#!/usr/bin/env bash
# Pre-publish verification — pack the npm tarball and exercise every agent
# install/uninstall path in an isolated HOME so it can't touch real settings.
#
# Usage:
#   scripts/verify-package.sh                 # full suite (recommended)
#   scripts/verify-package.sh --quick         # skip the npm-install smoke test
#   scripts/verify-package.sh --keep-sandbox  # preserve sandbox on success
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -t 1 ]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

step()  { printf "\n${BOLD}${BLUE}▸ %s${NC}\n" "$*"; }
pass()  { printf "  ${GREEN}✓${NC} %s\n" "$*"; PASS=$((PASS+1)); }
fail()  { printf "  ${RED}✗${NC} %s\n" "$*"; FAIL=$((FAIL+1)); FAILURES+=("$*"); }
info()  { printf "  ${BLUE}·${NC} %s\n" "$*"; }
die()   { printf "${RED}fatal:${NC} %s\n" "$*" >&2; exit 1; }

PASS=0; FAIL=0; FAILURES=()
QUICK=false
KEEP_SANDBOX=false
for arg in "$@"; do
  case "$arg" in
    --quick)         QUICK=true ;;
    --keep-sandbox)  KEEP_SANDBOX=true ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) die "unknown flag: $arg" ;;
  esac
done

assert() {
  local label="$1" cond="$2"
  if eval "$cond"; then pass "$label"; else fail "$label"; fi
}

cat <<EOF
${BOLD}Conductor Skills — pre-publish verification${NC}

What this script does:
  • Builds the npm tarball (\`npm pack\`)
  • Tests every agent × global+project install/uninstall path
  • Validates the Claude upgrade flow (stale legacy dir + cache cleanup)
  • Simulates an end-user \`npm install -g\` from the tarball

What this script does ${BOLD}NOT${NC} do:
  • Touch your real \$HOME or ~/.claude/ — everything runs in mktemp sandboxes
  • Install anything for you to use — this is a ${BOLD}regression test${NC}, not an installer

If you want to actually install/upgrade Conductor on your real machine:
  bash install.sh --agent claude --global

─────────────────────────────────────────────────────────────
EOF

# ─────────────────────────────────────────────────────────────────────────────
# 0. Preflight — versions, required tools
# ─────────────────────────────────────────────────────────────────────────────
step "Preflight"
command -v npm     >/dev/null || die "npm not found on PATH"
command -v node    >/dev/null || die "node not found on PATH"
command -v python3 >/dev/null || die "python3 not found on PATH"
command -v bash    >/dev/null || die "bash not found on PATH"

PKG_VERSION=$(node -p "require('$REPO_ROOT/package.json').version")
FILE_VERSION=$(cat "$REPO_ROOT/VERSION" | tr -d '[:space:]')
INSTALL_SH_VERSION=$(grep '^VERSION=' "$REPO_ROOT/install.sh" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
PLUGIN_VERSION=$(python3 -c "import json; print(json.load(open('$REPO_ROOT/.claude-plugin/plugin.json'))['version'])")
info "package.json:               $PKG_VERSION"
info "VERSION:                    $FILE_VERSION"
info "install.sh:                 $INSTALL_SH_VERSION"
info ".claude-plugin/plugin.json: $PLUGIN_VERSION"

# Per the marketplace schema, plugin version lives in plugin.json, not in
# marketplace.json's plugin entry. So we check 4 places, not 5.
assert "all four versions agree" \
  "[ '$PKG_VERSION' = '$FILE_VERSION' ] && [ '$FILE_VERSION' = '$INSTALL_SH_VERSION' ] && [ '$INSTALL_SH_VERSION' = '$PLUGIN_VERSION' ]"

# ─────────────────────────────────────────────────────────────────────────────
# 0a. Marketplace.json schema validation
#
# This block catches runtime errors that JSON-parse validation alone misses.
# History: we shipped 1.6.1 with `source: "."` — JSON-valid, schema-shaped, but
# Claude Code rejected it with "source type your Claude Code version does not
# support". This step would have caught that before publish.
#
# Valid source values (based on the schema used by claude-plugins-official):
#   - String relative path STARTING WITH "./"  (e.g. "./", "./plugins/foo")
#   - Object with discriminator: {"source": "github"|"git-subdir"|"url", ...}
# ─────────────────────────────────────────────────────────────────────────────
step "Marketplace.json schema validation"

market_check=$(python3 - "$REPO_ROOT/.claude-plugin/marketplace.json" <<'PY'
import json, re, sys
path = sys.argv[1]
with open(path) as f:
    m = json.load(f)

errors = []
warnings = []

if 'name' not in m:
    errors.append("missing top-level 'name'")
if 'plugins' not in m or not isinstance(m['plugins'], list):
    errors.append("missing or non-list 'plugins'")
    print("\n".join(errors)); sys.exit(1)

VALID_OBJECT_SOURCES = {"github", "git-subdir", "url", "git", "local"}
for i, p in enumerate(m.get('plugins', [])):
    label = f"plugins[{i}] (name={p.get('name','<missing>')!r})"
    if 'name' not in p:
        errors.append(f"{label}: missing 'name'")
    if 'source' not in p:
        errors.append(f"{label}: missing 'source'")
        continue
    src = p['source']
    if isinstance(src, str):
        # String form must begin with './' to be recognized as a relative path.
        # The exact bug we hit in 1.6.1: source="." (no slash) caused
        # "source type your Claude Code version does not support".
        # Bare './' (the marketplace root) IS valid: for a single-plugin repo
        # where the plugin IS the marketplace root, './' is the canonical form
        # (verified installing on Claude Code 2.1.179; same form used by other
        # single-plugin marketplaces). It also avoids a redundant network clone
        # that the object 'github' form triggers — and the SSH-rewrite failures
        # that clone causes for users with url.insteadOf git configs.
        if not src.startswith('./'):
            errors.append(
                f"{label}: source string {src!r} must start with './' "
                f"(e.g. './' for the repo root, or './plugins/foo' for a subdir)"
            )
    elif isinstance(src, dict):
        kind = src.get('source')
        if kind not in VALID_OBJECT_SOURCES:
            errors.append(
                f"{label}: source object .source={kind!r} must be one of {sorted(VALID_OBJECT_SOURCES)}"
            )
    else:
        errors.append(f"{label}: source must be string or object, got {type(src).__name__}")
    if 'version' in p:
        warnings.append(f"{label}: 'version' in marketplace.json plugin entry — schema says version lives in plugin.json")

if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
if warnings:
    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)
PY
)
market_rc=$?
if [ $market_rc -eq 0 ]; then
  pass "marketplace.json source format is recognized by Claude Code"
else
  fail "marketplace.json schema check"
  echo "$market_check" | sed 's/^/    /'
fi

# Cross-check against a known-good marketplace if we have one cached locally —
# protects against drift if Anthropic adds new source types in the future.
if [ -f "$HOME/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json" ]; then
  known_good=$(python3 -c "
import json
m = json.load(open('$HOME/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json'))
seen = set()
for p in m['plugins']:
    s = p.get('source')
    if isinstance(s, str):
        seen.add('string-./*' if s.startswith('./') else f'string-{s!r}')
    elif isinstance(s, dict):
        seen.add(f\"object-{s.get('source')}\")
print(' '.join(sorted(seen)))
")
  info "known-good source formats observed upstream: $known_good"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 1. Lint shell scripts
# ─────────────────────────────────────────────────────────────────────────────
step "Lint install.sh"
bash -n "$REPO_ROOT/install.sh" 2>&1 && pass "install.sh parses" || fail "install.sh parse error"

# ─────────────────────────────────────────────────────────────────────────────
# 2. npm pack — build the actual tarball that would publish
# ─────────────────────────────────────────────────────────────────────────────
step "Build npm tarball"
SANDBOX=$(mktemp -d -t verify-package-XXXXXX)
trap 'if [ "$KEEP_SANDBOX" = "false" ] || [ $FAIL -gt 0 ]; then :; fi; if [ "$KEEP_SANDBOX" = "false" ] && [ $FAIL -eq 0 ]; then rm -rf "$SANDBOX"; fi' EXIT
info "sandbox: $SANDBOX"

cd "$SANDBOX"
TARBALL_NAME=$(npm pack "$REPO_ROOT" 2>/dev/null | tail -1)
TARBALL="$SANDBOX/$TARBALL_NAME"
assert "tarball created: $TARBALL_NAME" "[ -f '$TARBALL' ]"

# Required files in tarball
step "Verify tarball contents"
EXTRACT="$SANDBOX/extracted"
mkdir -p "$EXTRACT"
tar -xzf "$TARBALL" -C "$EXTRACT"
PKG_DIR="$EXTRACT/package"

for required in \
  "package.json" \
  "VERSION" \
  "install.sh" \
  "install.ps1" \
  "bin/conductor-skills.js" \
  ".claude-plugin/plugin.json" \
  ".claude-plugin/marketplace.json" \
  "skills/conductor/SKILL.md" \
  "skills/conductor/references/setup.md" \
  "skills/conductor/references/cli-index.md" \
  "skills/conductor/examples/llm-chat.md" \
  "skills/conductor/scripts/conductor_api.py"
do
  assert "tarball contains $required" "[ -f '$PKG_DIR/$required' ]"
done

# Claude Code's plugin loader scans `agents/` for *.md subagent definitions.
# If we ship non-MD files (or no agents/ at all), that's fine. But the moment
# someone adds a YAML or other-format file there, Claude shows "1 error" in
# the /plugin UI. Guard against accidental reintroduction.
if [ -d "$PKG_DIR/agents" ]; then
  bad_count=$(find "$PKG_DIR/agents" -maxdepth 1 -type f ! -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  assert "tarball: agents/ has only *.md files (Claude Code's subagent format)" \
    "[ $bad_count -eq 0 ]"
fi
assert "tarball: no agents/openai.yaml (the regression we just fixed)" \
  "[ ! -f '$PKG_DIR/agents/openai.yaml' ]"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Agent matrix — install/reinstall/uninstall every supported agent
# ─────────────────────────────────────────────────────────────────────────────
step "Agent matrix (12 agents × install/reinstall/uninstall × global+project)"
info "running against extracted tarball at $PKG_DIR"

# agent | global_path | project_path | supports_global
SPECS=(
  "claude|.claude/settings.json|.claude/settings.json|yes"
  "codex|.codex/AGENTS.md|AGENTS.md|yes"
  "gemini|.gemini/GEMINI.md|GEMINI.md|yes"
  "cursor|.cursor/skills/conductor/SKILL.md|.cursor/rules/conductor.mdc|yes"
  "windsurf|.codeium/windsurf/memories/global_rules.md|.windsurfrules|yes"
  "roo|.roo/rules/conductor.md|.roo/rules/conductor.md|yes"
  "amp|.config/AGENTS.md|.amp/instructions.md|yes"
  "aider|.conductor-skills/SKILL.md|.conductor-skills/SKILL.md|yes"
  "opencode|.config/opencode/skills/conductor/SKILL.md|AGENTS.md|yes"
  "cline|-|.clinerules|no"
  "copilot|-|.github/copilot-instructions.md|no"
  "amazonq|-|.amazonq/rules/conductor.md|no"
)

run_install_sh() {
  local agent_home="$1" agent_proj="$2"; shift 2
  HOME="$agent_home" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
    bash "$PKG_DIR/install.sh" --project-dir "$agent_proj" "$@" \
    >"$agent_home/last.log" 2>&1
}

test_agent() {
  local agent="$1" gpath="$2" ppath="$3" mode="$4"

  local box="$SANDBOX/matrix/${agent}-${mode}"
  mkdir -p "$box/home" "$box/proj"

  local target manifest flag
  if [ "$mode" = "global" ]; then
    target="$box/home/$gpath"
    manifest="$box/home/.conductor-skills/manifest.json"
    flag="--global"
  else
    target="$box/proj/$ppath"
    manifest="$box/proj/.conductor-skills/manifest.json"
    flag=""
  fi

  run_install_sh "$box/home" "$box/proj" --agent "$agent" $flag
  assert "[$agent/$mode] install ok" "[ \$? -eq 0 ]"
  assert "[$agent/$mode] target exists ($([[ $mode == global ]] && echo ~/ || echo \$proj/)$([[ $mode == global ]] && echo "$gpath" || echo "$ppath"))" "[ -e '$target' ]"
  assert "[$agent/$mode] manifest records v$PKG_VERSION" "grep -q '\"version\": \"$PKG_VERSION\"' '$manifest' 2>/dev/null"

  if [ "$agent" = "claude" ]; then
    assert "[claude/$mode] extraKnownMarketplaces.conductor-skills key written" "grep -q 'conductor-skills' '$target'"
    assert "[claude/$mode] enabledPlugins.conductor@conductor-skills key written" "grep -q 'conductor@conductor-skills' '$target'"
    # Dual install — skill files also written to ~/.claude/skills/conductor/
    assert "[claude/$mode] skill files copied to ~/.claude/skills/conductor/SKILL.md" \
      "[ -f '$box/home/.claude/skills/conductor/SKILL.md' ]"
    assert "[claude/$mode] skill includes references/" \
      "[ -d '$box/home/.claude/skills/conductor/references' ]"
    assert "[claude/$mode] skill includes examples/" \
      "[ -d '$box/home/.claude/skills/conductor/examples' ]"
  fi

  # Idempotent re-install — claude is the exception, always re-runs to bust caches
  run_install_sh "$box/home" "$box/proj" --agent "$agent" $flag
  if [ "$agent" = "claude" ]; then
    assert "[claude/$mode] re-install runs unconditionally (cache bust)" \
      "! grep -q 'already at v$PKG_VERSION' '$box/home/last.log'"
  else
    assert "[$agent/$mode] re-install is idempotent" \
      "grep -q 'already at v$PKG_VERSION' '$box/home/last.log'"
  fi

  # Uninstall
  run_install_sh "$box/home" "$box/proj" --agent "$agent" $flag --uninstall
  if [ "$agent" = "claude" ]; then
    assert "[claude/$mode] settings.json preserved after uninstall" "[ -f '$target' ]"
    assert "[claude/$mode] Conductor marketplace key removed" "! grep -q 'conductor-skills' '$target'"
    assert "[claude/$mode] Conductor plugin key removed" "! grep -q 'conductor@conductor-skills' '$target'"
    assert "[claude/$mode] skill dir removed on uninstall" \
      "[ ! -d '$box/home/.claude/skills/conductor' ]"
  elif [ "$agent" = "aider" ]; then
    local skilldir
    if [ "$mode" = "global" ]; then skilldir="$box/home/.conductor-skills"
    else skilldir="$box/proj/.conductor-skills"; fi
    assert "[aider/$mode] skill dir removed on uninstall" "[ ! -d '$skilldir' ]"
  else
    assert "[$agent/$mode] target removed on uninstall" "[ ! -e '$target' ]"
  fi
}

for spec in "${SPECS[@]}"; do
  IFS='|' read -r agent gpath ppath supports_global <<< "$spec"
  if [ "$supports_global" = "yes" ]; then
    test_agent "$agent" "$gpath" "$ppath" "global"
  fi
  test_agent "$agent" "$gpath" "$ppath" "project"
done

# ─────────────────────────────────────────────────────────────────────────────
# 3b. Upgrade-from-older-version path — file-based agents (the 1.5.0→1.6.x bug)
#
# Historical bug: `bash install.sh --all` against a v1.5.0 install ran the
# "Upgrading codex from v1.5.0 to v1.6.3" log line but silently skipped the
# actual file write — because safe_write's `Overwrite? [y/N]` prompt got an
# empty answer from non-interactive stdin. Fix: when manifest says older
# version, force-overwrite (file is ours, user already consented on install).
# ─────────────────────────────────────────────────────────────────────────────
step "Upgrade-from-older-version (file-based agents must actually overwrite)"

for agent in codex gemini windsurf; do
  UPGHOME="$SANDBOX/upg-$agent"
  mkdir -p "$UPGHOME"

  # Seed: manifest claims agent is at v1.5.0, AGENTS.md contains old marker text.
  manifest="$UPGHOME/.conductor-skills/manifest.json"
  mkdir -p "$(dirname "$manifest")"
  cat > "$manifest" <<EOF
{
  "schema_version": 1,
  "installations": {
    "$agent": {
      "version": "1.5.0",
      "installed_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z",
      "mode": "global",
      "target_path": "/PLACEHOLDER"
    }
  }
}
EOF

  case "$agent" in
    codex)    target="$UPGHOME/.codex/AGENTS.md" ;;
    gemini)   target="$UPGHOME/.gemini/GEMINI.md" ;;
    windsurf) target="$UPGHOME/.codeium/windsurf/memories/global_rules.md" ;;
  esac
  mkdir -p "$(dirname "$target")"
  echo "STALE-1.5.0-MARKER" > "$target"

  # Run install WITHOUT --upgrade, WITHOUT --force — simulating real user
  # running `npx ... --all` on an old install.
  HOME="$UPGHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
    bash "$PKG_DIR/install.sh" --agent "$agent" --global </dev/null \
    >"$UPGHOME/upgrade.log" 2>&1

  assert "[$agent upgrade] file overwritten (no STALE-1.5.0-MARKER remains)" \
    "! grep -q 'STALE-1.5.0-MARKER' '$target'"
  assert "[$agent upgrade] file contains fresh skill content" \
    "grep -q 'name: conductor' '$target'"
  assert "[$agent upgrade] manifest now records new version" \
    "grep -q '\"version\": \"$PKG_VERSION\"' '$manifest'"
done

# ─────────────────────────────────────────────────────────────────────────────
# 3a. Claude upgrade path — stale legacy dir + old plugin cache must be busted
# ─────────────────────────────────────────────────────────────────────────────
step "Claude upgrade path (legacy skill dir + old cache must be cleaned)"
UPHOME="$SANDBOX/claude-upgrade-home"
mkdir -p "$UPHOME/.claude/skills/conductor" \
         "$UPHOME/.claude/plugins/cache/conductor-skills/conductor/1.0.0" \
         "$UPHOME/.claude/plugins/marketplaces/conductor-skills"
echo "# stale" > "$UPHOME/.claude/skills/conductor/SKILL.md"
echo "stale cache content" > "$UPHOME/.claude/plugins/cache/conductor-skills/conductor/1.0.0/marker.txt"
echo "stale marketplace clone" > "$UPHOME/.claude/plugins/marketplaces/conductor-skills/marker.txt"

# Pre-existing settings.json with an OLD-style enabledPlugins entry already set,
# which would normally make the install a silent no-op.
mkdir -p "$UPHOME/proj"
cat > "$UPHOME/.claude/settings.json" <<EOF
{
  "model": "opus[1m]",
  "enabledPlugins": {
    "conductor@conductor-skills": true,
    "some-other@marketplace": true
  }
}
EOF

HOME="$UPHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
  bash "$PKG_DIR/install.sh" --project-dir "$UPHOME/proj" --agent claude --global \
  >"$UPHOME/upgrade.log" 2>&1

assert "upgrade: ~/.claude/skills/conductor OVERWRITTEN with fresh files (not the stale stub)" \
  "[ -f '$UPHOME/.claude/skills/conductor/SKILL.md' ] && ! grep -q '# stale' '$UPHOME/.claude/skills/conductor/SKILL.md'"
assert "upgrade: stale plugin cache removed" \
  "[ ! -d '$UPHOME/.claude/plugins/cache/conductor-skills' ]"
assert "upgrade: stale marketplace clone removed" \
  "[ ! -d '$UPHOME/.claude/plugins/marketplaces/conductor-skills' ]"

# Also stage a stale entry in installed_plugins.json and make sure we clean it
mkdir -p "$UPHOME/.claude/plugins"
cat > "$UPHOME/.claude/plugins/installed_plugins.json" <<'EOF'
{
  "version": 2,
  "plugins": {
    "frontend-design@claude-plugins-official": [{"scope":"user","version":"unknown"}],
    "conductor@conductor-skills": [{"scope":"project","installPath":"/old/v1.0.0","version":"1.0.0"}]
  }
}
EOF
HOME="$UPHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
  bash "$PKG_DIR/install.sh" --project-dir "$UPHOME/proj" --agent claude --global \
  >>"$UPHOME/upgrade.log" 2>&1
assert "upgrade: stale registry entry for conductor@conductor-skills removed" \
  "! python3 -c 'import json; r=json.load(open(\"$UPHOME/.claude/plugins/installed_plugins.json\")); exit(0 if \"conductor@conductor-skills\" in r.get(\"plugins\",{}) else 1)'"
assert "upgrade: unrelated registry entries preserved" \
  "python3 -c 'import json; r=json.load(open(\"$UPHOME/.claude/plugins/installed_plugins.json\")); exit(0 if \"frontend-design@claude-plugins-official\" in r.get(\"plugins\",{}) else 1)'"
assert "upgrade: extraKnownMarketplaces added" \
  "grep -q 'conductor-skills' '$UPHOME/.claude/settings.json'"
assert "upgrade: other enabledPlugins preserved" \
  "grep -q 'some-other@marketplace' '$UPHOME/.claude/settings.json'"
assert "upgrade: other settings (model) preserved" \
  "grep -q 'opus\\[1m\\]' '$UPHOME/.claude/settings.json'"

# Re-run install when manifest is already up-to-date — claude must NOT skip
# (other agents do skip when manifest matches; claude's plugin cache lives
# outside the manifest so the cache bust must run unconditionally).
echo "# new stale" > "$UPHOME/.claude/skills/conductor/SKILL.md"
HOME="$UPHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
  bash "$PKG_DIR/install.sh" --project-dir "$UPHOME/proj" --agent claude --global \
  >"$UPHOME/upgrade-rerun.log" 2>&1

assert "claude rerun: did NOT show 'already at version, skipping'" \
  "! grep -q 'claude already at v.*skipping' '$UPHOME/upgrade-rerun.log'"
assert "claude rerun: skill dir refreshed on re-install (no stale content)" \
  "[ -f '$UPHOME/.claude/skills/conductor/SKILL.md' ] && ! grep -q '# new stale' '$UPHOME/.claude/skills/conductor/SKILL.md'"

# But other agents (e.g. codex) should still skip when manifest matches
mkdir -p "$UPHOME/proj"
HOME="$UPHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
  bash "$PKG_DIR/install.sh" --project-dir "$UPHOME/proj" --agent codex --global \
  >"$UPHOME/codex-first.log" 2>&1
HOME="$UPHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
  bash "$PKG_DIR/install.sh" --project-dir "$UPHOME/proj" --agent codex --global \
  >"$UPHOME/codex-rerun.log" 2>&1
assert "codex rerun: DOES show 'already at version, skipping' (existing behavior preserved)" \
  "grep -q 'codex already at v.*skipping' '$UPHOME/codex-rerun.log'"

# Uninstall removes skill dir + settings.json keys + caches
HOME="$UPHOME" CONDUCTOR_SKILLS_LOCAL_DIR="$PKG_DIR" \
  bash "$PKG_DIR/install.sh" --agent claude --global --uninstall >>"$UPHOME/upgrade.log" 2>&1

assert "uninstall: ~/.claude/skills/conductor removed" \
  "[ ! -d '$UPHOME/.claude/skills/conductor' ]"
assert "uninstall: enabledPlugins.conductor@conductor-skills removed" \
  "! grep -q 'conductor@conductor-skills' '$UPHOME/.claude/settings.json'"
assert "uninstall: other enabledPlugins still preserved" \
  "grep -q 'some-other@marketplace' '$UPHOME/.claude/settings.json'"

# ─────────────────────────────────────────────────────────────────────────────
# 4. npx invocation — `npx --package=<tarball> conductor-skills --all`
# This is the EXACT code path that `npx @conductor-oss/conductor-skills --all`
# will take after publish. Different from `npm install -g` (no PATH symlink;
# npx extracts the tarball into its own cache and resolves `bin` via package.json).
# ─────────────────────────────────────────────────────────────────────────────
if [ "$QUICK" = "true" ]; then
  step "Skipping npx invocation test (--quick)"
else
  step "npx invocation (simulates 'npx @conductor-oss/conductor-skills --all' post-publish)"
  NPX_HOME="$SANDBOX/npx-home"
  mkdir -p "$NPX_HOME"

  # Seed with stale state — exactly what an existing user would have
  mkdir -p "$NPX_HOME/.claude/skills/conductor"
  echo "stale legacy" > "$NPX_HOME/.claude/skills/conductor/SKILL.md"
  mkdir -p "$NPX_HOME/.claude/plugins/cache/conductor-skills/conductor/1.0.0"
  echo "old cache" > "$NPX_HOME/.claude/plugins/cache/conductor-skills/conductor/1.0.0/marker.txt"
  cat > "$NPX_HOME/.claude/settings.json" <<'EOF'
{
  "model": "opus[1m]",
  "enabledPlugins": { "unrelated@marketplace": true }
}
EOF

  HOME="$NPX_HOME" npx --yes --package="$TARBALL" conductor-skills --all \
    >"$SANDBOX/npx-all.log" 2>&1
  assert "npx invocation exits 0" "[ \$? -eq 0 ]"
  assert "npx invocation: --version reports $PKG_VERSION" \
    "HOME='$NPX_HOME' npx --yes --package='$TARBALL' conductor-skills --version 2>/dev/null | tr -d '[:space:]' | grep -qx '$PKG_VERSION'"
  assert "npx invocation: claude was configured (settings.json updated)" \
    "grep -q 'conductor@conductor-skills' '$NPX_HOME/.claude/settings.json'"
  assert "npx invocation: skill dir overwritten with fresh content (not stale stub)" \
    "[ -f '$NPX_HOME/.claude/skills/conductor/SKILL.md' ] && ! grep -q 'stale legacy' '$NPX_HOME/.claude/skills/conductor/SKILL.md'"
  assert "npx invocation: stale plugin cache cleaned" \
    "[ ! -d '$NPX_HOME/.claude/plugins/cache/conductor-skills' ]"
  assert "npx invocation: pre-existing unrelated plugin preserved" \
    "grep -q 'unrelated@marketplace' '$NPX_HOME/.claude/settings.json'"
  assert "npx invocation: pre-existing model preserved" \
    "grep -q 'opus\\[1m\\]' '$NPX_HOME/.claude/settings.json'"
  assert "npx invocation: manifest tracks the install" \
    "[ -f '$NPX_HOME/.conductor-skills/manifest.json' ]"
  assert "npx invocation: restart-required messaging is shown" \
    "grep -q 'ACTION REQUIRED' '$SANDBOX/npx-all.log'"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. End-user fidelity — `npm install -g` from the tarball, then run the bin
# ─────────────────────────────────────────────────────────────────────────────
if [ "$QUICK" = "true" ]; then
  step "Skipping end-user fidelity smoke test (--quick)"
else
  step "End-user fidelity (npm install -g from tarball)"
  USER_HOME="$SANDBOX/user-home"
  PREFIX="$SANDBOX/npm-prefix"
  mkdir -p "$USER_HOME" "$PREFIX"
  # Seed ~/.claude so `--all` detects claude via the directory fallback rather
  # than relying on a `claude` binary being on the host PATH. Without this the
  # smoke test only passes on machines where the Claude CLI is installed.
  mkdir -p "$USER_HOME/.claude"

  info "npm install -g --prefix=$PREFIX $TARBALL_NAME"
  npm install -g --prefix="$PREFIX" "$TARBALL" >"$SANDBOX/npm-install.log" 2>&1
  assert "npm install -g succeeded" "[ \$? -eq 0 ]"
  assert "conductor-skills binary installed" "[ -x '$PREFIX/bin/conductor-skills' ]"

  # Run the installed binary exactly as a published user would
  out=$(HOME="$USER_HOME" PATH="$PREFIX/bin:$PATH" conductor-skills --version 2>&1)
  assert "binary --version reports $PKG_VERSION (got: $out)" "[ '$out' = '$PKG_VERSION' ]"

  HOME="$USER_HOME" PATH="$PREFIX/bin:$PATH" conductor-skills --all >"$SANDBOX/conductor-all.log" 2>&1
  assert "conductor-skills --all completed" "[ \$? -eq 0 ]"
  assert "--all installed claude settings.json"  "[ -f '$USER_HOME/.claude/settings.json' ]"
  assert "--all wrote enabledPlugins" "grep -q 'conductor@conductor-skills' '$USER_HOME/.claude/settings.json'"
  assert "--all wrote extraKnownMarketplaces" "grep -q 'conductor-skills' '$USER_HOME/.claude/settings.json'"
  assert "--all wrote manifest" "[ -f '$USER_HOME/.conductor-skills/manifest.json' ]"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "═════════════════════════════════════════════════════════════"
TOTAL=$((PASS+FAIL))
if [ $FAIL -eq 0 ]; then
  printf "${GREEN}${BOLD}✓ All %d checks passed.${NC} Tarball is ready: ${BOLD}%s${NC}\n" "$TOTAL" "$TARBALL_NAME"
  echo ""
  if [ "$KEEP_SANDBOX" = "true" ]; then
    info "sandbox preserved at: $SANDBOX"
  fi
  echo "Next: ${BOLD}npm publish --access public --dry-run${NC} (one more sanity check)"
  echo "Then: ${BOLD}npm publish --access public${NC}"
  exit 0
else
  printf "${RED}${BOLD}✗ %d of %d checks failed.${NC}\n" "$FAIL" "$TOTAL"
  echo ""
  echo "Failures:"
  for f in "${FAILURES[@]}"; do echo "  - $f"; done
  echo ""
  echo "Sandbox preserved at: $SANDBOX"
  echo "Recent logs:"
  echo "  - $SANDBOX/npm-install.log"
  echo "  - $SANDBOX/conductor-all.log"
  echo "  - $SANDBOX/matrix/<agent>-<mode>/home/last.log"
  exit 1
fi
