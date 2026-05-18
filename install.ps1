#Requires -Version 5.1
<#
.SYNOPSIS
    oh-my-research Windows 설치 프로그램 (멱등성, 복원 가능).

.DESCRIPTION
    oh-my-research를 %USERPROFILE%\.codex 및 %USERPROFILE%\.agents\skills에 설치합니다.
    해당 영역 외부의 사용자 편집 내용을 덮어쓰지 않고 config.toml과 AGENTS.md에
    센티넬로 구분된 영역을 병합합니다.

.PARAMETER SkipEmail
    연락처 이메일 입력을 건너뜁니다.

.PARAMETER CodexHome
    Codex 홈 디렉토리를 재정의합니다 (기본값: %USERPROFILE%\.codex).

.EXAMPLE
    .\install.ps1
    .\install.ps1 -SkipEmail
    .\install.ps1 -CodexHome "C:\Users\alice\.codex"
#>
[CmdletBinding()]
param(
    [switch]$SkipEmail,
    [string]$CodexHome = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── colour helpers ───────────────────────────────────────────
function Write-Info  { param($msg) Write-Host "[omr] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[omr 경고] $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[omr 오류] $msg" -ForegroundColor Red }
function Fail        { param($msg) Write-Err $msg; exit 1 }

# ── locate bundle root ───────────────────────────────────────
$BundleDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ============================================================
# STEP 1 — Resolve CODEX_HOME and skills dir
# ============================================================
Write-Info "1/10 단계 — 경로 확인 중 ..."

if ($CodexHome -eq "") {
    $CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } `
                 else { Join-Path $env:USERPROFILE ".codex" }
}
$SkillsDir = Join-Path $env:USERPROFILE ".agents\skills"

if (-not (Test-Path $CodexHome -PathType Container)) {
    Fail "Codex 홈 디렉토리를 '$CodexHome'에서 찾을 수 없습니다.`n먼저 Codex 데스크탑 앱을 설치하세요 (https://codex.so) 또는`nCODEX_HOME 환경 변수를 설정한 뒤 설치 프로그램을 다시 실행하세요."
}

if (-not (Test-Path $SkillsDir -PathType Container)) {
    New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
}

Write-Info "  CODEX_HOME = $CodexHome"
Write-Info "  SKILLS_DIR = $SkillsDir"

$OmrHome = Join-Path $CodexHome "omr"

# ============================================================
# STEP 2 — Backup existing config.toml and AGENTS.md
# ============================================================
Write-Info "2/10 단계 — 기존 설정 백업 중 ..."

$Ts = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$BackupDir = Join-Path $CodexHome "backups\omr\$Ts"
New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

foreach ($f in @("config.toml", "AGENTS.md")) {
    $src = Join-Path $CodexHome $f
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $BackupDir $f)
        Write-Info "  $f 백업 완료 → $BackupDir\$f"
    }
}

# Track what step 3 copies for rollback
$CopiedSkills = [System.Collections.Generic.List[string]]::new()
$CopiedOmr    = $false

function Invoke-Rollback {
    Write-Warn "3단계 복사 내용 롤백 중 ..."
    foreach ($d in $CopiedSkills) {
        if (Test-Path $d) { Remove-Item -Recurse -Force $d; Write-Warn "  삭제됨: $d" }
    }
    if ($CopiedOmr -and (Test-Path $OmrHome)) {
        Remove-Item -Recurse -Force $OmrHome; Write-Warn "  삭제됨: $OmrHome"
    }
}

# ============================================================
# STEP 3 — Copy skill dirs and bundle
# ============================================================
Write-Info "3/10 단계 — 스킬 디렉토리 설치 중 ..."

$SkillsSrc = Join-Path $BundleDir "skills"
if (Test-Path $SkillsSrc -PathType Container) {
    foreach ($skillSrc in Get-ChildItem $SkillsSrc -Directory -Filter "omr-*") {
        $dst = Join-Path $SkillsDir $skillSrc.Name
        if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
        Copy-Item -Recurse $skillSrc.FullName $dst
        $CopiedSkills.Add($dst)
        Write-Info "  스킬 설치됨: $($skillSrc.Name)"
    }
} else {
    Write-Warn "  번들에 skills\ 디렉토리가 없습니다 — 스킬 복사를 건너뜁니다."
}

