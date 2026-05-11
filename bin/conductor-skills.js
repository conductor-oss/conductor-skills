#!/usr/bin/env node
/*
 * conductor-skills — npm wrapper for the Conductor Skills installer.
 *
 * Detects the platform, then invokes the bundled install.sh (Unix) or
 * install.ps1 (Windows) with CONDUCTOR_SKILLS_LOCAL_DIR pointing at the
 * package root. The shell scripts read that env var and use the bundled
 * files instead of fetching from GitHub.
 */

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const PKG_ROOT = path.resolve(__dirname, '..');
const IS_WINDOWS = process.platform === 'win32';
const args = process.argv.slice(2);

function showHelp() {
  const version = readVersion();
  console.log(`@conductor-oss/conductor-skills v${version}

Install the Conductor Skills for your AI coding agent.

Usage:
  conductor-skills --all                        Install for all detected agents
  conductor-skills --agent <name>               Install for a specific agent
  conductor-skills --all --upgrade              Upgrade all installed agents
  conductor-skills --agent <name> --uninstall   Remove an installation
  conductor-skills --agent <name> --global      Global install (where supported)
  conductor-skills --check                      Dry run — show planned changes
  conductor-skills --version                    Print version
  conductor-skills --help                       This help

Supported agents:
  claude, codex, gemini, cursor, windsurf, cline, aider,
  copilot, amazonq, opencode, roo, amp

Examples:
  npx @conductor-oss/conductor-skills --agent claude
  npx @conductor-oss/conductor-skills --all
  conductor-skills --agent cursor --uninstall

Docs: https://github.com/conductor-oss/conductor-skills
`);
}

function readVersion() {
  try {
    return fs.readFileSync(path.join(PKG_ROOT, 'VERSION'), 'utf8').trim();
  } catch {
    return 'unknown';
  }
}

function runUnix() {
  const sh = path.join(PKG_ROOT, 'install.sh');
  if (!fs.existsSync(sh)) {
    console.error(`error: install.sh not found at ${sh}`);
    process.exit(1);
  }
  const r = spawnSync('bash', [sh, ...args], {
    stdio: 'inherit',
    env: { ...process.env, CONDUCTOR_SKILLS_LOCAL_DIR: PKG_ROOT },
  });
  process.exit(r.status === null ? 1 : r.status);
}

function runWindows() {
  const ps1 = path.join(PKG_ROOT, 'install.ps1');
  if (!fs.existsSync(ps1)) {
    console.error(`error: install.ps1 not found at ${ps1}`);
    process.exit(1);
  }
  // Translate POSIX-style flags ("--agent claude") into PowerShell
  // parameters ("-Agent claude"). Booleans like "--upgrade" become "-Upgrade".
  const psArgs = [];
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a.startsWith('--')) {
      const name = a.slice(2);
      const psName = '-' + name.charAt(0).toUpperCase() + name.slice(1);
      psArgs.push(psName);
    } else {
      psArgs.push(a);
    }
  }
  const r = spawnSync(
    'powershell',
    ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1, ...psArgs],
    {
      stdio: 'inherit',
      env: { ...process.env, CONDUCTOR_SKILLS_LOCAL_DIR: PKG_ROOT },
    }
  );
  process.exit(r.status === null ? 1 : r.status);
}

// Argument parsing — fast paths first.
if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
  showHelp();
  process.exit(0);
}

if (args.includes('--version') || args.includes('-v')) {
  console.log(readVersion());
  process.exit(0);
}

if (IS_WINDOWS) {
  runWindows();
} else {
  runUnix();
}
