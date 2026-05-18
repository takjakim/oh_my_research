#Requires -Version 5.1
<#
.SYNOPSIS
    oh-my-research Windows 설치 제거 프로그램 (M2 설계).

.DESCRIPTION
    oh-my-research 자산을 제거합니다:
      - %USERPROFILE%\.agents\skills\ 에서 omr-* 스킬 디렉토리
      - %CODEX_HOME%\omr\ 번들
      - 선택적 prompts 심 파일
      - config.toml 및 AGENTS.md에서 센티넬로 구분된 관리 영역만
        (영역 외부의 사용자 편집 내용은 보존됨)
    센티넬 마커가 없거나 손상된 경우에만 백업 복원을 제안합니다.

.PARAMETER Force
    확인 프롬프트를 건너뜁니다.

.PARAMETER CodexHome
    Codex 홈 디렉토리를 재정의합니다.
#>
[CmdletBinding()]
param(
    [switch]$Force,
    [string]$CodexHome = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info { param($msg) Write-Host "[omr-uninstall] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[omr-uninstall 경고] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "[omr-uninstall 오류] $msg" -ForegroundColor Red }
function Fail       { param($msg) Write-Err $msg; exit 1 }

# ── paths ────────────────────────────────────────────────────
if ($CodexHome -eq "") {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } `
                 else { Join-Path $env:USERPROFILE ".codex" }
}
$SkillsDir  = Join-Path $env:USERPROFILE ".agents\skills"
$OmrHome    = Join-Path $CodexHome "omr"
$ConfigToml = Join-Path $CodexHome "config.toml"
$AgentsMd   = Join-Path $CodexHome "AGENTS.md"
$PromptsDir = Join-Path $CodexHome "prompts"

# TABLE region sentinels (also match a legacy single-combined region).
$SentinelTomlStart = "# >>> oh-my-research (managed) >>>"
$SentinelTomlEnd   = "# <<< oh-my-research (managed) <<<"
# ROOT-SCALAR region sentinels (A6 split — separate top-of-file region).
$SentinelTomlRootStart = "# >>> oh-my-research:root (managed) >>>"
$SentinelTomlRootEnd   = "# <<< oh-my-research:root (managed) <<<"
$SentinelAgStart   = "<!-- omr:start -->"
$SentinelAgEnd     = "<!-- omr:end -->"

# ── confirmation ─────────────────────────────────────────────
Write-Host ""
Write-Host "oh-my-research 설치 제거 프로그램" -ForegroundColor White
Write-Host "다음 위치에서 oh-my-research 자산을 제거합니다:"
Write-Host "  스킬:    $SkillsDir\omr-*"
Write-Host "  번들:    $OmrHome"
Write-Host "  설정:    $ConfigToml  (센티넬 영역만)"
Write-Host "  Agents:  $AgentsMd   (센티넬 영역만)"
Write-Host ""

if (-not $Force) {
    $confirm = Read-Host "계속하시겠습니까? [y/N]"
    if ($confirm -notmatch '^[yY]') {
        Write-Info "취소되었습니다."
        exit 0
    }
}

# ── helper: self-healing sentinel strip ──────────────────────
# Removes EVERY start sentinel line, EVERY end sentinel line, and every line
# strictly between a start and its FOLLOWING end (whole array). Orphan /
# standalone / duplicate sentinels are also removed. A start with no following
# end is a stray line to delete WITHOUT dropping subsequent user content.
#   return $true  : sentinel(s) found & cleanly stripped (or file absent)
#   return $false : NO sentinel markers at all → corruption-fallback signal
function Remove-SentinelRegion {
    param(
        [string]$FilePath,
        [string]$StartSentinel,
        [string]$EndSentinel
    )

    if (-not (Test-Path $FilePath)) {
        Write-Warn "  $FilePath 을 찾을 수 없습니다 — 건너뜁니다."
        return $true   # not an error
    }

    $lines = [System.IO.File]::ReadAllLines($FilePath, [System.Text.Encoding]::UTF8)

    $hasStart = $lines -contains $StartSentinel
    $hasEnd   = $lines -contains $EndSentinel

    if (-not $hasStart -and -not $hasEnd) {
        Write-Warn "  $FilePath 에서 센티넬 마커를 찾을 수 없습니다."
        return $false  # signal: nothing managed → possible corruption/overwrite
    }

    $n = $lines.Count
    $endAfter = New-Object 'bool[]' $n
    $hasEndAfter = $false
    for ($i = $n - 1; $i -ge 0; $i--) {
        $endAfter[$i] = $hasEndAfter
        if ($lines[$i] -eq $EndSentinel) { $hasEndAfter = $true }
    }

    $output = [System.Collections.Generic.List[string]]::new()
    $inside = $false
    for ($i = 0; $i -lt $n; $i++) {
        $l = $lines[$i]
        if ($inside) {
            if ($l -eq $EndSentinel) { $inside = $false }
            continue
        }
        if ($l -eq $StartSentinel) {
            if ($endAfter[$i]) { $inside = $true }
            continue
        }
        if ($l -eq $EndSentinel) { continue }
        $output.Add($l)
    }

    # Trim BOTH leading and trailing blank lines left where the region sat
    # (a top-of-file ROOT region leaves a leading blank after its separator;
    # a tail TABLE region leaves trailing blanks). Interior blanks preserved.
    while ($output.Count -gt 0 -and $output[$output.Count - 1] -match '^\s*$') {
        $output.RemoveAt($output.Count - 1)
    }
    while ($output.Count -gt 0 -and $output[0] -match '^\s*$') {
        $output.RemoveAt(0)
    }

    [System.IO.File]::WriteAllLines($FilePath, $output, [System.Text.Encoding]::UTF8)
    Write-Info "  $FilePath 에서 센티넬 영역이 제거되었습니다 (고아 마커 포함 자가 치유)."
    return $true
}

# ── helper: offer backup restore (corruption fallback only) ──
function Invoke-BackupRestoreOffer {
    param([string]$TargetFile)

    $backupBase = Join-Path $CodexHome "backups\omr"
    if (-not (Test-Path $backupBase -PathType Container)) {
        Write-Warn "$backupBase 에 백업이 없습니다 — 복원 불가."
        return
    }

    $latest = Get-ChildItem $backupBase -Directory | Sort-Object Name | Select-Object -Last 1
    if (-not $latest) {
        Write-Warn "백업 타임스탬프를 찾을 수 없습니다."
        return
    }

    $backupFile = Join-Path $latest.FullName (Split-Path -Leaf $TargetFile)
    if (-not (Test-Path $backupFile)) {
        Write-Warn "$backupFile 에 백업 파일이 없습니다."
        return
    }

    Write-Host ""
    Write-Host "백업 $($latest.Name) 에서 $TargetFile 을 복원하시겠습니까?" -ForegroundColor Yellow
    Write-Host "(현재 파일을 덮어씁니다 — 파일이 손상된 경우에만 사용하세요)"
    $r = Read-Host "복원? [y/N]"
    if ($r -match '^[yY]') {
        Copy-Item $backupFile $TargetFile -Force
        Write-Info "  $TargetFile 이 $backupFile 에서 복원되었습니다."
    } else {
        Write-Info "  $TargetFile 백업 복원을 건너뜁니다."
    }
}

# ── 1. Remove skill dirs ─────────────────────────────────────
Write-Info "$SkillsDir 에서 omr-* 스킬 디렉토리를 제거하는 중 ..."
$removedSkills = 0
if (Test-Path $SkillsDir -PathType Container) {
    foreach ($skill in Get-ChildItem $SkillsDir -Directory -Filter "omr-*") {
        Remove-Item -Recurse -Force $skill.FullName
        Write-Info "  삭제됨: $($skill.FullName)"
        $removedSkills++
    }
}
if ($removedSkills -eq 0) { Write-Warn "  $SkillsDir 에서 omr-* 스킬 디렉토리를 찾을 수 없습니다." }

# ── 2. Remove bundle ─────────────────────────────────────────
Write-Info "$OmrHome 번들을 제거하는 중 ..."
if (Test-Path $OmrHome -PathType Container) {
    Remove-Item -Recurse -Force $OmrHome
    Write-Info "  삭제됨: $OmrHome"
} else {
    Write-Warn "  $OmrHome 을 찾을 수 없습니다 — 건너뜁니다."
}

# Remove known prompts shims only
if (Test-Path $PromptsDir -PathType Container) {
    Write-Info "$PromptsDir 에서 omr prompts 심 파일을 제거하는 중 ..."
    foreach ($shim in @("omr-start.md","omr-lit.md","omr-analyze.md","omr-write.md","omr-status.md")) {
        $f = Join-Path $PromptsDir $shim
        if (Test-Path $f) { Remove-Item $f -Force; Write-Info "  삭제됨: $f" }
    }
}

# ── 3. Strip BOTH config.toml sentinel regions ───────────────
# TABLE region first (also clears any legacy single-combined region, same
# sentinels), then ROOT-SCALAR region (top-of-file). Corruption fallback is
# offered ONLY when NEITHER region has any sentinel present at all.
Write-Info "$ConfigToml 에서 관리 영역을 제거하는 중 (테이블 + 루트) ..."
$okTable = Remove-SentinelRegion -FilePath $ConfigToml `
                             -StartSentinel $SentinelTomlStart `
                             -EndSentinel   $SentinelTomlEnd
$okRoot = Remove-SentinelRegion -FilePath $ConfigToml `
                             -StartSentinel $SentinelTomlRootStart `
                             -EndSentinel   $SentinelTomlRootEnd
if ((-not $okTable) -and (-not $okRoot)) { Invoke-BackupRestoreOffer -TargetFile $ConfigToml }

# ── 4. Strip AGENTS.md sentinel block ────────────────────────
Write-Info "$AgentsMd 에서 관리 블록을 제거하는 중 ..."
$ok = Remove-SentinelRegion -FilePath $AgentsMd `
                             -StartSentinel $SentinelAgStart `
                             -EndSentinel   $SentinelAgEnd
if (-not $ok) { Invoke-BackupRestoreOffer -TargetFile $AgentsMd }

# ── Summary ──────────────────────────────────────────────────
Write-Host ""
Write-Host "oh-my-research 설치가 제거되었습니다." -ForegroundColor Green
Write-Host "센티넬 영역 외부의 사용자 편집 내용은 보존되었습니다."
Write-Host "백업 위치: $(Join-Path $CodexHome 'backups\omr\')"
Write-Host ""
