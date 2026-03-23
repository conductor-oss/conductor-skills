# ─────────────────────────────────────────────────────────────────────────────
# Conductor Skills Installer (PowerShell)
# Installs Conductor workflow orchestration skills for your AI coding agent.
# https://github.com/conductor-oss/conductor-skills
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$Agent,
    [string]$ProjectDir = ".",
    [switch]$Global,
    [switch]$All,
    [switch]$Upgrade,
    [switch]$Check,
    [switch]$Force,
    [switch]$Uninstall,
    [switch]$Version
)

$ErrorActionPreference = "Stop"

$SCRIPT_VERSION = "1.0.0"
$REPO_BASE = "https://raw.githubusercontent.com/conductor-oss/conductor-skills/main"

$SKILL_FILES = @(
    "skills/conductor/SKILL.md"
    "skills/conductor/references/workflow-definition.md"
    "skills/conductor/references/workers.md"
    "skills/conductor/references/api-reference.md"
    "skills/conductor/examples/create-and-run-workflow.md"
    "skills/conductor/examples/monitor-and-retry.md"
    "skills/conductor/examples/signal-wait-task.md"
    "skills/conductor/scripts/conductor_api.py"
)

$VALID_AGENTS = @("claude","codex","gemini","cursor","windsurf","cline","aider","copilot","amazonq","opencode","roo","amp")
$GLOBAL_AGENTS = @("claude","codex","gemini","cursor","windsurf","roo","amp","aider","opencode")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

function Write-Info  { param([string]$Msg) Write-Host "[info] $Msg" -ForegroundColor Blue }
function Write-Ok    { param([string]$Msg) Write-Host "[ok] $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "[warn] $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "[error] $Msg" -ForegroundColor Red }

# ─────────────────────────────────────────────────────────────────────────────
# Agent detection
# ─────────────────────────────────────────────────────────────────────────────

function Detect-Agents {
    $detected = @()
    $home = $env:USERPROFILE

    if (Get-Command claude -ErrorAction SilentlyContinue) { $detected += "claude" }
    if ((Get-Command codex -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $home ".codex"))) { $detected += "codex" }
    if ((Get-Command gemini -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $home ".gemini"))) { $detected += "gemini" }
    if (Test-Path (Join-Path $home ".cursor")) { $detected += "cursor" }
    if (Test-Path (Join-Path $home ".codeium")) { $detected += "windsurf" }
    if (Test-Path (Join-Path $home ".cline")) { $detected += "cline" }
    if (Get-Command aider -ErrorAction SilentlyContinue) { $detected += "aider" }
    if (Test-Path (Join-Path $home ".config\github-copilot")) { $detected += "copilot" }
    if ((Get-Command q -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $home ".amazonq"))) { $detected += "amazonq" }
    if (Get-Command opencode -ErrorAction SilentlyContinue) { $detected += "opencode" }
    if (Test-Path (Join-Path $home ".roo")) { $detected += "roo" }
    if ((Get-Command amp -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $home ".config\amp"))) { $detected += "amp" }

    return $detected
}

# ─────────────────────────────────────────────────────────────────────────────
# Manifest tracking
# ─────────────────────────────────────────────────────────────────────────────

$GLOBAL_MANIFEST = Join-Path $env:USERPROFILE ".conductor-skills\manifest.json"

function Get-ManifestPath {
    param([bool]$IsGlobal, [string]$ProjDir = ".")
    if ($IsGlobal) { return $GLOBAL_MANIFEST }
    return Join-Path $ProjDir ".conductor-skills\manifest.json"
}

function Ensure-Manifest {
    param([string]$ManifestPath)
    $dir = Split-Path -Parent $ManifestPath
    if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    if (!(Test-Path $ManifestPath)) {
        '{"schema_version":1,"installations":{}}' | Set-Content -Path $ManifestPath
    }
}

function Read-ManifestVersion {
    param([string]$ManifestPath, [string]$AgentName)
    if (!(Test-Path $ManifestPath)) { return "" }
    try {
        $m = Get-Content $ManifestPath -Raw | ConvertFrom-Json
        $entry = $m.installations.PSObject.Properties | Where-Object { $_.Name -eq $AgentName }
        if ($entry) { return $entry.Value.version }
    } catch {}
    return ""
}

