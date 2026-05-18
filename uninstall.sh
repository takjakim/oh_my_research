#!/usr/bin/env bash
# ============================================================
#  oh-my-research — uninstall.sh
#  센티넬 영역 외부의 사용자 편집 내용을 건드리지 않고
#  oh-my-research 자산을 제거합니다.
#
#  설계 (M2):
#    - ~/.agents/skills/에서 omr-* 스킬 디렉토리 삭제
#    - ~/.codex/omr/ 번들 + 선택적 prompts 심 파일 삭제
#    - config.toml 및 AGENTS.md에서 omr 센티넬 영역만 제거
#      (해당 파일 전체를 덮어쓰지 않음)
#    - 센티넬 마커가 없거나 손상된 경우에만 백업 복원 제안
# ============================================================
set -euo pipefail

if [ -t 1 ]; then
  RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
  BOLD='\033[1m'; RESET='\033[0m'
else
  RED=''; YELLOW=''; GREEN=''; BOLD=''; RESET=''
fi

info()  { printf "${GREEN}[omr-uninstall]${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}[omr-uninstall 경고]${RESET} %s\n" "$*"; }
error() { printf "${RED}[omr-uninstall 오류]${RESET} %s\n" "$*" >&2; }
die()   { error "$*"; exit 1; }

# ── paths ────────────────────────────────────────────────────
CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
SKILLS_DIR="${HOME}/.agents/skills"
OMR_HOME="${CODEX_HOME}/omr"
CONFIG_TOML="${CODEX_HOME}/config.toml"
AGENTS_MD="${CODEX_HOME}/AGENTS.md"

# TABLE region sentinels (also match a legacy single-combined region).
SENTINEL_TOML_START="# >>> oh-my-research (managed) >>>"
SENTINEL_TOML_END="# <<< oh-my-research (managed) <<<"
# ROOT-SCALAR region sentinels (A6 split — separate top-of-file region).
SENTINEL_TOML_ROOT_START="# >>> oh-my-research:root (managed) >>>"
SENTINEL_TOML_ROOT_END="# <<< oh-my-research:root (managed) <<<"
SENTINEL_AGENTS_START="<!-- omr:start -->"
SENTINEL_AGENTS_END="<!-- omr:end -->"

# ── confirmation ─────────────────────────────────────────────
printf "\n${BOLD}oh-my-research 설치 제거 프로그램${RESET}\n"
printf "다음 위치에서 oh-my-research 자산을 제거합니다:\n"
printf "  스킬:    $SKILLS_DIR/omr-*\n"
printf "  번들:    $OMR_HOME\n"
printf "  설정:    $CONFIG_TOML  (센티넬 영역만)\n"
printf "  Agents:  $AGENTS_MD   (센티넬 영역만)\n\n"

if [ -t 0 ]; then
  read -r -p "계속하시겠습니까? [y/N] " _confirm
  case "$_confirm" in
    [yY]|[yY][eE][sS]) ;;
    *) info "취소되었습니다."; exit 0 ;;
  esac
fi

# ── helper: self-healing sentinel strip ──────────────────────
# Removes EVERY start sentinel line, EVERY end sentinel line, and every line
# strictly between a start and its FOLLOWING end — whole file. Orphan /
# standalone / duplicate sentinels are also removed. A start with no following
# end is a stray line to delete WITHOUT dropping subsequent user content.
# Net: ZERO sentinel lines + ZERO managed-region body remain; all other user
# content preserved in original order.
#   return 0 : at least one sentinel line was found & removed (clean strip)
#   return 1 : NO sentinel markers present at all → corruption-fallback signal
_strip_sentinel_region() {
  local file="$1" start="$2" end="$3"

  if [ ! -f "$file" ]; then
    warn "  $file 을 찾을 수 없습니다 — 건너뜁니다."
    return 0
  fi

  if ! grep -qF "$start" "$file" && ! grep -qF "$end" "$file"; then
    warn "  $file 에서 센티넬 마커를 찾을 수 없습니다."
    return 1  # signal: nothing managed here → possible corruption/overwrite
  fi

  local tmp
  tmp="$(mktemp)"

  # Self-heal: drop ALL sentinels + region bodies, keep everything else.
  # A stray start (no following end) is deleted but the lines after it survive.
  awk -v start="$start" -v end="$end" '
    { lines[n++] = $0 }
    END {
      has_end_after = 0
      for (i = n - 1; i >= 0; i--) {
        end_after[i] = has_end_after
        if (lines[i] == end) has_end_after = 1
      }
      inside = 0
      for (i = 0; i < n; i++) {
        l = lines[i]
        if (inside) {
          if (l == end) inside = 0
          continue
        }
        if (l == start) {
          if (end_after[i]) inside = 1
          continue
        }
        if (l == end) continue
        print l
      }
    }
  ' "$file" > "$tmp"

  # Trim BOTH leading and trailing blank lines left where the region sat
  # (a top-of-file ROOT region leaves a leading blank after its separator;
  # a tail TABLE region leaves trailing blanks). Interior blanks preserved.
  local tmp2
  tmp2="$(mktemp)"
  awk '
    /^[[:space:]]*$/ { if (!seen) next; blanks++; next }
    { while (blanks-- > 0) print ""; blanks = 0; seen = 1; print }
  ' "$tmp" > "$tmp2"
  rm -f "$tmp"

  mv "$tmp2" "$file"
  info "  $file 에서 센티넬 영역이 제거되었습니다 (고아 마커 포함 자가 치유)."
  return 0
}

