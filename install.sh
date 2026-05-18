#!/usr/bin/env bash
# ============================================================
#  oh-my-research  —  install.sh
#  macOS + Linux installer (idempotent, reversible)
#  Usage:  bash install.sh [--skip-email]
# ============================================================
set -euo pipefail

# ── colours (suppressed when not a tty) ──────────────────────
if [ -t 1 ]; then
  RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
  BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; YELLOW=''; GREEN=''; BOLD=''; RESET=''
fi

info()  { printf "${GREEN}[omr]${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}[omr 경고]${RESET} %s\n" "$*"; }
error() { printf "${RED}[omr 오류]${RESET} %s\n" "$*" >&2; }
die()   { error "$*"; exit 1; }

# ── locate the bundle root (script's own directory) ──────────
BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── arg parsing ──────────────────────────────────────────────
SKIP_EMAIL=false
for arg in "$@"; do
  case "$arg" in
    --skip-email) SKIP_EMAIL=true ;;
    *) warn "알 수 없는 인수: $arg" ;;
  esac
done

# ============================================================
# STEP 1 — Resolve CODEX_HOME and skills dir
# ============================================================
info "1/10 단계 — 경로 확인 중 …"

CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
SKILLS_DIR="${HOME}/.agents/skills"

if [ ! -d "$CODEX_HOME" ]; then
  die "Codex 홈 디렉토리를 '${CODEX_HOME}'에서 찾을 수 없습니다.