function Write-ManifestEntry {
    param([string]$ManifestPath, [string]$AgentName, [string]$Ver, [string]$Mode, [string]$TargetPath)
    Ensure-Manifest -ManifestPath $ManifestPath
    $m = Get-Content $ManifestPath -Raw | ConvertFrom-Json
    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    $existingEntry = $m.installations.PSObject.Properties | Where-Object { $_.Name -eq $AgentName }
    $installedAt = $now
    if ($existingEntry) { $installedAt = $existingEntry.Value.installed_at }

    $entry = [PSCustomObject]@{
        version = $Ver
        installed_at = $installedAt
        updated_at = $now
        mode = $Mode
        target_path = $TargetPath
    }

    if ($existingEntry) {
        $m.installations.PSObject.Properties.Remove($AgentName)
    }
    $m.installations | Add-Member -NotePropertyName $AgentName -NotePropertyValue $entry
    $m | ConvertTo-Json -Depth 10 | Set-Content -Path $ManifestPath
}

function Remove-ManifestEntry {
    param([string]$ManifestPath, [string]$AgentName)
    if (!(Test-Path $ManifestPath)) { return }
    try {
        $m = Get-Content $ManifestPath -Raw | ConvertFrom-Json
        $m.installations.PSObject.Properties.Remove($AgentName)
        $m | ConvertTo-Json -Depth 10 | Set-Content -Path $ManifestPath
    } catch {}
}

function Get-ManifestAgents {
    param([string]$ManifestPath)
    if (!(Test-Path $ManifestPath)) { return @() }
    try {
        $m = Get-Content $ManifestPath -Raw | ConvertFrom-Json
        return @($m.installations.PSObject.Properties.Name)
    } catch { return @() }
}

# ─────────────────────────────────────────────────────────────────────────────
# Remote version check
# ─────────────────────────────────────────────────────────────────────────────

function Fetch-RemoteVersion {
    try {
        $ver = (Invoke-WebRequest -Uri "$REPO_BASE/VERSION" -UseBasicParsing -ErrorAction Stop).Content.Trim()
        return $ver
    } catch { return "" }
}

# ─────────────────────────────────────────────────────────────────────────────
# Download & assembly
# ─────────────────────────────────────────────────────────────────────────────

