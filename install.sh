#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Conductor Skills Installer
# Installs Conductor workflow orchestration skills for your AI coding agent.
# https://github.com/conductor-oss/conductor-skills
# ─────────────────────────────────────────────────────────────────────────────

VERSION="1.6.4"
# Per-file fetches and the upgrade-check both read from `main`. Releases are
# rolled by bumping VERSION on main, not by tagging — the install scripts ride
# along with whatever main is serving.
REPO_BASE="https://raw.githubusercontent.com/conductor-oss/conductor-skills/main"

# When set, skip the network fetch and copy from this directory instead.
# The npm package sets this so the bundled files are used.
LOCAL_DIR="${CONDUCTOR_SKILLS_LOCAL_DIR:-}"

# Files to ship to non-Claude agents (Claude uses the marketplace flow).
SKILL_FILES=(
  "skills/conductor/SKILL.md"
  "skills/conductor/references/setup.md"
  "skills/conductor/references/cli-index.md"
  "skills/conductor/references/fallback-cli.md"
  "skills/conductor/references/workflow-definition.md"
  "skills/conductor/references/workers.md"
  "skills/conductor/references/api-reference.md"
  "skills/conductor/references/visualization.md"
  "skills/conductor/references/schedules.md"
  "skills/conductor/references/orkes.md"
  "skills/conductor/references/optimization.md"
  "skills/conductor/references/troubleshooting.md"
  "skills/conductor/examples/create-and-run-workflow.md"
  "skills/conductor/examples/monitor-and-retry.md"
  "skills/conductor/examples/signal-wait-task.md"
  "skills/conductor/examples/fork-join.md"
  "skills/conductor/examples/do-while-loop.md"
  "skills/conductor/examples/sub-workflow.md"
  "skills/conductor/examples/review-workflow.md"
  "skills/conductor/examples/llm-chat.md"
  "skills/conductor/examples/ai-agent-mcp.md"
  "skills/conductor/examples/ai-agent-loop.md"
  "skills/conductor/examples/llm-rag.md"
  "skills/conductor/examples/workflows/weather-notification.json"
  "skills/conductor/examples/workflows/fork-join.json"
  "skills/conductor/examples/workflows/do-while-loop.json"
  "skills/conductor/examples/workflows/child-normalize.json"
  "skills/conductor/examples/workflows/parent-pipeline.json"
  "skills/conductor/examples/workflows/llm-chat.json"
  "skills/conductor/examples/workflows/ai-agent-mcp.json"
  "skills/conductor/examples/workflows/ai-agent-loop.json"
  "skills/conductor/examples/workflows/llm-rag.json"
  "skills/conductor/scripts/conductor_api.py"
)

# Colors (if terminal supports them)
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

info()  { echo -e "${BLUE}[info]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*" >&2; }