먼저 Codex 데스크탑 앱을 설치하세요 (https://codex.so) 또는
CODEX_HOME을 올바른 경로로 설정한 뒤 설치 프로그램을 다시 실행하세요."
fi

mkdir -p "$SKILLS_DIR"
info "  CODEX_HOME = $CODEX_HOME"
info "  SKILLS_DIR = $SKILLS_DIR"

OMR_HOME="${CODEX_HOME}/omr"

# ============================================================
# STEP 2 — Backup existing config.toml and AGENTS.md
# ============================================================
info "2/10 단계 — 기존 설정 백업 중 …"

TS="$(date -u '+%Y%m%dT%H%M%SZ')"
BACKUP_DIR="${CODEX_HOME}/backups/omr/${TS}"
mkdir -p "$BACKUP_DIR"

for f in config.toml AGENTS.md; do
  if [ -f "${CODEX_HOME}/${f}" ]; then
    cp "${CODEX_HOME}/${f}" "${BACKUP_DIR}/${f}"
    info "  ${f} 백업 완료 → ${BACKUP_DIR}/${f}"
  fi
done

# ── helper: rollback step-3 copies on fatal error ─────────────
_COPIED_SKILLS=()
_COPIED_OMR=false

_rollback_step3() {
  warn "3단계 복사 내용 롤백 중 …"
  for d in "${_COPIED_SKILLS[@]}"; do
    rm -rf "$d" && warn "  스킬 디렉토리 삭제됨: $d"
  done
  if $_COPIED_OMR && [ -d "$OMR_HOME" ]; then
    rm -rf "$OMR_HOME" && warn "  $OMR_HOME 삭제됨"
  fi
}

# ============================================================
# STEP 3 — Copy skill dirs and bundle
# ============================================================
info "3/10 단계 — 스킬 디렉토리 설치 중 …"

# skills/omr-* → ~/.agents/skills/
if [ -d "${BUNDLE_DIR}/skills" ]; then
  for skill_src in "${BUNDLE_DIR}/skills"/omr-*; do
    [ -d "$skill_src" ] || continue
    skill_name="$(basename "$skill_src")"
    skill_dst="${SKILLS_DIR}/${skill_name}"
    rm -rf "$skill_dst"
    cp -r "$skill_src" "$skill_dst"
    _COPIED_SKILLS+=("$skill_dst")
    info "  스킬 설치됨: $skill_name"
  done
else
  warn "  번들에 skills/ 디렉토리가 없습니다 — 스킬 복사를 건너뜁니다."
fi

# omr/ bundle → ~/.codex/omr/
if [ -d "${BUNDLE_DIR}/omr" ]; then
  mkdir -p "$OMR_HOME"
  # rsync preferred; fall back to cp -r
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "${BUNDLE_DIR}/omr/" "${OMR_HOME}/"
  else
    rm -rf "$OMR_HOME"
    cp -r "${BUNDLE_DIR}/omr" "$OMR_HOME"
  fi
  _COPIED_OMR=true
  info "  번들 설치됨 → $OMR_HOME"
fi

# optional prompts/ shims → ~/.codex/prompts/
if [ -d "${BUNDLE_DIR}/prompts" ]; then
  mkdir -p "${CODEX_HOME}/prompts"
  cp -r "${BUNDLE_DIR}/prompts"/. "${CODEX_HOME}/prompts/"
  info "  prompts/ 심 파일 설치됨"
fi

# ============================================================
# STEP 4 — Python venv + pip install
# ============================================================
info "4/10 단계 — Python 가상 환경 설정 중 …"

# Probe Python ≥ 3.10
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver="$("$candidate" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null || true)"
    major="$("$candidate" -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo 0)"
    minor="$("$candidate" -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)"
    if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
      PYTHON="$(command -v "$candidate")"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  _rollback_step3
  die "Python 3.10 이상을 찾을 수 없습니다.
설치 방법:
  macOS:  brew install python@3.12
  Linux:  sudo apt install python3.12  (또는 dnf/pacman 동등 명령)
  공통:    https://www.python.org/downloads/
설치 후 설치 프로그램을 다시 실행하세요."
fi

PYTHON_VER="$("$PYTHON" --version 2>&1)"
info "  사용 중: $PYTHON ($PYTHON_VER)"

VENV_DIR="${OMR_HOME}/venv"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON" -m venv "$VENV_DIR"
  info "  가상 환경 생성됨: $VENV_DIR"
else
  info "  기존 가상 환경 재사용: $VENV_DIR"
fi

VENV_PY="${VENV_DIR}/bin/python"

# Upgrade pip silently
"$VENV_PY" -m pip install --quiet --upgrade pip

# Install MCP server packages
for pkg_dir in "${OMR_HOME}/mcp/omr_scholar" "${OMR_HOME}/mcp/omr_render"; do
  if [ -d "$pkg_dir" ]; then
    pkg_name="$(basename "$pkg_dir")"
    info "  pip install $pkg_name …"
    "$VENV_PY" -m pip install --quiet -e "$pkg_dir"
  fi
done

# ============================================================
# STEP 5 — Merge config.toml region
# ============================================================
info "5/10 단계 — config.toml 영역 병합 중 …"

CONFIG_TOML="${CODEX_HOME}/config.toml"
# TABLE region (position-independent — appended at END). Reuses the historical
# sentinel pair so a legacy single-combined region (which used these same
# sentinels but also contained the root scalars) is detected & cleanly removed
# by the self-healing strip on upgrade — no table duplication, clean migration.
SENTINEL_START="# >>> oh-my-research (managed) >>>"
SENTINEL_END="# <<< oh-my-research (managed) <<<"
# ROOT-SCALAR region (bare keys only — MUST sit before the first [table] header
# so it parses at the TOML document root, A6 fix). Distinct sentinel pair.
SENTINEL_ROOT_START="# >>> oh-my-research:root (managed) >>>"
SENTINEL_ROOT_END="# <<< oh-my-research:root (managed) <<<"
TMPL_TOML="${BUNDLE_DIR}/config/config.toml.omr-region.tmpl"
TMPL_TOML_ROOT="${BUNDLE_DIR}/config/config.toml.omr-root.tmpl"

# Build the substituted TABLE region
_build_toml_region() {
  local mailto="${1:-}"
  sed \
    -e "s|@@VENV_PY@@|${VENV_PY}|g" \
    -e "s|@@OMR_HOME@@|${OMR_HOME}|g" \
    -e "s|@@OMR_SCHOLAR_MAILTO@@|${mailto}|g" \
    "$TMPL_TOML"
}

# Build the substituted ROOT-SCALAR region (no placeholders today, but keep the
# substitution pipeline identical so future @@…@@ tokens work uniformly).
_build_toml_root_region() {
  sed \
    -e "s|@@VENV_PY@@|${VENV_PY}|g" \
    -e "s|@@OMR_HOME@@|${OMR_HOME}|g" \
    "$TMPL_TOML_ROOT"
}

# Pure-bash self-healing, idempotent sentinel-region strip.
# Removes EVERY start sentinel line, EVERY end sentinel line, and every line
# strictly between a start and its FOLLOWING end — scanning the WHOLE file.
# Orphan/standalone sentinels (start w/o end, end w/o start, duplicates) are
# also removed. A start with no following end is treated as a stray sentinel
# line to delete WITHOUT dropping the subsequent user content (no data loss).
# Result on stdout has ZERO sentinel lines and ZERO managed-region body.
#   $1 = source file (must exist)
#   $2 = start sentinel (exact line)
#   $3 = end   sentinel (exact line)
_strip_all_sentinel_regions() {
  local file="$1" start="$2" end="$3"
  awk -v start="$start" -v end="$end" '
    BEGIN { n = 0 }
    { lines[n++] = $0 }
    END {
      # Pre-compute, for every line, whether a later end sentinel exists.
      has_end_after = 0
      for (i = n - 1; i >= 0; i--) {
        end_after[i] = has_end_after
        if (lines[i] == end) has_end_after = 1
      }
      inside = 0
      for (i = 0; i < n; i++) {
        l = lines[i]
        if (inside) {
          if (l == end) { inside = 0 }      # drop end sentinel, leave region
          # else: drop region body line
          continue
        }
        if (l == start) {
          # Enter region-strip mode ONLY if a matching end follows.
          # Otherwise this is a stray start: drop just this line, keep rest.
          if (end_after[i]) inside = 1
          continue
        }
        if (l == end) continue            # orphan/standalone end: drop it
        print l                            # ordinary user content: keep
      }
    }
  ' "$file"
}

# Idempotent, convergent sentinel-region merge.
# Self-heals ANY prior state (clean / orphan-end / orphan-start / duplicate /
# none / absent), then appends exactly ONE freshly-built region separated by
# exactly one blank line, with no trailing-newline duplication.
# $4 = path to a FILE containing the new region (sentinel lines included).
_merge_sentinel_region() {
  local file="$1"        # target file (may not exist)
  local start="$2"       # sentinel start line (exact string)
  local end="$3"         # sentinel end line (exact string)
  local region_file="$4" # FILE whose contents are the new region

  if [ ! -f "$file" ]; then
    # Create a minimal valid TOML/Markdown stub
    printf '# Codex configuration\n' > "$file"
  fi

  local tmp stripped
  tmp="$(mktemp)"
  stripped="$(mktemp)"

  # 1. Strip every sentinel + managed body anywhere in the file (self-heal).
  _strip_all_sentinel_regions "$file" "$start" "$end" > "$stripped"

  # 2. Drop trailing blank lines so we control the single separator exactly.
  #    (awk: print lines but defer trailing blanks until a non-blank appears.)
  awk '
    /^[[:space:]]*$/ { blanks++; next }
    { while (blanks-- > 0) print ""; blanks = 0; print }
  ' "$stripped" > "$tmp"

  # 3. Append exactly one blank-line separator + the fresh region.
  #    Skip the separator if the stripped content is empty.
  if [ -s "$tmp" ]; then
    printf '\n' >> "$tmp"
  fi
  cat "$region_file" >> "$tmp"

  mv "$tmp" "$file"
  rm -f "$stripped"
}

# Idempotent, convergent ROOT-SCALAR sentinel-region merge.
# Self-heals ANY prior state of the root region (clean / orphan-end /
# orphan-start / duplicate / none / absent) using the SAME A5 strip, then
# inserts exactly ONE freshly-built root region at the TOP of the file —
# before any pre-existing content — so the bare keys parse at the TOML
# document root (never reparented into a user [table]). User content
# (including any leading user root keys) is preserved and follows the
# root region, which is still valid: omr root keys → user root keys → tables.
# $4 = path to a FILE containing the new root region (sentinel lines included).
_merge_root_region() {
  local file="$1"        # target file (may not exist)
  local start="$2"       # root sentinel start line (exact string)
  local end="$3"         # root sentinel end line (exact string)
  local region_file="$4" # FILE whose contents are the new root region

  if [ ! -f "$file" ]; then
    printf '# Codex configuration\n' > "$file"
  fi

  local tmp stripped
  tmp="$(mktemp)"
  stripped="$(mktemp)"

  # 1. Strip every root sentinel + its body anywhere in the file (self-heal).
  _strip_all_sentinel_regions "$file" "$start" "$end" > "$stripped"

  # 2. Drop LEADING blank lines so we control the separator after the region.
  awk 'NF==0 && !seen { next } { seen=1; print }' "$stripped" > "$tmp"
  mv "$tmp" "$stripped"
  tmp="$(mktemp)"

  # 3. Emit the fresh root region FIRST (top of file), then exactly one blank
  #    separator (only if user content remains), then the stripped content.
  cat "$region_file" > "$tmp"
  if [ -s "$stripped" ]; then
    printf '\n' >> "$tmp"
    cat "$stripped" >> "$tmp"
  fi

  mv "$tmp" "$file"
  rm -f "$stripped"
}

# Merge BOTH regions. TABLE region first (appended at END; its strip also
# removes any legacy single-combined region since it shares these sentinels —
# clean upgrade, no table duplication). ROOT region second (inserted at TOP
# so bare keys parse at the TOML document root — A6 fix).
# Determine mailto (may be updated in step 8; use placeholder for now)
_MAILTO_PLACEHOLDER="__PLACEHOLDER__"
_TOML_REGION_FILE="$(mktemp)"
_build_toml_region "$_MAILTO_PLACEHOLDER" > "$_TOML_REGION_FILE"
_merge_sentinel_region "$CONFIG_TOML" "$SENTINEL_START" "$SENTINEL_END" "$_TOML_REGION_FILE"
rm -f "$_TOML_REGION_FILE"

_TOML_ROOT_FILE="$(mktemp)"
_build_toml_root_region > "$_TOML_ROOT_FILE"
_merge_root_region "$CONFIG_TOML" "$SENTINEL_ROOT_START" "$SENTINEL_ROOT_END" "$_TOML_ROOT_FILE"
rm -f "$_TOML_ROOT_FILE"
info "  config.toml 병합 완료: $CONFIG_TOML"

# ============================================================
# STEP 6 — Merge AGENTS.md block
# ============================================================
info "6/10 단계 — AGENTS.md 블록 병합 중 …"

AGENTS_MD="${CODEX_HOME}/AGENTS.md"
TMPL_AGENTS="${BUNDLE_DIR}/config/AGENTS.md.omr-region.tmpl"
AGENTS_START="<!-- omr:start -->"
AGENTS_END="<!-- omr:end -->"

_merge_sentinel_region "$AGENTS_MD" "$AGENTS_START" "$AGENTS_END" "$TMPL_AGENTS"
info "  AGENTS.md 병합 완료: $AGENTS_MD"

# ============================================================
# STEP 7 — Prerequisite probe: R, Quarto, pandoc
# ============================================================
info "7/10 단계 — 필수 프로그램 확인 중 …"

_probe_tool() {
  # Usage: _probe_tool <name> <PATH-cmd> [<abs-candidate> ...]
  # Tries PATH first (via the first positional after name), then each absolute
  # candidate path in order.  Uses the first that responds to --version.
  local name="$1" path_cmd="$2"; shift 2
  local abs_candidates=("$@")
  local found_path="" found_ver=""

  # 1. PATH probe
  if command -v "$path_cmd" >/dev/null 2>&1; then
    found_path="$(command -v "$path_cmd")"
    found_ver="$("$found_path" --version 2>&1 | head -1 || true)"
  fi

  # 2. Per-OS absolute-path fallback (mirrors omr_render/detect.py)
  if [ -z "$found_path" ]; then
    for cand in "${abs_candidates[@]}"; do
      if [ -x "$cand" ]; then
        local ver
        ver="$("$cand" --version 2>&1 | head -1 || true)"
        if [ -n "$ver" ]; then
          found_path="$cand"
          found_ver="$ver"
          break
        fi
      fi
    done
  fi

  printf '%s\t%s\t%s\n' "$name" "${found_path}" "${found_ver}"
}

# Version floor check: returns 0 if version string meets major.minor floor
_ver_meets_floor() {
  local ver_str="$1" floor_major="$2" floor_minor="$3"
  # Extract first two numeric components
  local maj min
  maj="$(printf '%s' "$ver_str" | grep -oE '[0-9]+' | sed -n '1p')"
  min="$(printf '%s' "$ver_str" | grep -oE '[0-9]+' | sed -n '2p')"
  maj="${maj:-0}"; min="${min:-0}"
  if [ "$maj" -gt "$floor_major" ]; then return 0; fi
  if [ "$maj" -eq "$floor_major" ] && [ "$min" -ge "$floor_minor" ]; then return 0; fi
  return 1
}

# Per-OS candidate lists mirror omr_render/detect.py (_known_dirs_r/quarto/pandoc)
_OS="$(uname -s)"
if [ "$_OS" = "Darwin" ]; then
  _R_CANDS=(
    "/usr/local/bin/Rscript"
    "/opt/homebrew/bin/Rscript"
    "/Library/Frameworks/R.framework/Resources/bin/Rscript"
  )
  _QUARTO_CANDS=(
    "/usr/local/bin/quarto"
    "/opt/homebrew/bin/quarto"
    "/Applications/quarto/bin/quarto"
  )
  _PANDOC_CANDS=(
    "/usr/local/bin/pandoc"
    "/opt/homebrew/bin/pandoc"
  )
else
  # Linux / other POSIX
  _R_CANDS=("/usr/local/bin/Rscript" "/usr/bin/Rscript")
  _QUARTO_CANDS=("/usr/local/bin/quarto" "/usr/bin/quarto")
  _PANDOC_CANDS=("/usr/local/bin/pandoc" "/usr/bin/pandoc")
fi

PROBE_R="$(_probe_tool R Rscript "${_R_CANDS[@]}")"
PROBE_QUARTO="$(_probe_tool quarto quarto "${_QUARTO_CANDS[@]}")"
PROBE_PANDOC="$(_probe_tool pandoc pandoc "${_PANDOC_CANDS[@]}")"

R_PATH="$(printf '%s' "$PROBE_R" | cut -f2)"
R_VER="$(printf '%s' "$PROBE_R" | cut -f3)"
QUARTO_PATH="$(printf '%s' "$PROBE_QUARTO" | cut -f2)"
QUARTO_VER="$(printf '%s' "$PROBE_QUARTO" | cut -f3)"
PANDOC_PATH="$(printf '%s' "$PROBE_PANDOC" | cut -f2)"
PANDOC_VER="$(printf '%s' "$PROBE_PANDOC" | cut -f3)"

info "  R:      ${R_PATH:-찾을 수 없음}  ${R_VER}"
info "  Quarto: ${QUARTO_PATH:-찾을 수 없음}  ${QUARTO_VER}"
info "  pandoc: ${PANDOC_PATH:-찾을 수 없음}  ${PANDOC_VER}"

PREREQ_FAIL=false

# R ≥ 4.2
if [ -z "$R_PATH" ]; then
  error "R을 찾을 수 없습니다. https://cran.r-project.org 에서 R ≥ 4.2 를 설치하세요."
  PREREQ_FAIL=true
elif ! _ver_meets_floor "$R_VER" 4 2; then
  error "R 버전이 너무 낮습니다 (현재: $R_VER). R ≥ 4.2 가 필요합니다 — https://cran.r-project.org 에서 업그레이드하세요."
  PREREQ_FAIL=true
fi

# Quarto ≥ 1.4
if [ -z "$QUARTO_PATH" ]; then
  error "Quarto를 찾을 수 없습니다. https://quarto.org/docs/get-started/ 에서 Quarto ≥ 1.4 를 설치하세요."
  PREREQ_FAIL=true
elif ! _ver_meets_floor "$QUARTO_VER" 1 4; then
  error "Quarto 버전이 너무 낮습니다 (현재: $QUARTO_VER). Quarto ≥ 1.4 가 필요합니다 — https://quarto.org 에서 업그레이드하세요."
  PREREQ_FAIL=true
fi

# pandoc ≥ 3.1
if [ -z "$PANDOC_PATH" ]; then
  error "pandoc을 찾을 수 없습니다. https://pandoc.org/installing.html 에서 pandoc ≥ 3.1 을 설치하세요."
  PREREQ_FAIL=true
elif ! _ver_meets_floor "$PANDOC_VER" 3 1; then
  error "pandoc 버전이 너무 낮습니다 (현재: $PANDOC_VER). pandoc ≥ 3.1 이 필요합니다 — https://pandoc.org/installing.html 에서 업그레이드하세요."
  PREREQ_FAIL=true
fi

if $PREREQ_FAIL; then
  die "하나 이상의 필수 프로그램 확인이 실패했습니다 (위 오류 참조).
필요한 도구를 설치한 뒤 설치 프로그램을 다시 실행하세요."
fi

# Write preliminary manifest (updated again in step 10)
mkdir -p "$OMR_HOME"
_MANIFEST="${OMR_HOME}/manifest.json"

# ============================================================
# STEP 8 — Prompt for contact email
# ============================================================
info "8/10 단계 — 학술 API용 연락처 이메일 입력 (polite pool) …"

OMR_SCHOLAR_MAILTO=""
if ! $SKIP_EMAIL && [ -t 0 ]; then
  printf "${BOLD}Unpaywall/CrossRef polite pool에 등록할 연락처 이메일을 입력하세요${RESET}\n"
  printf "(건너뛰려면 Enter — config.toml에서 나중에 추가할 수 있습니다):\n"
  read -r -p "  이메일: " OMR_SCHOLAR_MAILTO || true
  OMR_SCHOLAR_MAILTO="${OMR_SCHOLAR_MAILTO:-}"
fi

if [ -n "$OMR_SCHOLAR_MAILTO" ]; then
  info "  이메일 기록됨: $OMR_SCHOLAR_MAILTO"
  # Re-merge config with actual email
  _TOML_REGION_FILE2="$(mktemp)"
  _build_toml_region "$OMR_SCHOLAR_MAILTO" > "$_TOML_REGION_FILE2"
  _merge_sentinel_region "$CONFIG_TOML" "$SENTINEL_START" "$SENTINEL_END" "$_TOML_REGION_FILE2"
  rm -f "$_TOML_REGION_FILE2"
  info "  config.toml이 이메일로 업데이트되었습니다."
else
  # Remove placeholder line from config if no email given
  # Strip the [mcp_servers.omr_scholar.env] block (no email to write)
  _TOML_REGION_FILE2="$(mktemp)"
  _build_toml_region "" | \
    awk '/^\[mcp_servers\.omr_scholar\.env\]/{skip=1;next} skip && /^OMR_SCHOLAR_MAILTO/{skip=0;next} skip && /^$/{skip=0} {print}' \
    > "$_TOML_REGION_FILE2"
  _merge_sentinel_region "$CONFIG_TOML" "$SENTINEL_START" "$SENTINEL_END" "$_TOML_REGION_FILE2"
  rm -f "$_TOML_REGION_FILE2"
  info "  이메일 미입력 — 건너뜁니다."
fi

# ============================================================
# STEP 9 — "You're set" summary
# ============================================================
info "9/10 단계 — 설치 요약 …"

printf "\n"
printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
printf "${BOLD}  oh-my-research 설치가 완료되었습니다!${RESET}\n"
printf "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
printf "\n"
printf "  ${BOLD}전역 Codex 설정이 기록되었습니다${RESET} (특정 프로필에 한정되지 않는 전역 설정):\n"
printf "    sandbox_mode, approval_policy, [sandbox_workspace_write],\n"
printf "    [mcp_servers.omr_scholar], [mcp_servers.omr_render]\n"
printf "  ※ 위 config 키들은 oh-my-research 전용이 아닌 전역 Codex 설정입니다.\n"
printf "\n"
printf "  ${BOLD}다음 단계:${RESET}\n"
printf "  1. Codex 데스크탑 앱을 엽니다.\n"
printf "  2. Codex 앱의 '/' 스킬 목록에서  ${BOLD}\$omr-doctor${RESET}  (설정 점검)을 실행하세요.\n"
printf "     '설정 점검'이 EV5 세션-전역 MCP 게이트를 통과해야\n"
printf "     설치 완료로 간주됩니다\n"
printf "     (omr_scholar + omr_render 버전 도구가 bare codex 실행 프롬프트에서\n"
printf "     접근 가능해야 합니다).\n"
printf "  3. 빈 연구 폴더를 워크스페이스로 생성/열고,\n"
printf "     '/' 스킬 목록에서  ${BOLD}\$omr-start${RESET}  (연구 프로젝트 시작)을 실행하세요.\n"
printf "\n"
printf "  스킬 설치 위치:   $SKILLS_DIR\n"
printf "  번들 설치 위치:   $OMR_HOME\n"
printf "  설정 병합 위치:   $CONFIG_TOML\n"
printf "  AGENTS.md 위치:   $AGENTS_MD\n"
printf "  백업 위치:        $BACKUP_DIR\n"
printf "\n"

# ============================================================
# STEP 10 — Write manifest.json
# ============================================================
info "10/10 단계 — 매니페스트 작성 중 …"

# Collect installed skill dirs
_skill_entries=""
for skill_dst in "${_COPIED_SKILLS[@]}"; do
  _skill_entries="${_skill_entries}    \"${skill_dst}\",\n"
done
_skill_entries="${_skill_entries%,\\n}"  # remove trailing comma

# Collect files under OMR_HOME
_omr_files=""
if [ -d "$OMR_HOME" ]; then
  while IFS= read -r -d '' f; do
    _omr_files="${_omr_files}    \"${f}\",\n"
  done < <(find "$OMR_HOME" -type f -print0 | sort -z)
fi
_omr_files="${_omr_files%,\\n}"

cat > "$_MANIFEST" <<EOF
{
  "version": "$(cat "${OMR_HOME}/VERSION" 2>/dev/null || echo '0.1.0')",
  "installed_at": "${TS}",
  "codex_home": "${CODEX_HOME}",
  "skills_dir": "${SKILLS_DIR}",
  "omr_home": "${OMR_HOME}",
  "config_toml": "${CONFIG_TOML}",
  "agents_md": "${AGENTS_MD}",
  "backup_dir": "${BACKUP_DIR}",
  "venv_python": "${VENV_PY}",
  "prereqs": {
    "r":      { "path": "${R_PATH}",      "version": "${R_VER}" },
    "quarto": { "path": "${QUARTO_PATH}", "version": "${QUARTO_VER}" },
    "pandoc": { "path": "${PANDOC_PATH}", "version": "${PANDOC_VER}" }
  },
  "skill_dirs": [
$(printf '%b' "$_skill_entries")
  ],
  "omr_files": [
$(printf '%b' "$_omr_files")
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
EOF

info "  매니페스트 작성 완료: $_MANIFEST"
info "설치가 완료되었습니다."