# ── helper: offer backup restore (corruption fallback only) ──
_offer_backup_restore() {
  local target_file="$1" backup_dir_base="${CODEX_HOME}/backups/omr"

  warn "$target_file 의 센티넬 마커가 없거나 손상되었습니다."
  warn "손상된 파일 복구 수단으로 백업 복원을 사용할 수 있습니다."

  if [ ! -d "$backup_dir_base" ]; then
    warn "$backup_dir_base 에 백업이 없습니다 — 복원 불가."
    return
  fi

  # Find the most-recent backup
  local latest
  latest="$(ls -1 "$backup_dir_base" 2>/dev/null | sort | tail -1)"
  if [ -z "$latest" ]; then
    warn "백업 타임스탬프를 찾을 수 없습니다."
    return
  fi

  local backup_file="${backup_dir_base}/${latest}/$(basename "$target_file")"
  if [ ! -f "$backup_file" ]; then
    warn "$backup_file 에 백업 파일이 없습니다."
    return
  fi

  if [ -t 0 ]; then
    printf "\n${YELLOW}백업 ${latest} 에서 $target_file 을 복원하시겠습니까?${RESET}\n"
    printf "(현재 파일을 덮어씁니다 — 파일이 손상된 경우에만 사용하세요)\n"
    read -r -p "복원? [y/N] " _r
    case "$_r" in
      [yY]|[yY][eE][sS])
        cp "$backup_file" "$target_file"
        info "  $target_file 이 $backup_file 에서 복원되었습니다."
        ;;
      *)
        info "  $target_file 백업 복원을 건너뜁니다."
        ;;
    esac
  else
    warn "비대화형 모드 — $target_file 백업 복원 프롬프트를 건너뜁니다."
  fi
}

# ── 1. Remove skill dirs ─────────────────────────────────────
info "$SKILLS_DIR 에서 omr-* 스킬 디렉토리를 제거하는 중 …"
_removed_skills=0
if [ -d "$SKILLS_DIR" ]; then
  for skill_dir in "${SKILLS_DIR}"/omr-*; do
    if [ -d "$skill_dir" ]; then
      rm -rf "$skill_dir"
      info "  삭제됨: $skill_dir"
      _removed_skills=$((_removed_skills + 1))
    fi
  done
fi
[ $_removed_skills -eq 0 ] && warn "  $SKILLS_DIR 에서 omr-* 스킬 디렉토리를 찾을 수 없습니다."

# ── 2. Remove bundle + shims ─────────────────────────────────
info "$OMR_HOME 번들을 제거하는 중 …"
if [ -d "$OMR_HOME" ]; then
  rm -rf "$OMR_HOME"
  info "  삭제됨: $OMR_HOME"
else
  warn "  $OMR_HOME 을 찾을 수 없습니다 — 건너뜁니다."
fi

# Remove prompts shims (only omr-* files, to avoid deleting user shims)
PROMPTS_DIR="${CODEX_HOME}/prompts"
if [ -d "$PROMPTS_DIR" ]; then
  info "$PROMPTS_DIR 에서 omr prompts 심 파일을 제거하는 중 …"
  for shim in omr-start.md omr-lit.md omr-analyze.md omr-write.md omr-status.md; do
    f="${PROMPTS_DIR}/${shim}"
    if [ -f "$f" ]; then
      rm -f "$f"
      info "  삭제됨: $f"
    fi
  done
fi

# ── 3. Strip BOTH sentinel regions from config.toml ──────────
# Order: TABLE region first (also clears any legacy single-combined region,
# same sentinels), then ROOT-SCALAR region (top-of-file). Corruption fallback
# is offered ONLY when NEITHER region has any sentinel present at all.
info "$CONFIG_TOML 에서 관리 영역을 제거하는 중 (테이블 + 루트) …"
_toml_table_present=true
_toml_root_present=true
_strip_sentinel_region "$CONFIG_TOML" "$SENTINEL_TOML_START" "$SENTINEL_TOML_END" \
  || _toml_table_present=false
_strip_sentinel_region "$CONFIG_TOML" "$SENTINEL_TOML_ROOT_START" "$SENTINEL_TOML_ROOT_END" \
  || _toml_root_present=false
if ! $_toml_table_present && ! $_toml_root_present; then
  # No omr sentinels of EITHER kind → possible corruption/overwrite.
  _offer_backup_restore "$CONFIG_TOML"
fi

# ── 4. Strip sentinel block from AGENTS.md ───────────────────
info "$AGENTS_MD 에서 관리 블록을 제거하는 중 …"
if ! _strip_sentinel_region "$AGENTS_MD" "$SENTINEL_AGENTS_START" "$SENTINEL_AGENTS_END"; then
  _offer_backup_restore "$AGENTS_MD"
fi

# ── Summary ──────────────────────────────────────────────────
printf "\n${BOLD}${GREEN}oh-my-research 설치가 제거되었습니다.${RESET}\n"
printf "센티넬 영역 외부의 사용자 편집 내용은 보존되었습니다.\n"
printf "백업 위치: ${CODEX_HOME}/backups/omr/\n\n"