usage() {
  cat <<EOF
${BOLD}Conductor Skills Installer v${VERSION}${NC}

Usage:
  install.sh [--agent <name> | --all] [--global] [--project-dir <path>]
             [--upgrade] [--check] [--force] [--uninstall]

Options:
  --agent <name>        Install for a specific agent
  --all                 Auto-detect all agents and install for each
  --global              Install globally (available in all projects)
  --project-dir <path>  Target project directory (default: current directory)
  --upgrade             Check for newer version and upgrade installed agents
  --check               Dry run — show what would be installed, no changes
  --force               Overwrite existing files without prompting
  --uninstall           Remove installed skill files
  --version             Print version and exit
  --help                Show this help message

Supported agents:
  claude      Claude Code (Anthropic)
  codex       Codex CLI (OpenAI)
  gemini      Gemini CLI (Google)
  cursor      Cursor
  windsurf    Windsurf (Codeium)
  cline       Cline
  aider       Aider
  copilot     GitHub Copilot
  amazonq     Amazon Q Developer
  opencode    OpenCode
  roo         Roo Code
  amp         Amp

Examples:
  # Auto-detect and install for all agents
  install.sh --all

  # Install globally for Codex CLI
  install.sh --agent codex --global

  # Check what would be installed
  install.sh --all --check

  # Upgrade all installed agents to latest
  install.sh --all --upgrade

  # Uninstall from all agents
  install.sh --all --uninstall

EOF
  exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Agent detection
# ─────────────────────────────────────────────────────────────────────────────

detect_agents() {
  local detected=()

  command -v claude &>/dev/null && detected+=(claude)
  { command -v codex &>/dev/null || [ -d "$HOME/.codex" ]; } && detected+=(codex)
  { command -v gemini &>/dev/null || [ -d "$HOME/.gemini" ]; } && detected+=(gemini)
  [ -d "$HOME/.cursor" ] && detected+=(cursor)
  [ -d "$HOME/.codeium" ] && detected+=(windsurf)
  [ -d "$HOME/.cline" ] && detected+=(cline)
  command -v aider &>/dev/null && detected+=(aider)
  [ -d "$HOME/.config/github-copilot" ] && detected+=(copilot)
  { command -v q &>/dev/null || [ -d "$HOME/.amazonq" ]; } && detected+=(amazonq)
  command -v opencode &>/dev/null && detected+=(opencode)
  [ -d "$HOME/.roo" ] && detected+=(roo)
  { command -v amp &>/dev/null || [ -d "$HOME/.config/amp" ]; } && detected+=(amp)

  echo "${detected[@]}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Manifest tracking
# ─────────────────────────────────────────────────────────────────────────────

GLOBAL_MANIFEST="$HOME/.conductor-skills/manifest.json"

get_manifest_path() {
  local is_global="$1"
  local project_dir="${2:-.}"
  if [ "$is_global" = "true" ]; then
    echo "$GLOBAL_MANIFEST"
  else
    echo "$project_dir/.conductor-skills/manifest.json"
  fi
}

ensure_manifest() {
  local manifest="$1"
  local dir
  dir=$(dirname "$manifest")
  mkdir -p "$dir"
  if [ ! -f "$manifest" ]; then
    echo '{"schema_version":1,"installations":{}}' > "$manifest"
  fi
}

read_manifest_version() {
  local manifest="$1"
  local agent="$2"

  if [ ! -f "$manifest" ]; then
    echo ""
    return
  fi

  python3 -c "
import json, sys
try:
    m = json.load(open('$manifest'))
    print(m.get('installations',{}).get('$agent',{}).get('version',''))
except: pass
" 2>/dev/null || echo ""
}

write_manifest_entry() {
  local manifest="$1"
  local agent="$2"
  local ver="$3"
  local mode="$4"
  local target_path="$5"

  ensure_manifest "$manifest"

  python3 -c "
import json, datetime
m = json.load(open('$manifest'))
now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
entry = m.setdefault('installations',{}).get('$agent',{})
m['installations']['$agent'] = {
    'version': '$ver',
    'installed_at': entry.get('installed_at', now),
    'updated_at': now,
    'mode': '$mode',
    'target_path': '$target_path'
}
json.dump(m, open('$manifest','w'), indent=2)
" 2>/dev/null
}

remove_manifest_entry() {
  local manifest="$1"
  local agent="$2"

  if [ ! -f "$manifest" ]; then
    return
  fi

  python3 -c "
import json
m = json.load(open('$manifest'))
m.get('installations',{}).pop('$agent', None)
json.dump(m, open('$manifest','w'), indent=2)
" 2>/dev/null
}

list_manifest_agents() {
  local manifest="$1"

  if [ ! -f "$manifest" ]; then
    echo ""
    return
  fi

  python3 -c "
import json
try:
    m = json.load(open('$manifest'))
    agents = list(m.get('installations',{}).keys())
    print(' '.join(agents))
except: pass
" 2>/dev/null || echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Remote version check
# ─────────────────────────────────────────────────────────────────────────────

fetch_remote_version() {
  if [ -n "$LOCAL_DIR" ] && [ -f "$LOCAL_DIR/VERSION" ]; then
    cat "$LOCAL_DIR/VERSION" | tr -d '[:space:]'
    return
  fi
  local remote_ver
  remote_ver=$(curl -sSfL "$REPO_BASE/VERSION" 2>/dev/null | tr -d '[:space:]') || true
  echo "$remote_ver"
}

# ─────────────────────────────────────────────────────────────────────────────
# Download & assembly
# ─────────────────────────────────────────────────────────────────────────────

download_files() {
  local tmp_dir="$1"

  if [ -n "$LOCAL_DIR" ]; then
    if [ ! -d "$LOCAL_DIR" ]; then
      error "CONDUCTOR_SKILLS_LOCAL_DIR=$LOCAL_DIR is not a directory"
      exit 1
    fi
    info "Copying skill files from $LOCAL_DIR..."
    for file in "${SKILL_FILES[@]}"; do
      local src="$LOCAL_DIR/$file"
      local dest="$tmp_dir/$file"
      if [ ! -f "$src" ]; then
        error "Missing file in local source: $file"
        # tmp_dir cleanup handled by EXIT trap
        exit 1
      fi
      mkdir -p "$(dirname "$dest")"
      cp "$src" "$dest"
    done
    ok "Copied ${#SKILL_FILES[@]} files"
    return
  fi

  info "Downloading skill files..."
  for file in "${SKILL_FILES[@]}"; do
    local dir
    dir=$(dirname "$file")
    mkdir -p "$tmp_dir/$dir"
    if ! curl -sSfL "$REPO_BASE/$file" -o "$tmp_dir/$file" 2>/dev/null; then
      local http_code
      http_code=$(curl -sS -o /dev/null -w "%{http_code}" "$REPO_BASE/$file" 2>/dev/null || echo "?")
      error "Failed to download $file (HTTP $http_code from $REPO_BASE)"
      if [ "$http_code" = "404" ]; then
        error "File is missing upstream — likely a release packaging bug."
        error "Please report: https://github.com/conductor-oss/conductor-skills/issues"
      else
        error "Check your internet connection and try again."
      fi
      # tmp_dir cleanup handled by EXIT trap
      exit 1
    fi
  done
  ok "Downloaded ${#SKILL_FILES[@]} files"
}

assemble_content() {
  local tmp_dir="$1"
  local output="$2"

  {
    cat "$tmp_dir/skills/conductor/SKILL.md"
    echo ""
    echo "---"
    echo ""
    echo "# References"
    echo ""
    for f in "$tmp_dir"/skills/conductor/references/*.md; do
      cat "$f"
      echo ""
      echo "---"
      echo ""
    done
    echo "# Examples"
    echo ""
    for f in "$tmp_dir"/skills/conductor/examples/*.md; do
      cat "$f"
      echo ""
      echo "---"
      echo ""
    done
  } > "$output"
}

# ─────────────────────────────────────────────────────────────────────────────
# Safe file writing (respects --force)
# ─────────────────────────────────────────────────────────────────────────────

safe_write() {
  local target="$1"
  local source="$2"
  local force="$3"

  if [ -f "$target" ] && [ "$force" != "true" ]; then
    warn "File already exists: $target"
    printf "  Overwrite? [y/N] "
    read -r answer
    if [[ ! "$answer" =~ ^[Yy] ]]; then
      info "Skipped. Use --force to overwrite."
      return 1
    fi
  fi

  local dir
  dir=$(dirname "$target")
  mkdir -p "$dir"
  cp "$source" "$target"
  ok "Installed: $target"
}

# ─────────────────────────────────────────────────────────────────────────────
# Global install paths
# ─────────────────────────────────────────────────────────────────────────────

supports_global() {
  local agent="$1"
  case "$agent" in
    claude|codex|gemini|cursor|windsurf|roo|amp|aider|opencode) return 0 ;;
    *) return 1 ;;
  esac
}

get_global_path() {
  local agent="$1"
  case "$agent" in
    claude)   echo "$HOME/.claude/settings.json" ;;
    codex)    echo "${CODEX_HOME:-$HOME/.codex}/AGENTS.md" ;;
    cursor)   echo "$HOME/.cursor/skills/conductor/SKILL.md" ;;
    gemini)   echo "$HOME/.gemini/GEMINI.md" ;;
    windsurf) echo "$HOME/.codeium/windsurf/memories/global_rules.md" ;;
    roo)      echo "$HOME/.roo/rules/conductor.md" ;;
    amp)      echo "$HOME/.config/AGENTS.md" ;;
    aider)    echo "$HOME/.aider.conf.yml" ;;
    opencode) echo "$HOME/.config/opencode/skills/conductor/SKILL.md" ;;
  esac
}

get_target_path() {
  local agent="$1"
  local project_dir="$2"

  case "$agent" in
    claude)   echo "$project_dir/.claude/settings.json" ;;
    codex)    echo "$project_dir/AGENTS.md" ;;
    gemini)   echo "$project_dir/GEMINI.md" ;;
    cursor)   echo "$project_dir/.cursor/rules/conductor.mdc" ;;
    windsurf) echo "$project_dir/.windsurfrules" ;;
    cline)    echo "$project_dir/.clinerules" ;;
    aider)    echo "$project_dir/.conductor-skills" ;;
    copilot)  echo "$project_dir/.github/copilot-instructions.md" ;;
    amazonq)  echo "$project_dir/.amazonq/rules/conductor.md" ;;
    opencode) echo "$project_dir/AGENTS.md" ;;
    roo)      echo "$project_dir/.roo/rules/conductor.md" ;;
    amp)      echo "$project_dir/.amp/instructions.md" ;;
  esac
}

# ─────────────────────────────────────────────────────────────────────────────
# Per-agent install logic
# ─────────────────────────────────────────────────────────────────────────────

# Bust plugin caches so existing Claude installs actually pick up new content.
# Note: we do NOT delete ~/.claude/skills/conductor — that's the user-skill
# install location, populated by install_claude_skill below. We *overwrite*
# it with fresh content on each install instead.
clean_claude_legacy_and_caches() {
  local cache="$HOME/.claude/plugins/cache/conductor-skills"
  local market="$HOME/.claude/plugins/marketplaces/conductor-skills"
  local registry="$HOME/.claude/plugins/installed_plugins.json"

  if [ -d "$cache" ]; then
    rm -rf "$cache"
    ok "Cleared plugin cache: $cache (will re-fetch on next session)"
  fi
  if [ -d "$market" ]; then
    rm -rf "$market"
    ok "Cleared marketplace clone: $market (will re-clone on next session)"
  fi

  # Surgically remove our entry from Claude's plugin registry — if we leave
  # a stale "installed at v1.0.0" record pointing to a now-deleted cache dir,
  # Claude Code may skip re-fetching on next session start.
  if [ -f "$registry" ]; then
    if python3 - "$registry" <<'PY' 2>/dev/null
import json, os, sys
path = sys.argv[1]
with open(path) as f:
    r = json.load(f)
plugins = r.get('plugins') or {}
if 'conductor@conductor-skills' not in plugins:
    sys.exit(2)  # nothing to do
plugins.pop('conductor@conductor-skills')
tmp = path + '.tmp'
with open(tmp, 'w') as f:
    json.dump(r, f, indent=2)
    f.write('\n')
os.replace(tmp, path)
PY
    then
      ok "Cleared stale registry entry in $registry"
    fi
  fi
}

# Install Conductor as a user-skill at ~/.claude/skills/conductor — the
# "good old" skill location that's visible to the user immediately and
# auto-loaded by Claude Code at session start (no marketplace fetch needed).
# Source files come from $tmp_dir (downloaded from GitHub) or $LOCAL_DIR
# (bundled with the npm package).
install_claude_skill() {
  local tmp_dir="$1"
  local skill_dest="$HOME/.claude/skills/conductor"
  local src_dir

  if [ -n "$LOCAL_DIR" ]; then
    src_dir="$LOCAL_DIR/skills/conductor"
  else
    src_dir="$tmp_dir/skills/conductor"
  fi

  if [ ! -d "$src_dir" ]; then
    error "Skill source not found at $src_dir"
    return 1
  fi

  mkdir -p "$skill_dest"
  # Mirror the skill contents — replace, don't merge, so removed files vanish.
  rm -rf "$skill_dest"
  mkdir -p "$skill_dest"
  cp -R "$src_dir/." "$skill_dest/"
  ok "Installed skill files: $skill_dest"
}

install_claude() {
  # Dual install for Claude Code:
  #   1. Plugin via settings.json (slash commands, auto-updates from marketplace)
  #   2. User skill at ~/.claude/skills/conductor (visible files, immediate)
  # Both coexist — Claude Code dedupes on skill name at load time.
  local is_global="$1"
  local project_dir="$2"
  local tmp_dir="$3"
  local settings_path

  if [ "$is_global" = "true" ]; then
    settings_path="$HOME/.claude/settings.json"
  else
    settings_path="$project_dir/.claude/settings.json"
  fi

  mkdir -p "$(dirname "$settings_path")"

  clean_claude_legacy_and_caches

  install_claude_skill "$tmp_dir"

  info "Enabling Conductor plugin in $settings_path ..."
  if ! python3 - "$settings_path" <<'PY'
import json, os, sys
path = sys.argv[1]
try:
    with open(path) as f:
        s = json.load(f)
except FileNotFoundError:
    s = {}
except json.JSONDecodeError as e:
    print(f"error: {path} is not valid JSON: {e}", file=sys.stderr)
    sys.exit(1)

mkts = s.setdefault('extraKnownMarketplaces', {})
mkts['conductor-skills'] = {
    'source': {'source': 'github', 'repo': 'conductor-oss/conductor-skills'}
}
enabled = s.setdefault('enabledPlugins', {})
enabled['conductor@conductor-skills'] = True

tmp = path + '.tmp'
with open(tmp, 'w') as f:
    json.dump(s, f, indent=2)
    f.write('\n')
os.replace(tmp, path)
PY
  then
    error "Failed to update $settings_path"
    return 1
  fi

  ok "Configured: $settings_path"
  echo ""
  echo -e "${GREEN}${BOLD}Conductor installed two ways:${NC}"
  echo ""
  echo "  1. ${BOLD}Skill${NC} at ~/.claude/skills/conductor/"
  echo "     Files are there NOW. Skill auto-loads on next session start."
  echo ""
  echo "  2. ${BOLD}Plugin${NC} via settings.json (extraKnownMarketplaces + enabledPlugins)"
  echo "     Claude Code fetches plugin v${VERSION} on next session start."
  echo "     Provides slash commands: /conductor, /conductor-setup, /conductor-optimize, /conductor-scaffold-worker"
  echo ""
  echo -e "${YELLOW}${BOLD}⚠ Restart Claude Code to activate.${NC}"
  echo "    • claude CLI:           exit (Ctrl+D) and start a new session"
  echo "    • VS Code extension:    Cmd+Shift+P → \"Reload Window\""
  echo "    • Desktop app:          quit and reopen"
  echo ""
  echo "  Verify after restart:"
  echo "    ls ~/.claude/skills/conductor/                                   # skill files"
  echo "    ls ~/.claude/plugins/cache/conductor-skills/conductor/${VERSION}/  # plugin files"
}

install_to_file() {
  local target="$1"
  local assembled="$2"
  local force="$3"
  local prefix="${4:-}"

  if [ -n "$prefix" ]; then
    local tmp_with_prefix
    tmp_with_prefix=$(mktemp)
    {
      echo "$prefix"
      cat "$assembled"
    } > "$tmp_with_prefix"
    local rv=0
    safe_write "$target" "$tmp_with_prefix" "$force" || rv=$?
    rm -f "$tmp_with_prefix"
    return $rv
  else
    safe_write "$target" "$assembled" "$force"
  fi
}

install_aider_to_dir() {
  local skill_dir="$1"
  local tmp_dir="$2"
  local config="$3"
  local read_prefix="$4"

  mkdir -p "$skill_dir/references" "$skill_dir/examples" "$skill_dir/scripts"

  info "Copying skill files to $skill_dir ..."
  cp "$tmp_dir/skills/conductor/SKILL.md" "$skill_dir/"
  for f in "$tmp_dir"/skills/conductor/references/*.md; do
    cp "$f" "$skill_dir/references/"
  done
  for f in "$tmp_dir"/skills/conductor/examples/*.md; do
    cp "$f" "$skill_dir/examples/"
  done
  for f in "$tmp_dir"/skills/conductor/scripts/*.py; do
    [ -f "$f" ] && cp "$f" "$skill_dir/scripts/"
  done
  ok "Files copied to $skill_dir"

  if [ -f "$config" ] && grep -q "conductor-skills" "$config" 2>/dev/null; then
    info "Aider config already references conductor-skills, skipping."
  else
    info "Adding read entries to $config ..."
    {
      echo ""
      echo "# Conductor Skills"
      echo "read:"
      for file in "${SKILL_FILES[@]}"; do
        echo "  - ${read_prefix}${file#skills/conductor/}"
      done
    } >> "$config"
    ok "Updated: $config"
  fi
}

# Install a single agent. Returns 0 on success, 1 on skip/failure.
install_for_agent() {
  local agent="$1"
  local project_dir="$2"
  local is_global="$3"
  local force="$4"
  local tmp_dir="$5"
  local assembled="$6"

  # Claude has its own install path (writes to settings.json + skill dir)
  if [ "$agent" = "claude" ]; then
    install_claude "$is_global" "$project_dir" "$tmp_dir"
    return $?
  fi

  if [ "$is_global" = "true" ]; then
    local target_path
    target_path=$(get_global_path "$agent")

    if [ "$agent" = "aider" ]; then
      install_aider_to_dir "$HOME/.conductor-skills" "$tmp_dir" "$HOME/.aider.conf.yml" "$HOME/.conductor-skills/"
    else
      install_to_file "$target_path" "$assembled" "$force"
    fi
  else
    case "$agent" in
      codex)
        install_to_file "$project_dir/AGENTS.md" "$assembled" "$force"
        ;;
      gemini)
        install_to_file "$project_dir/GEMINI.md" "$assembled" "$force"
        ;;
      cursor)
        local frontmatter
        frontmatter=$(cat <<'FRONT'
---
description: Conductor workflow orchestration - create, run, monitor, and manage workflows
globs: "**/*"
alwaysApply: true
---

FRONT
)
        install_to_file "$project_dir/.cursor/rules/conductor.mdc" "$assembled" "$force" "$frontmatter"
        ;;
      windsurf)
        install_to_file "$project_dir/.windsurfrules" "$assembled" "$force"
        ;;
      cline)
        install_to_file "$project_dir/.clinerules" "$assembled" "$force"
        ;;
      aider)
        install_aider_to_dir "$project_dir/.conductor-skills" "$tmp_dir" "$project_dir/.aider.conf.yml" ".conductor-skills/"
        ;;
      copilot)
        install_to_file "$project_dir/.github/copilot-instructions.md" "$assembled" "$force"
        ;;
      amazonq)
        install_to_file "$project_dir/.amazonq/rules/conductor.md" "$assembled" "$force"
        ;;
      opencode)
        install_to_file "$project_dir/AGENTS.md" "$assembled" "$force"
        ;;
      roo)
        install_to_file "$project_dir/.roo/rules/conductor.md" "$assembled" "$force"
        ;;
      amp)
        install_to_file "$project_dir/.amp/instructions.md" "$assembled" "$force"
        ;;
    esac
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Uninstall
# ─────────────────────────────────────────────────────────────────────────────

