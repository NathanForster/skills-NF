# sync-skills.ps1
# Copies changed skills and the shared lib from this repo to where Claude Code
# and GitHub Copilot load them, then commits. Run after editing a skill.
#
#   skills\<name>\...  ->  every folder in SKILL_DIRS
#   lib\...            ->  COMMANDS_DIR\lib\   (the shared docset engine)
#   anything else      ->  not installed (README, this script, .env.example, ...)
#
# Only uncommitted changes are synced. A change you commit yourself first is
# never copied, so either run this before committing or copy that file by hand.
#
# Install paths default to your user profile. To override them on one machine,
# copy .env.example to .env (gitignored) and edit it.
#
# Usage: powershell -ExecutionPolicy Bypass -File <repo>\sync-skills.ps1

$RepoDir     = $PSScriptRoot
$CommandsDir = Join-Path $HOME ".claude\commands"
$SkillDirs   = @((Join-Path $HOME ".claude\skills"), (Join-Path $HOME ".copilot\skills"))

function Expand-Home([string]$Path) {
    if ($Path -eq "~") { return $HOME }
    if ($Path -like "~[\/]*") { return Join-Path $HOME $Path.Substring(2) }
    return $Path
}

# Optional overrides: KEY=VALUE lines; # starts a comment; a blank value keeps
# the default. An unknown key is reported rather than silently ignored, because
# a misspelled key would otherwise quietly install to the default location.
$EnvFile = Join-Path $RepoDir ".env"
if (Test-Path $EnvFile) {
    foreach ($Raw in Get-Content $EnvFile) {
        $Line = $Raw.Trim()
        if (-not $Line -or $Line.StartsWith("#")) { continue }
        $Key, $Value = $Line -split "=", 2
        $Key   = $Key.Trim()
        $Value = "$Value".Trim().Trim('"').Trim("'")
        switch ($Key) {
            "COMMANDS_DIR" { if ($Value) { $CommandsDir = Expand-Home $Value } }
            "SKILL_DIRS"   {
                if ($Value) {
                    $SkillDirs = @($Value -split ";" | ForEach-Object { $_.Trim() } |
                                   Where-Object { $_ } | ForEach-Object { Expand-Home $_ })
                }
            }
            default { Write-Warning ".env: unknown key '$Key' ignored (expected COMMANDS_DIR or SKILL_DIRS)" }
        }
    }
}

Write-Host "Repo   : $RepoDir"
Write-Host "Skills : $($SkillDirs -join '; ')"
Write-Host "lib    : $(Join-Path $CommandsDir 'lib')"
if (Test-Path $EnvFile) { Write-Host "         (with overrides from .env)" }
Write-Host ""

# Where a repo file gets installed: an allowlist, so a new file elsewhere in
# the repo is never copied into a folder the tools load from.
function Get-Targets([string]$RelPath) {
    $p = $RelPath -replace '/', '\'
    if ($p -like 'skills\*\*') {
        $rest = $p.Substring(7)
        return @($SkillDirs | ForEach-Object { Join-Path $_ $rest })
    }
    if ($p -like 'lib\*') {
        return @(Join-Path $CommandsDir $p)
    }
    return @()
}

# -uall lists the files inside a new folder one by one, instead of just the
# folder, so a brand-new skill gets copied rather than skipped.
$StatusLines = git -C $RepoDir status --porcelain -uall

if (-not $StatusLines) {
    Write-Host "Nothing to sync -- working tree is clean." -ForegroundColor Green
    exit 0
}

$ToRemove = @()
$ToCopy   = @()

foreach ($Line in $StatusLines) {
    $XY   = $Line.Substring(0, 2)
    $Path = $Line.Substring(3).Trim()
    if ($XY -match '[RC]') {
        # Rename or copy: "old -> new". A rename retires the old location.
        $Old, $New = $Path -split ' -> ', 2
        if ($XY -match 'R') { $ToRemove += $Old.Trim('"') }
        $ToCopy += $New.Trim('"')
    } elseif ($XY -match 'D') {
        $ToRemove += $Path.Trim('"')
    } else {
        $ToCopy += $Path.Trim('"')
    }
}

$Synced  = @()
$Deleted = @()

# After a removal, prune any folders it left empty (a renamed or deleted skill
# would otherwise leave its folder behind), stopping at the install roots.
$Roots = @($SkillDirs) + @(Join-Path $CommandsDir "lib") | ForEach-Object { $_.TrimEnd('\') }
function Remove-EmptyParents([string]$Target) {
    $Dir = Split-Path $Target -Parent
    while ($Dir -and (Test-Path $Dir -PathType Container) -and
           -not (Get-ChildItem -Force $Dir | Select-Object -First 1)) {
        $AtRoot = $Roots | Where-Object { $Dir.TrimEnd('\') -ieq $_ }
        $Inside = $Roots | Where-Object { $Dir.StartsWith($_ + '\', [StringComparison]::OrdinalIgnoreCase) }
        if ($AtRoot -or -not $Inside) { break }
        Remove-Item $Dir -Force
        Write-Host "  Removed : $Dir\ (left empty)" -ForegroundColor Yellow
        $Dir = Split-Path $Dir -Parent
    }
}

foreach ($File in $ToRemove) {
    $Targets = Get-Targets $File
    if (-not $Targets) { continue }
    foreach ($Target in $Targets) {
        if (Test-Path $Target) {
            Remove-Item $Target -Force
            Write-Host "  Removed : $Target" -ForegroundColor Yellow
            Remove-EmptyParents $Target
        }
    }
    $Deleted += $File
}

foreach ($File in $ToCopy) {
    $Targets = Get-Targets $File
    if (-not $Targets) { continue }
    $Source = Join-Path $RepoDir $File
    if (-not (Test-Path $Source -PathType Leaf)) { continue }
    foreach ($Target in $Targets) {
        $TargetDir = Split-Path $Target -Parent
        if (-not (Test-Path $TargetDir)) {
            New-Item -ItemType Directory -Force $TargetDir | Out-Null
        }
        Copy-Item $Source $Target -Force
        Write-Host "  Synced  : $Target" -ForegroundColor Cyan
    }
    $Synced += $File
}

$AllChanged = $Synced + $Deleted
if ($AllChanged.Count -eq 0) {
    Write-Host "No installable files changed (only files outside skills\ and lib\)." -ForegroundColor Green
    exit 0
}

$CommitMsg = "sync: " + ($AllChanged -join ", ")
git -C $RepoDir add -A
git -C $RepoDir commit -m $CommitMsg

Write-Host ""
Write-Host "Committed: $CommitMsg" -ForegroundColor Green