function Download-Files {
    param([string]$TmpDir)

    Write-Info "Downloading skill files..."
    foreach ($file in $SKILL_FILES) {
        $dir = Split-Path -Parent (Join-Path $TmpDir $file)
        if ($dir -and !(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        $url = "$REPO_BASE/$file"
        $dest = Join-Path $TmpDir $file
        try {
            Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -ErrorAction Stop | Out-Null
        } catch {
            Write-Err "Failed to download $file"
            Write-Err "Check your internet connection and try again."
            Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
            exit 1
        }
    }
    Write-Ok "Downloaded $($SKILL_FILES.Count) files"
}

function Assemble-Content {
    param([string]$TmpDir, [string]$Output)

    $content = @()
    $content += Get-Content (Join-Path $TmpDir "skills/conductor/SKILL.md") -Raw
    $content += "`n---`n"
    $content += "# References`n"
    foreach ($f in Get-ChildItem (Join-Path $TmpDir "skills/conductor/references") -Filter "*.md") {
        $content += Get-Content $f.FullName -Raw
        $content += "`n---`n"
    }
    $content += "# Examples`n"
    foreach ($f in Get-ChildItem (Join-Path $TmpDir "skills/conductor/examples") -Filter "*.md") {
        $content += Get-Content $f.FullName -Raw
        $content += "`n---`n"
    }
    $content -join "`n" | Set-Content -Path $Output -NoNewline
}

# ─────────────────────────────────────────────────────────────────────────────
# Safe file writing
# ─────────────────────────────────────────────────────────────────────────────

function Safe-Write {
    param([string]$Target, [string]$Source, [bool]$ForceWrite)

    if ((Test-Path $Target) -and !$ForceWrite) {
        Write-Warn "File already exists: $Target"
        $answer = Read-Host "  Overwrite? [y/N]"
        if ($answer -notmatch "^[Yy]") {
            Write-Info "Skipped. Use -Force to overwrite."
            return $false
        }
    }

    $dir = Split-Path -Parent $Target
    if ($dir -and !(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Copy-Item -Path $Source -Destination $Target -Force
    Write-Ok "Installed: $Target"
    return $true
}

# ─────────────────────────────────────────────────────────────────────────────
# Global install paths
# ─────────────────────────────────────────────────────────────────────────────

function Supports-Global {
    param([string]$AgentName)
    return $GLOBAL_AGENTS -contains $AgentName
}

function Get-GlobalPath {
    param([string]$AgentName)
    $home = $env:USERPROFILE
    switch ($AgentName) {
        "claude"   { return "__claude__" }
        "codex"    { $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $home ".codex" }; return Join-Path $codexHome "AGENTS.md" }
        "cursor"   { return Join-Path $home ".cursor\skills\conductor\SKILL.md" }
        "gemini"   { return Join-Path $home ".gemini\GEMINI.md" }
        "windsurf" { return Join-Path $home ".codeium\windsurf\memories\global_rules.md" }
        "roo"      { return Join-Path $home ".roo\rules\conductor.md" }
        "amp"      { return Join-Path $home ".config\AGENTS.md" }
        "aider"    { return Join-Path $home ".aider.conf.yml" }
        "opencode" { return Join-Path $home ".config\opencode\skills\conductor\SKILL.md" }
    }
}

function Get-TargetPath {
    param([string]$AgentName, [string]$ProjDir)
    switch ($AgentName) {
        "claude"   { return "__claude__" }
        "codex"    { return Join-Path $ProjDir "AGENTS.md" }
        "gemini"   { return Join-Path $ProjDir "GEMINI.md" }
        "cursor"   { return Join-Path $ProjDir ".cursor\rules\conductor.mdc" }
        "windsurf" { return Join-Path $ProjDir ".windsurfrules" }
        "cline"    { return Join-Path $ProjDir ".clinerules" }
        "aider"    { return Join-Path $ProjDir ".conductor-skills" }
        "copilot"  { return Join-Path $ProjDir ".github\copilot-instructions.md" }
        "amazonq"  { return Join-Path $ProjDir ".amazonq\rules\conductor.md" }
        "opencode" { return Join-Path $ProjDir "AGENTS.md" }
        "roo"      { return Join-Path $ProjDir ".roo\rules\conductor.md" }
        "amp"      { return Join-Path $ProjDir ".amp\instructions.md" }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Per-agent install logic
# ─────────────────────────────────────────────────────────────────────────────

function Install-Claude {
    if (!(Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Err "'claude' CLI not found. Install it first: npm install -g @anthropic-ai/claude-code"
        return $false
    }
    Write-Info "Installing skill via Claude Code CLI..."
    claude skill add --from "https://github.com/conductor-oss/conductor-skills"
    Write-Ok "Conductor skill added to Claude Code"
    return $true
}

function Install-ToFile {
    param([string]$Target, [string]$Assembled, [bool]$ForceWrite, [string]$Prefix = "")

    if ($Prefix) {
        $tmpFile = [System.IO.Path]::GetTempFileName()
        ($Prefix + (Get-Content $Assembled -Raw)) | Set-Content -Path $tmpFile -NoNewline
        Safe-Write -Target $Target -Source $tmpFile -ForceWrite $ForceWrite
        Remove-Item $tmpFile -ErrorAction SilentlyContinue
    } else {
        Safe-Write -Target $Target -Source $Assembled -ForceWrite $ForceWrite
    }
}

function Install-AiderToDir {
    param([string]$SkillDir, [string]$TmpDir, [string]$Config, [string]$ReadPrefix)

    New-Item -ItemType Directory -Path (Join-Path $SkillDir "references") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $SkillDir "examples") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $SkillDir "scripts") -Force | Out-Null

    Write-Info "Copying skill files to $SkillDir ..."
    Copy-Item (Join-Path $TmpDir "skills/conductor/SKILL.md") $SkillDir -Force
    foreach ($f in Get-ChildItem (Join-Path $TmpDir "skills/conductor/references") -Filter "*.md") {
        Copy-Item $f.FullName (Join-Path $SkillDir "references") -Force
    }
    foreach ($f in Get-ChildItem (Join-Path $TmpDir "skills/conductor/examples") -Filter "*.md") {
        Copy-Item $f.FullName (Join-Path $SkillDir "examples") -Force
    }
    $scriptsDir = Join-Path $TmpDir "skills/conductor/scripts"
    if (Test-Path $scriptsDir) {
        foreach ($f in Get-ChildItem $scriptsDir -Filter "*.py") {
            Copy-Item $f.FullName (Join-Path $SkillDir "scripts") -Force
        }
    }
    Write-Ok "Files copied to $SkillDir"

    if ((Test-Path $Config) -and (Select-String -Path $Config -Pattern "conductor-skills" -Quiet)) {
        Write-Info "Aider config already references conductor-skills, skipping."
    } else {
        Write-Info "Adding read entries to $Config ..."
        $entries = @("", "# Conductor Skills", "read:")
        foreach ($file in $SKILL_FILES) {
            $relative = $file -replace "^skills/conductor/", ""
            $entries += "  - ${ReadPrefix}${relative}"
        }
        $entries -join "`n" | Add-Content -Path $Config
        Write-Ok "Updated: $Config"
    }
}

function Install-ForAgent {
    param([string]$AgentName, [string]$ProjDir, [bool]$IsGlobal, [bool]$ForceWrite, [string]$TmpDir, [string]$Assembled)

    if ($AgentName -eq "claude") {
        return Install-Claude
    }

    if ($IsGlobal) {
        $home = $env:USERPROFILE
        if ($AgentName -eq "aider") {
            Install-AiderToDir -SkillDir (Join-Path $home ".conductor-skills") -TmpDir $TmpDir -Config (Join-Path $home ".aider.conf.yml") -ReadPrefix "$home/.conductor-skills/"
        } else {
            $targetPath = Get-GlobalPath -AgentName $AgentName
            Install-ToFile -Target $targetPath -Assembled $Assembled -ForceWrite $ForceWrite
        }
    } else {
        switch ($AgentName) {
            "codex"    { Install-ToFile -Target (Join-Path $ProjDir "AGENTS.md") -Assembled $Assembled -ForceWrite $ForceWrite }
            "gemini"   { Install-ToFile -Target (Join-Path $ProjDir "GEMINI.md") -Assembled $Assembled -ForceWrite $ForceWrite }
            "cursor"   {
                $frontmatter = "---`ndescription: Conductor workflow orchestration - create, run, monitor, and manage workflows`nglobs: `"**/*`"`nalwaysApply: true`n---`n`n"
                Install-ToFile -Target (Join-Path $ProjDir ".cursor\rules\conductor.mdc") -Assembled $Assembled -ForceWrite $ForceWrite -Prefix $frontmatter
            }
            "windsurf" { Install-ToFile -Target (Join-Path $ProjDir ".windsurfrules") -Assembled $Assembled -ForceWrite $ForceWrite }
            "cline"    { Install-ToFile -Target (Join-Path $ProjDir ".clinerules") -Assembled $Assembled -ForceWrite $ForceWrite }
            "aider"    { Install-AiderToDir -SkillDir (Join-Path $ProjDir ".conductor-skills") -TmpDir $TmpDir -Config (Join-Path $ProjDir ".aider.conf.yml") -ReadPrefix ".conductor-skills/" }
            "copilot"  { Install-ToFile -Target (Join-Path $ProjDir ".github\copilot-instructions.md") -Assembled $Assembled -ForceWrite $ForceWrite }
            "amazonq"  { Install-ToFile -Target (Join-Path $ProjDir ".amazonq\rules\conductor.md") -Assembled $Assembled -ForceWrite $ForceWrite }
            "opencode" { Install-ToFile -Target (Join-Path $ProjDir "AGENTS.md") -Assembled $Assembled -ForceWrite $ForceWrite }
            "roo"      { Install-ToFile -Target (Join-Path $ProjDir ".roo\rules\conductor.md") -Assembled $Assembled -ForceWrite $ForceWrite }
            "amp"      { Install-ToFile -Target (Join-Path $ProjDir ".amp\instructions.md") -Assembled $Assembled -ForceWrite $ForceWrite }
        }
    }
    return $true
}

# ─────────────────────────────────────────────────────────────────────────────
# Uninstall
# ─────────────────────────────────────────────────────────────────────────────

function Uninstall-Agent {
    param([string]$AgentName, [string]$ProjDir, [bool]$IsGlobal)

    if ($AgentName -eq "claude") {
        Write-Info "To remove the Conductor skill from Claude Code, run:"
        Write-Host "  claude skill remove conductor"
        return
    }

    if ($IsGlobal) {
        if ($AgentName -eq "aider") {
            $skillDir = Join-Path $env:USERPROFILE ".conductor-skills"
            if (Test-Path $skillDir) {
                Remove-Item -Recurse -Force $skillDir
                Write-Ok "Removed: $skillDir"
                Write-Info "Note: You may also want to remove the 'read:' entries from ~/.aider.conf.yml"
            } else {
                Write-Warn "Nothing to uninstall: $skillDir not found"
            }
            return
        }
        $target = Get-GlobalPath -AgentName $AgentName
    } else {
        $target = Get-TargetPath -AgentName $AgentName -ProjDir $ProjDir
        if ($AgentName -eq "aider") {
            if (Test-Path $target) {
                Remove-Item -Recurse -Force $target
                Write-Ok "Removed: $target"
                Write-Info "Note: You may also want to remove the 'read:' entries from .aider.conf.yml"
            } else {
                Write-Warn "Nothing to uninstall: $target not found"
            }
            return
        }
    }

    if (Test-Path $target) {
        Remove-Item -Force $target
        Write-Ok "Removed: $target"
    } else {
        Write-Warn "Nothing to uninstall: $target not found"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Check mode (dry run)
# ─────────────────────────────────────────────────────────────────────────────

function Do-Check {
    param([string[]]$Agents)

    $manifest = Get-ManifestPath -IsGlobal $true

    Write-Host ""
    Write-Host "Detected agents:" -ForegroundColor White
    if ($Agents.Count -eq 0) {
        Write-Warn "No AI coding agents detected on this system."
        return
    }

    foreach ($a in $Agents) {
        $installedVer = Read-ManifestVersion -ManifestPath $manifest -AgentName $a
        $globalSupport = if (Supports-Global -AgentName $a) { "yes" } else { "no" }

        if ($installedVer) {
            if ($installedVer -eq $SCRIPT_VERSION) {
                Write-Host "  * $a  v$installedVer (up to date)" -ForegroundColor Green
            } else {
                Write-Host "  * $a  v$installedVer -> v$SCRIPT_VERSION (upgrade available)" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  * $a  (not installed)  global: $globalSupport" -ForegroundColor Blue
        }
    }
    Write-Host ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if ($Version) {
    Write-Host "v$SCRIPT_VERSION"
    exit 0
}

# Require -Agent or -All
if (-not $Agent -and -not $All) {
    Write-Err "Missing required -Agent parameter (or use -All)"
    exit 1
}

# Resolve project dir
$ProjectDir = (Resolve-Path $ProjectDir).Path

Write-Host ""
Write-Host "Conductor Skills Installer v$SCRIPT_VERSION" -ForegroundColor White
Write-Host ""

# Build agent list
$agentList = @()
if ($All) {
    $agentList = @(Detect-Agents)
    if ($agentList.Count -eq 0) {
        Write-Warn "No AI coding agents detected on this system."
        Write-Host ""
        Write-Info "Supported agents: claude, codex, gemini, cursor, windsurf, cline,"
        Write-Info "  aider, copilot, amazonq, opencode, roo, amp"
        Write-Host ""
        Write-Info "Install one of the above, then re-run this command."
        exit 0
    }
    Write-Info "Detected agents: $($agentList -join ', ')"
    Write-Host ""
} else {
    $Agent = $Agent.ToLower()
    if ($VALID_AGENTS -notcontains $Agent) {
        Write-Err "Unknown agent: $Agent"
        exit 1
    }
    $agentList = @($Agent)
}

# Check mode
if ($Check) {
    Do-Check -Agents $agentList
    exit 0
}

# Determine manifest path
$useGlobalManifest = $Global -or $All
$manifest = Get-ManifestPath -IsGlobal $useGlobalManifest -ProjDir $ProjectDir

# Handle uninstall
if ($Uninstall) {
    foreach ($a in $agentList) {
        $useGlobal = [bool]$Global
        if ($All -and (Supports-Global -AgentName $a)) { $useGlobal = $true }
        Write-Info "Uninstalling $a ..."
        Uninstall-Agent -AgentName $a -ProjDir $ProjectDir -IsGlobal $useGlobal
        Remove-ManifestEntry -ManifestPath $manifest -AgentName $a
    }
    Write-Host ""
    Write-Ok "Done!"
    exit 0
}

# Check for upgrade
$targetVersion = $SCRIPT_VERSION
if ($Upgrade) {
    Write-Info "Checking for updates..."
    $remoteVer = Fetch-RemoteVersion
    if (-not $remoteVer) {
        Write-Warn "Could not check for updates (offline?). Using bundled v$SCRIPT_VERSION."
    } elseif ($remoteVer -ne $SCRIPT_VERSION) {
        Write-Info "Update available: v$SCRIPT_VERSION -> v$remoteVer"
        $targetVersion = $remoteVer
    } else {
        Write-Info "Already at latest version (v$SCRIPT_VERSION)."
    }
    Write-Host ""
}

# Download files to temp dir
$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) "conductor-skills-$(Get-Random)"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

try {
    Download-Files -TmpDir $tmpDir

    $assembled = Join-Path $tmpDir "_assembled.md"
    Assemble-Content -TmpDir $tmpDir -Output $assembled
    $size = (Get-Item $assembled).Length
    Write-Ok "Assembled skill content ($size bytes)"

    $installedCount = 0
    $skippedCount = 0

    foreach ($a in $agentList) {
        Write-Host ""

        # Determine if global for this agent
        $useGlobal = [bool]$Global
        if ($All) {
            if (Supports-Global -AgentName $a) {
                $useGlobal = $true
            } else {
                Write-Info "${a}: skipped (project-only install). Use -ProjectDir <path> to include."
                $skippedCount++
                continue
            }
        }

        # Validate global support for single-agent mode
        if ($useGlobal -and !(Supports-Global -AgentName $a)) {
            Write-Err "Global install is not supported for $a. Run from your project directory instead."
            continue
        }

        # Idempotency check
        $installedVer = Read-ManifestVersion -ManifestPath $manifest -AgentName $a
        if ($installedVer -and ($installedVer -eq $targetVersion) -and !$Force -and !$Upgrade) {
            Write-Ok "$a already at v$installedVer, skipping."
            $skippedCount++
            continue
        }

        if ($installedVer -and ($installedVer -ne $targetVersion)) {
            Write-Info "Upgrading $a from v$installedVer to v$targetVersion ..."
        } else {
            Write-Info "Installing for $a ..."
        }

        # Perform install
        $result = Install-ForAgent -AgentName $a -ProjDir $ProjectDir -IsGlobal $useGlobal -ForceWrite $Force -TmpDir $tmpDir -Assembled $assembled
        if ($result -ne $false) {
            $targetPath = if ($useGlobal) { Get-GlobalPath -AgentName $a } else { Get-TargetPath -AgentName $a -ProjDir $ProjectDir }
            $mode = if ($useGlobal) { "global" } else { "project" }
            Write-ManifestEntry -ManifestPath $manifest -AgentName $a -Ver $targetVersion -Mode $mode -TargetPath $targetPath
            $installedCount++
        }
    }

    Write-Host ""
    Write-Host "Done! Installed: $installedCount, Skipped: $skippedCount" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host '  Ask your agent to connect to your Conductor server, e.g.:'
    Write-Host ""
    Write-Host '     "Connect to my Conductor server at http://localhost:8080/api"'
    Write-Host ""
    Write-Host "  Docs: https://github.com/conductor-oss/conductor-skills" -ForegroundColor Blue
    Write-Host ""
} finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}