uninstall_agent() {
  local agent="$1"
  local project_dir="$2"
  local is_global="$3"

  if [ "$agent" = "claude" ]; then
    local settings_path
    if [ "$is_global" = "true" ]; then
      settings_path="$HOME/.claude/settings.json"
    else
      settings_path="$project_dir/.claude/settings.json"
    fi
    if [ ! -f "$settings_path" ]; then
      warn "Nothing to uninstall: $settings_path not found"
      return
    fi
    if python3 - "$settings_path" <<'PY'
import json, os, sys
path = sys.argv[1]
with open(path) as f:
    s = json.load(f)
changed = False
mkts = s.get('extraKnownMarketplaces') or {}
if 'conductor-skills' in mkts:
    mkts.pop('conductor-skills')
    if not mkts:
        s.pop('extraKnownMarketplaces', None)
    changed = True
enabled = s.get('enabledPlugins') or {}
if 'conductor@conductor-skills' in enabled:
    enabled.pop('conductor@conductor-skills')
    if not enabled:
        s.pop('enabledPlugins', None)
    changed = True
if changed:
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(s, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)
PY
    then
      ok "Removed Conductor entries from $settings_path"
      # Also remove the user-skill copy
      if [ -d "$HOME/.claude/skills/conductor" ]; then
        rm -rf "$HOME/.claude/skills/conductor"
        ok "Removed skill dir: $HOME/.claude/skills/conductor"
      fi
      clean_claude_legacy_and_caches
    else
      error "Failed to update $settings_path"
    fi
    return
  fi

  local target
  if [ "$is_global" = "true" ]; then
    if [ "$agent" = "aider" ]; then
      local skill_dir="$HOME/.conductor-skills"
      if [ -d "$skill_dir" ]; then
        rm -rf "$skill_dir"
        ok "Removed: $skill_dir"
        info "Note: You may also want to remove the 'read:' entries from ~/.aider.conf.yml"
      else
        warn "Nothing to uninstall: $skill_dir not found"
      fi
      return
    fi
    target=$(get_global_path "$agent")
  else
    target=$(get_target_path "$agent" "$project_dir")
    if [ "$agent" = "aider" ]; then
      if [ -d "$target" ]; then
        rm -rf "$target"
        ok "Removed: $target"
        info "Note: You may also want to remove the 'read:' entries from .aider.conf.yml"
      else
        warn "Nothing to uninstall: $target not found"
      fi
      return
    fi
  fi

  if [ -f "$target" ]; then
    rm -f "$target"
    ok "Removed: $target"
  else
    warn "Nothing to uninstall: $target not found"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Check mode (dry run)
# ─────────────────────────────────────────────────────────────────────────────

do_check() {
  local agents=("$@")

  local manifest
  manifest=$(get_manifest_path "true" "")

  echo ""
  echo -e "${BOLD}Detected agents:${NC}"
  if [ ${#agents[@]} -eq 0 ]; then
    warn "No AI coding agents detected on this system."
    return
  fi

  for agent in "${agents[@]}"; do
    local installed_ver
    installed_ver=$(read_manifest_version "$manifest" "$agent")
    local global_support="yes"
    supports_global "$agent" || global_support="no"

    if [ -n "$installed_ver" ]; then
      if [ "$installed_ver" = "$VERSION" ]; then
        echo -e "  ${GREEN}●${NC} $agent  v${installed_ver} (up to date)"
      else
        echo -e "  ${YELLOW}●${NC} $agent  v${installed_ver} → v${VERSION} (upgrade available)"
      fi
    else
      echo -e "  ${BLUE}●${NC} $agent  (not installed)  global: $global_support"
    fi
  done
  echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

main() {
  local agent=""
  local project_dir="."
  local force="false"
  local uninstall="false"
  local global="false"
  local all="false"
  local upgrade="false"
  local check="false"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent)       agent="$2"; shift 2 ;;
      --project-dir) project_dir="$2"; shift 2 ;;
      --global)      global="true"; shift ;;
      --all)         all="true"; shift ;;
      --upgrade)     upgrade="true"; shift ;;
      --check)       check="true"; shift ;;
      --force)       force="true"; shift ;;
      --uninstall)   uninstall="true"; shift ;;
      --version)     echo "v${VERSION}"; exit 0 ;;
      --help|-h)     usage ;;
      *)             error "Unknown option: $1"; usage ;;
    esac
  done

  # Require --agent or --all
  if [ -z "$agent" ] && [ "$all" != "true" ]; then
    error "Missing required --agent flag (or use --all)"
    echo ""
    usage
  fi

  # Resolve project dir to absolute path
  project_dir=$(cd "$project_dir" && pwd)

  echo ""
  echo -e "${BOLD}Conductor Skills Installer v${VERSION}${NC}"
  echo ""

  # Build agent list
  local agents=()
  if [ "$all" = "true" ]; then
    local detected
    detected=$(detect_agents)
    if [ -z "$detected" ]; then
      warn "No AI coding agents detected on this system."
      echo ""
      info "Supported agents: claude, codex, gemini, cursor, windsurf, cline,"
      info "  aider, copilot, amazonq, opencode, roo, amp"
      echo ""
      info "Install one of the above, then re-run this command."
      exit 0
    fi
    # shellcheck disable=SC2206
    agents=($detected)
    info "Detected agents: ${agents[*]}"
    echo ""
  else
    agent=$(echo "$agent" | tr '[:upper:]' '[:lower:]')
    case "$agent" in
      claude|codex|gemini|cursor|windsurf|cline|aider|copilot|amazonq|opencode|roo|amp) ;;
      *) error "Unknown agent: $agent"; echo ""; usage ;;
    esac
    agents=("$agent")
  fi

  # Check mode — dry run
  if [ "$check" = "true" ]; then
    do_check "${agents[@]}"
    exit 0
  fi

  # Determine manifest path
  local manifest
  if [ "$global" = "true" ] || [ "$all" = "true" ]; then
    manifest=$(get_manifest_path "true" "")
  else
    manifest=$(get_manifest_path "false" "$project_dir")
  fi

  # Handle uninstall
  if [ "$uninstall" = "true" ]; then
    for a in "${agents[@]}"; do
      local use_global="$global"
      if [ "$all" = "true" ] && supports_global "$a"; then
        use_global="true"
      fi
      info "Uninstalling ${BOLD}${a}${NC} ..."
      uninstall_agent "$a" "$project_dir" "$use_global"
      remove_manifest_entry "$manifest" "$a"
    done
    echo ""
    ok "Done!"
    return
  fi

  # Check for upgrade
  local target_version="$VERSION"
  if [ "$upgrade" = "true" ]; then
    info "Checking for updates..."
    local remote_ver
    remote_ver=$(fetch_remote_version)
    if [ -z "$remote_ver" ]; then
      warn "Could not check for updates (offline?). Using bundled v${VERSION}."
    elif [ "$remote_ver" != "$VERSION" ]; then
      info "Update available: v${VERSION} → v${remote_ver}"
      target_version="$remote_ver"
    else
      info "Already at latest version (v${VERSION})."
    fi
    echo ""
  fi

  # Download files to temp dir (not local — the EXIT trap must access it after main returns)
  tmp_dir=$(mktemp -d)
  trap 'rm -rf "$tmp_dir"' EXIT

  download_files "$tmp_dir"

  # Assemble into single file
  local assembled="$tmp_dir/_assembled.md"
  assemble_content "$tmp_dir" "$assembled"
  ok "Assembled skill content ($(wc -c < "$assembled" | tr -d ' ') bytes)"

  # Install for each agent
  local installed_count=0
  local skipped_count=0

  for a in "${agents[@]}"; do
    echo ""

    # Determine if global for this agent
    local use_global="$global"
    if [ "$all" = "true" ]; then
      if supports_global "$a"; then
        use_global="true"
      else
        info "${BOLD}${a}${NC}: skipped (project-only install). Use --project-dir <path> to include."
        skipped_count=$((skipped_count + 1))
        continue
      fi
    fi

    # Validate global support for single-agent mode
    if [ "$use_global" = "true" ] && ! supports_global "$a"; then
      error "Global install is not supported for $a. Run from your project directory instead."
      continue
    fi

    # Idempotency check. --force re-installs anyway; --upgrade does not (matches
    # --check semantics: "already at latest" should be a no-op).
    #
    # Exception: claude always re-runs. Its "installed state" lives in two
    # places — our manifest AND Claude Code's plugin cache. The manifest alone
    # isn't authoritative; the cache can drift (e.g. user installed v1.0.0 via
    # /plugin install, then we publish v1.6.0 — manifest matches but cache is
    # stale). Always re-running the cache bust + settings.json upsert keeps
    # upgrades honest. Cost: ~3 seconds added to next session start.
    local installed_ver
    installed_ver=$(read_manifest_version "$manifest" "$a")
    if [ "$a" != "claude" ] && [ -n "$installed_ver" ] && [ "$installed_ver" = "$target_version" ] && [ "$force" != "true" ]; then
      ok "${a} already at v${installed_ver}, skipping."
      skipped_count=$((skipped_count + 1))
      continue
    fi

    if [ -n "$installed_ver" ] && [ "$installed_ver" != "$target_version" ]; then
      info "Upgrading ${BOLD}${a}${NC} from v${installed_ver} to v${target_version} ..."
    else
      info "Installing for ${BOLD}${a}${NC} ..."
    fi

    # Write-time force semantics:
    #   --force / --upgrade   → always force
    #   manifest shows older  → force (clear upgrade; file is OURS, user
    #     already consented to this install path on the original install).
    # Without the third condition: `bash install.sh --all` against a v1.5.0
    # install silently skipped every file because safe_write's `Overwrite? [y/N]`
    # prompt got an empty answer from non-interactive stdin. That's the
    # 1.5.0→1.6.x upgrade-no-op bug.
    local install_force="$force"
    [ "$upgrade" = "true" ] && install_force="true"
    if [ -n "$installed_ver" ] && [ "$installed_ver" != "$target_version" ]; then
      install_force="true"
    fi

    # Perform install
    if install_for_agent "$a" "$project_dir" "$use_global" "$install_force" "$tmp_dir" "$assembled"; then
      # Determine target path for manifest
      local target_path
      if [ "$use_global" = "true" ]; then
        target_path=$(get_global_path "$a")
      else
        target_path=$(get_target_path "$a" "$project_dir")
      fi
      local mode
      if [ "$use_global" = "true" ]; then mode="global"; else mode="project"; fi
      write_manifest_entry "$manifest" "$a" "$target_version" "$mode" "$target_path"
      installed_count=$((installed_count + 1))
    fi
  done

  echo ""
  echo -e "${GREEN}${BOLD}Done!${NC} ${installed_count} configured, ${skipped_count} skipped (already up to date)."
  echo ""
  echo "Next steps:"
  # If claude was among the agents, the in-place messaging from install_claude
  # already covered the restart instructions. For non-claude agents, just point
  # the user at connecting to their server.
  local agents_str="${agents[*]}"
  if [[ " $agents_str " == *" claude "* ]]; then
    echo "  1. Restart Claude Code to load the plugin (see ACTION REQUIRED above)"
    echo "  2. In the new session, ask your agent to connect to your Conductor server, e.g.:"
  else
    echo "  Ask your agent to connect to your Conductor server, e.g.:"
  fi
  echo ""
  echo '     "Connect to my Conductor server at http://localhost:8080/api"'
  echo ""
  echo -e "  Docs: ${BLUE}https://github.com/conductor-oss/conductor-skills${NC}"
  echo ""
}

main "$@"