# omr/ bundle → %CODEX_HOME%\omr\
$OmrSrc = Join-Path $BundleDir "omr"
if (Test-Path $OmrSrc -PathType Container) {
    if (Test-Path $OmrHome) { Remove-Item -Recurse -Force $OmrHome }
    Copy-Item -Recurse $OmrSrc $OmrHome
    $CopiedOmr = $true
    Write-Info "  번들 설치됨 → $OmrHome"
}

# Optional prompts shims
$PromptsSrc = Join-Path $BundleDir "prompts"
if (Test-Path $PromptsSrc -PathType Container) {
    $PromptsDst = Join-Path $CodexHome "prompts"
    New-Item -ItemType Directory -Path $PromptsDst -Force | Out-Null
    Copy-Item "$PromptsSrc\*" $PromptsDst -Force
    Write-Info "  prompts\ 심 파일 설치됨"
}

# ============================================================
# STEP 4 — Python venv + pip install
# ============================================================
Write-Info "4/10 단계 — Python 가상 환경 설정 중 ..."

$PythonExe = $null
$PythonCandidates = @("python3.13","python3.12","python3.11","python3.10","python3","python")
foreach ($candidate in $PythonCandidates) {
    try {
        $verOut = & $candidate -c "import sys; print(sys.version_info[0], sys.version_info[1])" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $parts = $verOut.Trim() -split '\s+'
            $maj = [int]$parts[0]; $min = [int]$parts[1]
            if ($maj -ge 3 -and $min -ge 10) {
                $PythonExe = (Get-Command $candidate -ErrorAction SilentlyContinue).Path
                if (-not $PythonExe) { $PythonExe = $candidate }
                break
            }
        }
    } catch { continue }
}

if (-not $PythonExe) {
    Invoke-Rollback
    Fail "Python 3.10 이상을 찾을 수 없습니다.`n설치 방법:`n  winget install Python.Python.3.12`n  또는 https://www.python.org/downloads/"
}

$PythonVer = (& $PythonExe --version 2>&1)
Write-Info "  사용 중: $PythonExe ($PythonVer)"

$VenvDir = Join-Path $OmrHome "venv"
if (-not (Test-Path $VenvDir -PathType Container)) {
    & $PythonExe -m venv $VenvDir
    Write-Info "  가상 환경 생성됨: $VenvDir"
} else {
    Write-Info "  기존 가상 환경 재사용: $VenvDir"
}

$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

# Upgrade pip
& $VenvPy -m pip install --quiet --upgrade pip

# Install MCP packages
foreach ($pkgDir in @("omr_scholar","omr_render")) {
    $fullPkg = Join-Path $OmrHome "mcp\$pkgDir"
    if (Test-Path $fullPkg -PathType Container) {
        Write-Info "  pip install $pkgDir ..."
        & $VenvPy -m pip install --quiet -e $fullPkg
    }
}

# ============================================================
# STEP 5 — Merge config.toml region
# ============================================================
Write-Info "5/10 단계 — config.toml 영역 병합 중 ..."

$ConfigToml   = Join-Path $CodexHome "config.toml"
# TABLE region (position-independent — appended at END). Reuses the historical
# sentinel pair so a legacy single-combined region (same sentinels, also held
# the root scalars) is detected & cleanly removed by the self-healing strip on
# upgrade — no table duplication, clean migration.
$SentinelTomlStart = "# >>> oh-my-research (managed) >>>"
$SentinelTomlEnd   = "# <<< oh-my-research (managed) <<<"
# ROOT-SCALAR region (bare keys only — MUST sit before the first [table]
# header so it parses at the TOML document root, A6 fix). Distinct sentinels.
$SentinelTomlRootStart = "# >>> oh-my-research:root (managed) >>>"
$SentinelTomlRootEnd   = "# <<< oh-my-research:root (managed) <<<"
$TmplToml     = Join-Path $BundleDir "config\config.toml.omr-region.tmpl"
$TmplTomlRoot = Join-Path $BundleDir "config\config.toml.omr-root.tmpl"

