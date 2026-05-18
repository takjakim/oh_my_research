#!/usr/bin/env bash
# ============================================================
#  oh-my-research — install.command
#  macOS 더블클릭 실행기 (Gatekeeper 호환 래퍼).
#
#  참고 (Gatekeeper): macOS가 "신원 불명 개발자"로 이 파일을
#  차단하는 경우, 시스템 설정 → 개인 정보 보호 및 보안 → 아래로
#  스크롤하여 "그래도 열기"를 클릭하거나, 터미널에서 다음과 같이
#  한 번 실행하세요:
#    bash install.sh
# ============================================================

# Change to the directory containing this script so relative
# paths in install.sh resolve correctly.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Keep the Terminal window open long enough to read the output.
exec bash "${SCRIPT_DIR}/install.sh" "$@"
