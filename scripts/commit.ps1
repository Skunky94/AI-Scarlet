<#
.SYNOPSIS
    Helper per commit Conventional Commits + aggiornamento automatico CHANGELOG.md

.PARAMETER Type
    Tipo: feat, fix, refactor, docs, chore, infra, test, style

.PARAMETER Scope
    Scope opzionale (es. gateway, pad, memory, docker)

.PARAMETER Description
    Descrizione breve (imperativo, max 72 char)

.PARAMETER Body
    Descrizione estesa per changelog (opzionale)

.PARAMETER Files
    File specifici da aggiungere (default: tutti - git add -A)

.PARAMETER NoStage
    Non eseguire git add

.PARAMETER Yes
    Salta la conferma interattiva

.EXAMPLE
    .\scripts\commit.ps1 -Type feat -Scope gateway -Description "Aggiunge endpoint /health"

.EXAMPLE
    .\scripts\commit.ps1
    # Modalita interattiva
#>
[CmdletBinding()]
param(
    [ValidateSet("feat","fix","refactor","docs","chore","infra","test","style")]
    [string]$Type,
    [string]$Scope,
    [string]$Description,
    [string]$Body,
    [string[]]$Files,
    [switch]$NoStage,
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT      = Split-Path -Parent $PSScriptRoot
$CHANGELOG = Join-Path $ROOT "CHANGELOG.md"

$VALID_TYPES = @("feat","fix","refactor","docs","chore","infra","test","style")
$TYPE_LABELS = @{
    feat     = "Nuova funzionalita"
    fix      = "Correzione bug"
    refactor = "Refactoring"
    docs     = "Documentazione"
    chore    = "Manutenzione"
    infra    = "Infrastruttura"
    test     = "Test"
    style    = "Stile/formattazione"
}

function Write-H  { param($m) Write-Host "`n$m" -ForegroundColor Cyan }
function Write-Ok { param($m) Write-Host "  $m" -ForegroundColor Green }
function Write-Wn { param($m) Write-Host "  $m" -ForegroundColor Yellow }
function Write-Er { param($m) Write-Host "  ERRORE: $m" -ForegroundColor Red }

Set-Location $ROOT
if (-not (Test-Path ".git")) {
    Write-Er "Non sei nella root del repository git."
    exit 1
}

Write-H "=== SCARLET - COMMIT HELPER ==="
Write-Host ""

$gitStatus = git status --short 2>&1
if (-not $gitStatus) {
    Write-Wn "Nessuna modifica da committare. Uscita."
    exit 0
}

Write-Host "Modifiche correnti:" -ForegroundColor White
foreach ($line in $gitStatus) {
    $sc = $line.Substring(0,2).Trim()
    $color = switch -Wildcard ($sc) {
        "A*" { "Green" }
        "M*" { "Yellow" }
        "D*" { "Red" }
        "??" { "Gray" }
        default { "White" }
    }
    Write-Host "  $line" -ForegroundColor $color
}
Write-Host ""

if (-not $Type) {
    Write-Host "Tipo di commit:" -ForegroundColor White
    $i = 1
    foreach ($t in $VALID_TYPES) {
        Write-Host "  [$i] $t - $($TYPE_LABELS[$t])"
        $i++
    }
    Write-Host ""
    do {
        $choice = Read-Host "Scegli [1-$($VALID_TYPES.Count)]"
        $idx = [int]$choice - 1
    } while ($idx -lt 0 -or $idx -ge $VALID_TYPES.Count)
    $Type = $VALID_TYPES[$idx]
}

if (-not $Scope) {
    $inp = Read-Host "Scope (opzionale, es. gateway/pad/memory - invio per saltare)"
    $Scope = $inp.Trim()
}

if (-not $Description) {
    do {
        $inp = Read-Host "Descrizione breve (imperativo, max 72 char)"
        $Description = $inp.Trim()
    } while ($Description.Length -eq 0)
}

if (-not $Body) {
    $inp = Read-Host "Descrizione estesa per changelog (opzionale - invio per saltare)"
    $Body = $inp.Trim()
}

$scopePart = if ($Scope) { "($Scope)" } else { "" }
$commitMsg = "${Type}${scopePart}: $Description"

if ($commitMsg.Length -gt 72) {
    Write-Wn "Il messaggio supera 72 caratteri ($($commitMsg.Length))."
}

Write-Host ""
Write-Host "Messaggio commit: " -ForegroundColor White -NoNewline
Write-Host $commitMsg -ForegroundColor Cyan

# --- Raccoglie file modificati per changelog ---
$fileEntries = @()
$changed = git diff --name-status HEAD 2>&1
foreach ($line in $changed) {
    if ($line -match "^([AMDRC])\s+(.+)$") {
        $lbl = switch ($Matches[1]) {
            "A" { "*(new)*" }; "M" { "*(modified)*" }; "D" { "*(deleted)*" }
            "R" { "*(renamed)*" }; "C" { "*(copied)*" }; default { "" }
        }
        $fileEntries += "- ``$($Matches[2])`` $lbl"
    }
}
$untracked = git ls-files --others --exclude-standard 2>&1
foreach ($f in $untracked) {
    if ($f) { $fileEntries += "- ``$f`` *(new)*" }
}
if ($fileEntries.Count -eq 0) {
    $cached = git diff --name-status --cached 2>&1
    foreach ($line in $cached) {
        if ($line -match "^([AMDRC])\s+(.+)$") {
            $lbl = switch ($Matches[1]) {
                "A" { "*(new)*" }; "M" { "*(modified)*" }; "D" { "*(deleted)*" }; default { "" }
            }
            $fileEntries += "- ``$($Matches[2])`` $lbl"
        }
    }
}

# --- Compone entry changelog ---
$today     = Get-Date -Format "yyyy-MM-dd"
$typeLabel = $TYPE_LABELS[$Type]

$entry = "`n---`n`n## [$today] ``${Type}${scopePart}`` - $Description`n`n**Categoria:** $typeLabel"
if ($Body)                { $entry += "`n`n$Body" }
if ($fileEntries.Count -gt 0) { $entry += "`n`n### File`n" + ($fileEntries -join "`n") }

Write-Host ""
Write-Host "Entry CHANGELOG:" -ForegroundColor White
Write-Host $entry -ForegroundColor DarkGray

# --- Conferma ---
Write-Host ""
$confirm = if ($Yes) { "S" } else { Read-Host "Procedere? [S/n]" }
if ($confirm -match "^[Nn]") {
    Write-Wn "Annullato."
    exit 0
}

# --- Aggiorna CHANGELOG.md ---
if (Test-Path $CHANGELOG) {
    $existing = [System.IO.File]::ReadAllText($CHANGELOG, [System.Text.Encoding]::UTF8)
    $marker = "<!-- ENTRIES -->"
    if ($existing.Contains($marker)) {
        $newContent = $existing.Replace($marker, "$marker$entry")
    } else {
        $lines = $existing -split "`n"
        $newContent = $lines[0] + "`n" + $entry + "`n" + ($lines[1..($lines.Length-1)] -join "`n")
    }
    [System.IO.File]::WriteAllText($CHANGELOG, $newContent, [System.Text.Encoding]::UTF8)
} else {
    Write-Wn "CHANGELOG.md non trovato - verra creato."
}
Write-Ok "CHANGELOG.md aggiornato."

# --- git add ---
if (-not $NoStage) {
    if ($Files -and $Files.Count -gt 0) {
        git add ($Files + $CHANGELOG)
    } else {
        git add -A
    }
    Write-Ok "Staging completato."
}

# --- git commit ---
git commit -m $commitMsg
Write-Ok "Commit eseguito: $commitMsg"
Write-Host ""
Write-Host "Ultimi commit:" -ForegroundColor White
git log --oneline -3