function Get-TomlRegion {
    param([string]$Mailto = "")
    $tmpl = Get-Content $TmplToml -Raw
    $tmpl = $tmpl -replace [regex]::Escape("@@VENV_PY@@"),  $VenvPy.Replace('\','/')
    $tmpl = $tmpl -replace [regex]::Escape("@@OMR_HOME@@"),  $OmrHome.Replace('\','/')
    $tmpl = $tmpl -replace [regex]::Escape("@@OMR_SCHOLAR_MAILTO@@"), $Mailto
    return $tmpl
}

function Get-TomlRootRegion {
    # No placeholders today, but keep the substitution pipeline identical so
    # future @@...@@ tokens work uniformly across both regions.
    $tmpl = Get-Content $TmplTomlRoot -Raw
    $tmpl = $tmpl -replace [regex]::Escape("@@VENV_PY@@"),  $VenvPy.Replace('\','/')
    $tmpl = $tmpl -replace [regex]::Escape("@@OMR_HOME@@"),  $OmrHome.Replace('\','/')
    return $tmpl
}

# Self-healing strip: removes EVERY start sentinel line, EVERY end sentinel
# line, and every line strictly between a start and its FOLLOWING end (whole
# array). Orphan / standalone / duplicate sentinels are also removed. A start
# with no following end is a stray line to delete WITHOUT dropping subsequent
# user content (no data loss). Returns the surviving lines in original order.
function Remove-AllSentinelRegions {
    param(
        [string[]]$Lines,
        [string]$StartSentinel,
        [string]$EndSentinel
    )
    $n = $Lines.Count
    $endAfter = New-Object 'bool[]' $n
    $hasEndAfter = $false
    for ($i = $n - 1; $i -ge 0; $i--) {
        $endAfter[$i] = $hasEndAfter
        if ($Lines[$i] -eq $EndSentinel) { $hasEndAfter = $true }
    }
    $output = [System.Collections.Generic.List[string]]::new()
    $inside = $false
    for ($i = 0; $i -lt $n; $i++) {
        $l = $Lines[$i]
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
    return ,$output.ToArray()
}

# Idempotent, convergent sentinel-region merge. Self-heals ANY prior state
# (clean / orphan-end / orphan-start / duplicate / none / absent), then
# appends exactly ONE freshly-built region separated by exactly one blank line.
function Merge-SentinelRegion {
    param(
        [string]$FilePath,
        [string]$StartSentinel,
        [string]$EndSentinel,
        [string]$Region
    )

    if (-not (Test-Path $FilePath)) {
        Set-Content -Path $FilePath -Value "# Codex configuration`n" -Encoding UTF8
    }

    $lines = [System.IO.File]::ReadAllLines($FilePath, [System.Text.Encoding]::UTF8)

    # 1. Strip every sentinel + managed body anywhere (self-heal).
    $stripped = Remove-AllSentinelRegions -Lines $lines `
                    -StartSentinel $StartSentinel -EndSentinel $EndSentinel

    # 2. Drop trailing blank lines so we control the single separator exactly.
    $end = $stripped.Count - 1
    while ($end -ge 0 -and $stripped[$end] -match '^\s*$') { $end-- }

    $output = [System.Collections.Generic.List[string]]::new()
    for ($i = 0; $i -le $end; $i++) { $output.Add($stripped[$i]) }

    # 3. Append exactly one blank-line separator + the fresh region.
    #    Normalize the region: drop a single trailing newline's empty element
    #    so re-running yields byte-identical output (no trailing-nl growth).
    $regionLines = [System.Collections.Generic.List[string]]::new()
    foreach ($rl in ($Region -split "`r?`n")) { $regionLines.Add($rl) }
    while ($regionLines.Count -gt 0 -and $regionLines[$regionLines.Count - 1] -eq "") {
        $regionLines.RemoveAt($regionLines.Count - 1)
    }
    if ($output.Count -gt 0) { $output.Add("") }
    foreach ($rl in $regionLines) { $output.Add($rl) }

    [System.IO.File]::WriteAllLines($FilePath, $output, [System.Text.Encoding]::UTF8)
}

# Idempotent, convergent ROOT-SCALAR sentinel-region merge. Self-heals ANY
# prior state of the root region using the SAME A5 strip, then inserts exactly
# ONE freshly-built root region at the TOP of the file (before any pre-existing
# content) so the bare keys parse at the TOML document root and are never
# reparented into a user [table]. User content (incl. any leading user root
# keys) follows the region: omr root keys -> user root keys -> tables (valid).
function Merge-RootRegion {
    param(
        [string]$FilePath,
        [string]$StartSentinel,
        [string]$EndSentinel,
        [string]$Region
    )

    if (-not (Test-Path $FilePath)) {
        Set-Content -Path $FilePath -Value "# Codex configuration`n" -Encoding UTF8
    }

    $lines = [System.IO.File]::ReadAllLines($FilePath, [System.Text.Encoding]::UTF8)

    # 1. Strip every root sentinel + its body anywhere (self-heal).
    $stripped = Remove-AllSentinelRegions -Lines $lines `
                    -StartSentinel $StartSentinel -EndSentinel $EndSentinel

    # 2. Drop LEADING blank lines so we control the post-region separator.
    $startIdx = 0
    while ($startIdx -lt $stripped.Count -and $stripped[$startIdx] -match '^\s*$') {
        $startIdx++
    }

    # 3. Region FIRST (top of file), then one blank separator (only if user
    #    content remains), then the stripped content.
    $regionLines = [System.Collections.Generic.List[string]]::new()
    foreach ($rl in ($Region -split "`r?`n")) { $regionLines.Add($rl) }
    while ($regionLines.Count -gt 0 -and $regionLines[$regionLines.Count - 1] -eq "") {
        $regionLines.RemoveAt($regionLines.Count - 1)
    }

    $output = [System.Collections.Generic.List[string]]::new()
    foreach ($rl in $regionLines) { $output.Add($rl) }
    if ($startIdx -lt $stripped.Count) {
        $output.Add("")
        for ($i = $startIdx; $i -lt $stripped.Count; $i++) { $output.Add($stripped[$i]) }
    }

    [System.IO.File]::WriteAllLines($FilePath, $output, [System.Text.Encoding]::UTF8)
}

# Merge BOTH regions. TABLE region first (appended at END; its strip also
# clears any legacy single-combined region — same sentinels — clean upgrade,
# no table duplication). ROOT region second (inserted at TOP so the bare keys
# parse at the TOML document root — A6 fix).
$TomlRegionPlaceholder = Get-TomlRegion -Mailto "__PLACEHOLDER__"
Merge-SentinelRegion -FilePath $ConfigToml `
                     -StartSentinel $SentinelTomlStart `
                     -EndSentinel   $SentinelTomlEnd `
                     -Region        $TomlRegionPlaceholder

$TomlRootRegion = Get-TomlRootRegion
Merge-RootRegion -FilePath $ConfigToml `
                 -StartSentinel $SentinelTomlRootStart `
                 -EndSentinel   $SentinelTomlRootEnd `
                 -Region        $TomlRootRegion
Write-Info "  config.toml 병합 완료: $ConfigToml"

# ============================================================
# STEP 6 — Merge AGENTS.md block
# ============================================================
Write-Info "6/10 단계 — AGENTS.md 블록 병합 중 ..."

$AgentsMd      = Join-Path $CodexHome "AGENTS.md"
$TmplAgents    = Join-Path $BundleDir "config\AGENTS.md.omr-region.tmpl"
$SentinelAgStart = "<!-- omr:start -->"
$SentinelAgEnd   = "<!-- omr:end -->"

$AgentsRegion = Get-Content $TmplAgents -Raw
Merge-SentinelRegion -FilePath $AgentsMd `
                     -StartSentinel $SentinelAgStart `
                     -EndSentinel   $SentinelAgEnd `
                     -Region        $AgentsRegion
Write-Info "  AGENTS.md 병합 완료: $AgentsMd"

# ============================================================
# STEP 7 — Prerequisite probe: R, Quarto, pandoc
# ============================================================
Write-Info "7/10 단계 — 필수 프로그램 확인 중 ..."

function Find-Tool {
    # Probe PATH candidates first, then absolute fallback paths.
    # Mirrors omr_render/detect.py find_candidates() logic.
    param(
        [string[]]$PathCandidates,   # names to try via PATH (Get-Command)
        [string[]]$AbsCandidates = @() # absolute paths to probe if PATH misses
    )
    # 1. PATH probe
    foreach ($c in $PathCandidates) {
        $p = Get-Command $c -ErrorAction SilentlyContinue
        if ($p) { return $p.Source }
    }
    # 2. Absolute-path fallback (per-OS known install dirs)
    foreach ($abs in $AbsCandidates) {
        # Expand any environment variable references embedded in the string
        $expanded = [System.Environment]::ExpandEnvironmentVariables($abs)
        # Support glob patterns (e.g. C:\Program Files\R\R-*\bin\Rscript.exe)
        $resolved = @(Get-Item -Path $expanded -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1)
        if ($resolved.Count -gt 0 -and (Test-Path $resolved[0].FullName)) {
            try {
                $ver = & $resolved[0].FullName --version 2>&1 | Select-Object -First 1
                if ($ver) { return $resolved[0].FullName }
            } catch {}
        }
    }
    return $null
}

function Get-ToolVersion {
    param([string]$Path)
    try { return (& $Path --version 2>&1 | Select-Object -First 1) } catch { return "" }
}

function Test-VersionFloor {
    param([string]$VerStr, [int]$FloorMaj, [int]$FloorMin)
    $nums = [regex]::Matches($VerStr, '\d+') | ForEach-Object { [int]$_.Value }
    if ($nums.Count -lt 2) { return $false }
    $maj = $nums[0]; $min = $nums[1]
    return ($maj -gt $FloorMaj) -or ($maj -eq $FloorMaj -and $min -ge $FloorMin)
}

# Per-OS absolute candidate lists mirror omr_render/detect.py (_known_dirs_r/quarto/pandoc)
$LocalAppData = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { "" }

$RAbsCandidates = @(
    'C:\Program Files\R\R-*\bin\Rscript.exe',
    'C:\Program Files\R\R-*\bin\x64\Rscript.exe'
)
$QuartoAbsCandidates = @(
    $(if ($LocalAppData) { Join-Path $LocalAppData 'Programs\Quarto\bin\quarto.exe' } else { "" }),
    'C:\Program Files\Quarto\bin\quarto.exe'
) | Where-Object { $_ -ne "" }
$PandocAbsCandidates = @(
    $(if ($LocalAppData) { Join-Path $LocalAppData 'Pandoc\pandoc.exe' } else { "" }),
    'C:\Program Files\Pandoc\pandoc.exe'
) | Where-Object { $_ -ne "" }

$RPath      = Find-Tool -PathCandidates @("Rscript","R")      -AbsCandidates $RAbsCandidates
$QuartoPath = Find-Tool -PathCandidates @("quarto")           -AbsCandidates $QuartoAbsCandidates
$PandocPath = Find-Tool -PathCandidates @("pandoc")           -AbsCandidates $PandocAbsCandidates

$RVer      = if ($RPath)      { Get-ToolVersion $RPath }      else { "" }
$QuartoVer = if ($QuartoPath) { Get-ToolVersion $QuartoPath } else { "" }
$PandocVer = if ($PandocPath) { Get-ToolVersion $PandocPath } else { "" }

Write-Info "  R:      $(if ($RPath) { "$RPath  $RVer" } else { '찾을 수 없음' })"
Write-Info "  Quarto: $(if ($QuartoPath) { "$QuartoPath  $QuartoVer" } else { '찾을 수 없음' })"
Write-Info "  pandoc: $(if ($PandocPath) { "$PandocPath  $PandocVer" } else { '찾을 수 없음' })"

$PrereqFail = $false

if (-not $RPath) {
    Write-Err "R을 찾을 수 없습니다. https://cran.r-project.org 에서 R >= 4.2 를 설치하세요."
    $PrereqFail = $true
} elseif (-not (Test-VersionFloor $RVer 4 2)) {
    Write-Err "R 버전이 너무 낮습니다 (현재: $RVer). R >= 4.2 가 필요합니다 — https://cran.r-project.org 에서 업그레이드하세요."
    $PrereqFail = $true
}

if (-not $QuartoPath) {
    Write-Err "Quarto를 찾을 수 없습니다. https://quarto.org/docs/get-started/ 에서 Quarto >= 1.4 를 설치하세요."
    $PrereqFail = $true
} elseif (-not (Test-VersionFloor $QuartoVer 1 4)) {
    Write-Err "Quarto 버전이 너무 낮습니다 (현재: $QuartoVer). Quarto >= 1.4 가 필요합니다 — https://quarto.org 에서 업그레이드하세요."
    $PrereqFail = $true
}

if (-not $PandocPath) {
    Write-Err "pandoc을 찾을 수 없습니다. https://pandoc.org/installing.html 에서 pandoc >= 3.1 을 설치하세요."
    $PrereqFail = $true
} elseif (-not (Test-VersionFloor $PandocVer 3 1)) {
    Write-Err "pandoc 버전이 너무 낮습니다 (현재: $PandocVer). pandoc >= 3.1 이 필요합니다 — https://pandoc.org/installing.html 에서 업그레이드하세요."
    $PrereqFail = $true
}

if ($PrereqFail) {
    Fail "하나 이상의 필수 프로그램 확인이 실패했습니다 (위 오류 참조).`n필요한 도구를 설치한 뒤 설치 프로그램을 다시 실행하세요."
}

# ============================================================
# STEP 8 — Contact email prompt
# ============================================================
Write-Info "8/10 단계 — 학술 API용 연락처 이메일 입력 (polite pool) ..."

$OmrScholarMailto = ""
if (-not $SkipEmail -and [Environment]::UserInteractive) {
    Write-Host "`nUnpaywall/CrossRef polite pool에 등록할 연락처 이메일을 입력하세요"
    Write-Host "(건너뛰려면 Enter — config.toml에서 나중에 추가할 수 있습니다):"
    $OmrScholarMailto = Read-Host "  이메일"
    $OmrScholarMailto = $OmrScholarMailto.Trim()
}

if ($OmrScholarMailto -ne "") {
    Write-Info "  이메일 기록됨: $OmrScholarMailto"
    $TomlRegionFinal = Get-TomlRegion -Mailto $OmrScholarMailto
} else {
    Write-Info "  이메일 미입력 — 건너뜁니다."
    # Build region without the env section
    $TomlRegionFinal = Get-TomlRegion -Mailto ""
    # Strip empty mailto env block lines
    $TomlRegionFinal = ($TomlRegionFinal -split "`r?`n" | Where-Object {
        $_ -notmatch '^\[mcp_servers\.omr_scholar\.env\]' -and
        $_ -notmatch '^OMR_SCHOLAR_MAILTO\s*='
    }) -join "`n"
}

Merge-SentinelRegion -FilePath $ConfigToml `
                     -StartSentinel $SentinelTomlStart `
                     -EndSentinel   $SentinelTomlEnd `
                     -Region        $TomlRegionFinal
Write-Info "  config.toml이 업데이트되었습니다."

# ============================================================
# STEP 9 — "You're set" summary
# ============================================================
Write-Info "9/10 단계 — 설치 요약 ..."

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "  oh-my-research 설치가 완료되었습니다!" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "  전역 Codex 설정이 기록되었습니다 (특정 프로필에 한정되지 않는 전역 설정):"
Write-Host "    sandbox_mode, approval_policy, [sandbox_workspace_write],"
Write-Host "    [mcp_servers.omr_scholar], [mcp_servers.omr_render]"
Write-Host "  ※ 위 config 키들은 oh-my-research 전용이 아닌 전역 Codex 설정입니다."
Write-Host ""
Write-Host "  다음 단계:"
Write-Host "  1. Codex 데스크탑 앱을 엽니다."
Write-Host "  2. Codex 앱의 '/' 스킬 목록에서  `$omr-doctor  (설정 점검)을 실행하세요."
Write-Host "     '설정 점검'이 EV5 세션-전역 MCP 게이트를 통과해야"
Write-Host "     설치 완료로 간주됩니다"
Write-Host "     (omr_scholar + omr_render 버전 도구가 bare codex 실행 프롬프트에서"
Write-Host "     접근 가능해야 합니다)."
Write-Host "  3. 빈 연구 폴더를 워크스페이스로 생성/열고,"
Write-Host "     '/' 스킬 목록에서  `$omr-start  (연구 프로젝트 시작)을 실행하세요."
Write-Host ""
Write-Host "  스킬 설치 위치:   $SkillsDir"
Write-Host "  번들 설치 위치:   $OmrHome"
Write-Host "  설정 병합 위치:   $ConfigToml"
Write-Host "  AGENTS.md 위치:   $AgentsMd"
Write-Host "  백업 위치:        $BackupDir"
Write-Host ""

# ============================================================
# STEP 10 — Write manifest.json
# ============================================================
Write-Info "10/10 단계 — 매니페스트 작성 중 ..."

$ManifestPath = Join-Path $OmrHome "manifest.json"

$VersionStr = "0.1.0"
$VersionFile = Join-Path $OmrHome "VERSION"
if (Test-Path $VersionFile) { $VersionStr = (Get-Content $VersionFile -Raw).Trim() }

# Collect skill dirs
$SkillEntries = ($CopiedSkills | ForEach-Object { "    `"$_`"" }) -join ",`n"

# Collect omr files
$OmrFiles = @()
if (Test-Path $OmrHome -PathType Container) {
    $OmrFiles = Get-ChildItem -Recurse -File $OmrHome | ForEach-Object { $_.FullName }
}
$OmrFileEntries = ($OmrFiles | ForEach-Object { "    `"$_`"" }) -join ",`n"

$ManifestContent = @"
{
  "version": "$VersionStr",
  "installed_at": "$Ts",
  "codex_home": "$($CodexHome.Replace('\','/'))",
  "skills_dir": "$($SkillsDir.Replace('\','/'))",
  "omr_home": "$($OmrHome.Replace('\','/'))",
  "config_toml": "$($ConfigToml.Replace('\','/'))",
  "agents_md": "$($AgentsMd.Replace('\','/'))",
  "backup_dir": "$($BackupDir.Replace('\','/'))",
  "venv_python": "$($VenvPy.Replace('\','/'))",
  "prereqs": {
    "r":      { "path": "$($RPath -replace '\\','/')",      "version": "$RVer" },
    "quarto": { "path": "$($QuartoPath -replace '\\','/')", "version": "$QuartoVer" },
    "pandoc": { "path": "$($PandocPath -replace '\\','/')", "version": "$PandocVer" }
  },
  "skill_dirs": [
$SkillEntries
  ],
  "omr_files": [
$OmrFileEntries
  ],
  "config_regions": {
    "config_toml_table": {
      "sentinel_start": "# >>> oh-my-research (managed) >>>",
      "sentinel_end":   "# <<< oh-my-research (managed) <<<"
    },
    "config_toml_root": {
      "sentinel_start": "# >>> oh-my-research:root (managed) >>>",
      "sentinel_end":   "# <<< oh-my-research:root (managed) <<<"
    },
    "agents_md": {
      "sentinel_start": "<!-- omr:start -->",
      "sentinel_end":   "<!-- omr:end -->"
    }
  }
}
"@

Set-Content -Path $ManifestPath -Value $ManifestContent -Encoding UTF8
Write-Info "  매니페스트 작성 완료: $ManifestPath"
Write-Info "설치가 완료되었습니다."
