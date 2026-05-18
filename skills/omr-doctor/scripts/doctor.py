#!/usr/bin/env python3
"""omr-doctor environment probe.

Pure standard library (Python >= 3.10). No third-party imports.

Reports, per tool: presence, version, absolute path.
Enforces version floors (HARD FAIL):  R >= 4.2, Quarto >= 1.4, pandoc >= 3.1.
Classifies the MCP privilege model (render.classify_privilege semantics).
Runs the EV5 session-global MCP gate: a bare `codex exec` prompt invoking NO
omr skill that calls omr_scholar's and omr_render's `version` tool, and asserts
both appear under the app's built-in /mcp.

Degrades gracefully: if the `codex` CLI is absent, the EV5/privilege checks are
reported SKIPPED (never a crash). Exit code 0 only if no HARD FAIL and EV5 did
not FAIL (SKIPPED is tolerated).
"""

from __future__ import annotations

import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

# (display name, executable, version flag args, floor as (major, minor) or None)
# HARD-FAIL gating is UNCHANGED from prior fixes: R/Quarto/pandoc enforce a
# floor (FAIL on miss/below-floor/unparseable); python3 floor stays None so
# its HARD-FAIL gating behavior is exactly as before (WARN-only on absence).
# A10 guidance/remediation uses a SEPARATE advisory floor (_GUIDANCE_FLOOR)
# so a stale/missing python3 still gets an exact copy-paste command without
# altering the existing exit-code gate.
TOOLS: list[tuple[str, str, list[str], tuple[int, int] | None]] = [
    ("R", "Rscript", ["--version"], (4, 2)),
    ("quarto", "quarto", ["--version"], (1, 4)),
    ("pandoc", "pandoc", ["--version"], (3, 1)),
    ("python3", "python3", ["--version"], None),
]

# Plan A10 min-version floors for GUIDANCE/remediation only (does NOT change
# probe_tools' exit-code HARD FAIL gate). Python ≥3.10 surfaces a copy-paste
# command for a too-old/absent python3 without making it a hard gate.
_GUIDANCE_FLOOR: dict[str, tuple[int, int]] = {
    "R": (4, 2),
    "quarto": (1, 4),
    "pandoc": (3, 1),
    "python3": (3, 10),
}

# ── A10: per-OS prerequisite remediation ────────────────────────────────────
# Only OS package managers install these — R/Python cannot install each other.
# macOS = Homebrew, Windows = winget. Items needing an admin/sudo password
# (notably the Quarto macOS cask) CANNOT be automated by this script/agent
# (interactive sudo) — we print the exact command + plain reason instead.
#
# "tool" key = the display name used in TOOLS / probe results.
_PKG_MGR_ABSENT_MACOS = (
    "Homebrew(brew)가 설치되어 있지 않습니다. 먼저 Homebrew를 설치하세요: "
    "https://brew.sh  (설치 명령은 공식 사이트의 안내를 따르세요)"
)
_PKG_MGR_ABSENT_WINDOWS = (
    "winget(앱 설치 관리자)을 찾을 수 없습니다. Microsoft Store에서 "
    "'앱 설치 관리자(App Installer)'를 설치하거나 "
    "https://aka.ms/getwinget 를 참조하세요"
)

# macOS: copy-paste brew command per tool. needs_admin=True ⇒ NEVER auto-run.
_MACOS_REMED: dict[str, tuple[str, bool, str]] = {
    # tool: (exact command, needs_admin, plain-language note)
    "python3": ("brew install python", False, ""),
    "R": ("brew install r", False, ""),
    "pandoc": ("brew install pandoc", False, ""),
    "quarto": (
        "brew install --cask quarto  # 관리자 비밀번호 필요 — 본인이 직접 실행",
        True,
        "관리자 비밀번호 필요로 자동화 불가, 직접 실행하세요",
    ),
}

# Windows: widely-valid winget IDs (-e exact, --id). Canonical download URLs
# given as a fallback in case a winget source/ID is unavailable.
_WINDOWS_REMED: dict[str, tuple[str, bool, str]] = {
    "python3": (
        "winget install -e --id Python.Python.3.12"
        "  # 또는 https://www.python.org/downloads/",
        False,
        "",
    ),
    "R": (
        "winget install -e --id RProject.R"
        "  # 또는 https://cran.r-project.org",
        False,
        "",
    ),
    "pandoc": (
        "winget install -e --id JohnMacFarlane.Pandoc"
        "  # 또는 https://pandoc.org/installing.html",
        False,
        "",
    ),
    "quarto": (
        "winget install -e --id Posit.Quarto"
        "  # 또는 https://quarto.org/docs/get-started/",
        False,
        "",
    ),
}

# brew formula name per tool (no-sudo, non-cask installable subset).
_BREW_FORMULA = {"python3": "python", "R": "r", "pandoc": "pandoc"}
# winget ID per tool (non-elevated installable subset).
_WINGET_ID = {
    "python3": "Python.Python.3.12",
    "R": "RProject.R",
    "pandoc": "JohnMacFarlane.Pandoc",
    "quarto": "Posit.Quarto",
}

# Generous wall-clock so a pkg-manager install never hangs a terminal.
_PREREQ_TIMEOUT = int(os.environ.get("OMR_DOCTOR_PREREQ_TIMEOUT", "900"))


def _remed_table() -> dict[str, tuple[str, bool, str]]:
    """Return the per-OS {tool: (command, needs_admin, note)} mapping."""
    if platform.system() == "Windows":
        return _WINDOWS_REMED
    # macOS is the primary no-sudo target; Linux falls back to the macOS
    # guidance shape but the consent bootstrap only auto-runs when `brew`
    # actually resolves (Linuxbrew) — otherwise guidance only.
    return _MACOS_REMED


def _known_candidates_r() -> list[str]:
    sysname = platform.system()
    if sysname == "Windows":
        cands: list[str] = []
        for pat in (
            r"C:\Program Files\R\R-*\bin\Rscript.exe",
            r"C:\Program Files\R\R-*\bin\x64\Rscript.exe",
        ):
            cands += sorted(glob.glob(pat))
        return cands
    if sysname == "Darwin":
        return [
            "/usr/local/bin/Rscript",
            "/opt/homebrew/bin/Rscript",
            "/Library/Frameworks/R.framework/Resources/bin/Rscript",
        ]
    # Linux / other POSIX
    return ["/usr/local/bin/Rscript", "/usr/bin/Rscript"]


def _known_candidates_quarto() -> list[str]:
    sysname = platform.system()
    if sysname == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        cands: list[str] = []
        if local:
            cands.append(os.path.join(local, "Programs", "Quarto", "bin", "quarto.exe"))
        cands.append(r"C:\Program Files\Quarto\bin\quarto.exe")
        return cands
    if sysname == "Darwin":
        return [
            "/usr/local/bin/quarto",
            "/opt/homebrew/bin/quarto",
            "/Applications/quarto/bin/quarto",
        ]
    return ["/usr/local/bin/quarto", "/usr/bin/quarto"]


def _known_candidates_pandoc() -> list[str]:
    sysname = platform.system()
    if sysname == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        cands: list[str] = []
        if local:
            cands.append(os.path.join(local, "Pandoc", "pandoc.exe"))
        cands.append(r"C:\Program Files\Pandoc\pandoc.exe")
        return cands
    if sysname == "Darwin":
        return ["/usr/local/bin/pandoc", "/opt/homebrew/bin/pandoc"]
    return ["/usr/local/bin/pandoc", "/usr/bin/pandoc"]


_CANDIDATE_FACTORIES = {
    "Rscript": _known_candidates_r,
    "quarto": _known_candidates_quarto,
    "pandoc": _known_candidates_pandoc,
}


def _find_candidates(executable: str) -> list[str]:
    """Return ordered absolute-path candidates: PATH hit first, then per-OS known dirs."""
    found: list[str] = []
    which = shutil.which(executable)
    if which:
        found.append(os.path.realpath(which))
    factory = _CANDIDATE_FACTORIES.get(executable)
    if factory:
        for p in factory():
            if os.path.isfile(p):
                rp = os.path.realpath(p)
                if rp not in found:
                    found.append(rp)
    return found

PASS, FAIL, SKIP, WARN = "PASS", "FAIL", "SKIPPED", "WARN"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    # A10: tool display-names whose initial probe FAILed but were
    # consent-installed and RE-PROBED to PASS. Their original probe FAIL is
    # superseded for the exit-code/verdict gate (spec: missing prereq ⇒
    # not-OK/1 UNLESS consent-installed→reprobe PASS). The original check
    # line stays visible for transparency.
    resolved_prereqs: set[str] = field(default_factory=set)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(Check(name, status, detail))

    def mark_prereq_resolved(self, tool: str) -> None:
        self.resolved_prereqs.add(tool)

    def has_hard_fail(self) -> bool:
        for c in self.checks:
            if c.status != FAIL:
                continue
            # A consent-installed-then-reprobe-PASS prereq's original probe
            # FAIL is superseded (its name is a bare TOOLS display-name).
            if c.name in self.resolved_prereqs and not c.name.startswith(
                "선수도구"
            ):
                continue
            return True
        return False

    def render(self) -> str:
        width = max((len(c.name) for c in self.checks), default=4)
        lines = ["omr-doctor — 환경 및 MCP 보고서", "=" * 44]
        for c in self.checks:
            line = f"[{c.status:<7}] {c.name.ljust(width)}"
            if c.detail:
                line += f"  {c.detail}"
            lines.append(line)
        lines.append("=" * 44)
        verdict = "OK 아님" if self.has_hard_fail() else "OK"
        if any(c.status == FAIL and c.name.startswith("EV5") for c in self.checks):
            verdict = "OK 아님"
        lines.append(f"판정: {verdict}")
        return "\n".join(lines)


_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def _parse_version(text: str) -> tuple[int, int, int] | None:
    m = _VERSION_RE.search(text or "")
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3)) if m.group(3) else 0
    return (major, minor, patch)


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    """Run a command with stdin closed so it can never block on input.

    On timeout the process is killed and a non-zero rc is returned so the
    probe degrades gracefully instead of hanging a terminal.
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return 124, out, f"{err}\n[timed out after {timeout}s]"
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        return 1, "", str(exc)


def probe_tools(report: Report) -> list[str]:
    """Probe each prerequisite tool; preserve the existing HARD-FAIL gating
    (missing/below-floor/unparseable ⇒ FAIL when a floor exists, WARN
    otherwise — unchanged behavior).

    Returns the ordered list of tool display-names that are MISSING or
    below-floor or unparseable, so the caller can print exact per-OS
    copy-paste remediation commands (A10 guidance, always-on) and optionally
    offer the consent-gated bootstrap.
    """
    needs_remediation: list[str] = []
    for name, executable, args, floor in TOOLS:
        # Build candidate list: PATH first, then per-OS known install dirs.
        candidates = _find_candidates(executable)

        gfloor = _GUIDANCE_FLOOR.get(name)

        if not candidates:
            status = FAIL if floor else WARN
            report.add(name, status, "PATH 또는 알려진 설치 경로에서 찾을 수 없음")
            needs_remediation.append(name)
            continue

        # Try each candidate in order; use the first that yields a parseable version.
        resolved_path: str | None = None
        ver: tuple[int, int, int] | None = None
        for cand in candidates:
            rc, out, err = _run([cand, *args])
            parsed = _parse_version(out) or _parse_version(err)
            if parsed is not None:
                resolved_path = os.path.realpath(cand)
                ver = parsed
                break

        if resolved_path is None:
            # Found candidate(s) but none returned a parseable version — HARD FAIL per spec.
            abspath = os.path.realpath(candidates[0])
            status = FAIL if floor else WARN
            suffix = " (HARD FAIL)" if floor else ""
            report.add(name, status, f"{abspath} (버전 알 수 없음){suffix}")
            needs_remediation.append(name)
            continue

        vstr = ".".join(str(p) for p in ver)
        if floor is not None and (ver[0], ver[1]) < floor:
            need = f"{floor[0]}.{floor[1]}"
            report.add(
                name,
                FAIL,
                f"{resolved_path} v{vstr} < 필요 버전 {need} (HARD FAIL)",
            )
            needs_remediation.append(name)
        elif gfloor is not None and (ver[0], ver[1]) < gfloor:
            # Below the A10 advisory floor (e.g. python3 < 3.10): NOT a hard
            # gate change — report WARN and surface a copy-paste command.
            need = f"{gfloor[0]}.{gfloor[1]}"
            report.add(
                name,
                WARN,
                f"{resolved_path} v{vstr} < 권장 버전 {need} (A10 안내)",
            )
            needs_remediation.append(name)
        else:
            report.add(name, PASS, f"{resolved_path} v{vstr}")
    return needs_remediation


def _have_pkg_manager() -> tuple[bool, str]:
    """Return (present?, manager-name) for the detected OS package manager."""
    mgr = "winget" if platform.system() == "Windows" else "brew"
    return (shutil.which(mgr) is not None, mgr)


def _print_guidance(needs: list[str]) -> None:
    """A10 (ALWAYS): for each missing/below-floor tool print the EXACT
    copy-paste command for the detected OS. Korean, concise, copy-paste-ready.
    Items needing admin/sudo are printed but flagged as not-automatable.
    """
    remed = _remed_table()
    have_mgr, mgr = _have_pkg_manager()
    print()
    print("선수도구 설치 안내 (복사-붙여넣기)")
    print("-" * 44)
    if not have_mgr:
        pointer = (
            _PKG_MGR_ABSENT_WINDOWS
            if platform.system() == "Windows"
            else _PKG_MGR_ABSENT_MACOS
        )
        print(f"  ! {pointer}")
        print()
    for name in needs:
        cmd, needs_admin, note = remed.get(name, ("(설치 명령 없음)", False, ""))
        print(f"  [{name}]")
        print(f"    {cmd}")
        if needs_admin and note:
            print(f"    └─ 주의: {note}")
    print("-" * 44)


def _pkg_install(mgr: str, tool: str) -> tuple[int, str, str]:
    """Run the detected pkg manager for ONE no-sudo tool. Output captured;
    time-bounded so it never hangs. NEVER used for admin/sudo items.
    """
    if mgr == "brew":
        formula = _BREW_FORMULA[tool]
        return _run(["brew", "install", formula], timeout=_PREREQ_TIMEOUT)
    # winget: non-interactive, accept agreements; non-elevated subset only.
    wid = _WINGET_ID[tool]
    return _run(
        [
            "winget",
            "install",
            "-e",
            "--id",
            wid,
            "--accept-source-agreements",
            "--accept-package-agreements",
        ],
        timeout=_PREREQ_TIMEOUT,
    )


def _reprobe_tool(name: str) -> tuple[str, str]:
    """Re-run the floor check for a single tool after an install attempt.
    Returns (status, detail) mirroring probe_tools' verdict semantics.
    """
    spec = next((t for t in TOOLS if t[0] == name), None)
    if spec is None:
        return WARN, "알 수 없는 도구"
    _, executable, args, floor = spec
    gfloor = _GUIDANCE_FLOOR.get(name)
    candidates = _find_candidates(executable)
    if not candidates:
        return (FAIL if floor else WARN), "여전히 찾을 수 없음"
    for cand in candidates:
        rc, out, err = _run([cand, *args])
        parsed = _parse_version(out) or _parse_version(err)
        if parsed is not None:
            vstr = ".".join(str(p) for p in parsed)
            if floor is not None and (parsed[0], parsed[1]) < floor:
                need = f"{floor[0]}.{floor[1]}"
                return FAIL, f"{os.path.realpath(cand)} v{vstr} < {need} (HARD FAIL)"
            if gfloor is not None and (parsed[0], parsed[1]) < gfloor:
                need = f"{gfloor[0]}.{gfloor[1]}"
                return FAIL, f"{os.path.realpath(cand)} v{vstr} < {need} (A10 권장 미달)"
            return PASS, f"{os.path.realpath(cand)} v{vstr}"
    return (FAIL if floor else WARN), f"{os.path.realpath(candidates[0])} (버전 알 수 없음)"


def bootstrap_prereqs(report: Report, needs: list[str], want_fix_prereqs: bool) -> None:
    """A10 consent bootstrap. ALWAYS prints exact per-OS guidance first.

    Then, ONLY with explicit consent (the `--fix-prereqs` flag OR an
    interactive TTY y/N prompt — mirrors A9 exactly), auto-installs the
    NO-SUDO subset via the detected package manager:
      - macOS: `brew install` python/r/pandoc (only the missing ones).
        Quarto cask is NEVER auto-run (interactive sudo) — its exact command
        + admin-password reason is printed instead.
      - Windows: `winget install` the non-elevated missing ones.
      - pkg manager absent ⇒ official install pointer, install nothing.
    Non-TTY without the flag ⇒ guidance ONLY, NO install (A9 "consent ≠
    silent"). After any install attempt the tool is RE-PROBED and PASS/FAIL
    reported per tool with the manual command + stderr tail on failure.
    """
    if not needs:
        return

    # (1) ALWAYS: exact per-OS copy-paste guidance.
    _print_guidance(needs)

    # (2) Consent decision — identical shape to A9's knitr/rmarkdown path.
    consent = False
    if want_fix_prereqs:
        consent = True
    elif sys.stdin is not None and sys.stdin.isatty():
        try:
            sys.stdout.write("누락 선수도구를 설치할까요? [y/N]: ")
            sys.stdout.flush()
            answer = sys.stdin.readline().strip()
        except (EOFError, OSError):
            answer = ""
        consent = answer in ("y", "Y", "예")

    if not consent:
        # Non-TTY w/o flag, or declined: guidance already printed; no install.
        report.add(
            "선수도구 부트스트랩",
            SKIP,
            "동의 없음 (비대화형 + --fix-prereqs 미지정 또는 거부) — 안내만 제공",
        )
        return

    have_mgr, mgr = _have_pkg_manager()
    if not have_mgr:
        # pkg manager absent: pointer only, install nothing.
        pointer = (
            _PKG_MGR_ABSENT_WINDOWS
            if platform.system() == "Windows"
            else _PKG_MGR_ABSENT_MACOS
        )
        report.add(
            "선수도구 부트스트랩",
            FAIL,
            f"{mgr} 미설치로 자동 설치 불가 — {pointer}",
        )
        return

    remed = _remed_table()
    auto_subset = _BREW_FORMULA if mgr == "brew" else _WINGET_ID
    attempted_any = False
    for name in needs:
        cmd, needs_admin, note = remed.get(name, ("", False, ""))
        if needs_admin or name not in auto_subset:
            # Admin/sudo (e.g. macOS Quarto cask): NEVER auto-run.
            report.add(
                f"선수도구 {name}",
                FAIL,
                f"자동 설치 제외 — 직접 실행: {cmd}"
                + (f" ({note})" if note else ""),
            )
            continue
        attempted_any = True
        rc, out, err = _pkg_install(mgr, name)
        status, detail = _reprobe_tool(name)
        if status == PASS:
            report.add(f"선수도구 {name}", PASS, f"설치/재검증 완료 — {detail}")
            # Supersede the original probe FAIL for the exit-code gate.
            report.mark_prereq_resolved(name)
        else:
            tail = " | ".join((err or "").strip().splitlines()[-3:]) or "(stderr 없음)"
            report.add(
                f"선수도구 {name}",
                FAIL,
                f"설치 실패 (rc={rc}): {tail[:160]} — 수동: {cmd}",
            )
    if not attempted_any:
        report.add(
            "선수도구 부트스트랩",
            WARN,
            "자동 설치 가능한 누락 도구 없음 (admin 필요 항목은 직접 실행)",
        )


# A9: render infra ONLY. We probe/consent-install exactly knitr+rmarkdown
# (Quarto's knitr engine needs them to render any .qmd R chunk). Statistical
# packages (car/jsonlite/lme4/...) are NEVER probed or auto-installed here:
# the MVP/examples use base-R/stats only (AC-enforced), and any beyond-MVP
# package stays explicit-approval per plan §4.4 with sessionInfo notes.
_R_PKGS = ("knitr", "rmarkdown")
_R_PKG_REMEDIATION = (
    "Rscript -e 'install.packages(c(\"knitr\",\"rmarkdown\"), "
    "repos=\"https://cloud.r-project.org\")'"
)
# Generous wall-clock for a CRAN install so it never hangs a terminal.
_R_INSTALL_TIMEOUT = int(os.environ.get("OMR_DOCTOR_R_INSTALL_TIMEOUT", "600"))


def _resolved_rscript() -> str | None:
    """Reuse the existing per-OS Rscript detection (probe_tools' resolver).

    Returns the first candidate that yields a parseable version AND meets the
    R version floor; otherwise None so the knitr/rmarkdown probe is skipped
    (the existing R FAIL already covers an absent/below-floor Rscript — we do
    not double-fail or crash).
    """
    floor = (4, 2)
    for cand in _find_candidates("Rscript"):
        rc, out, err = _run([cand, "--version"])
        parsed = _parse_version(out) or _parse_version(err)
        if parsed is None:
            continue
        if (parsed[0], parsed[1]) < floor:
            continue
        return os.path.realpath(cand)
    return None


def _probe_r_pkgs(rscript: str) -> dict[str, bool] | None:
    """Return {'knitr': bool, 'rmarkdown': bool} or None if unparseable."""
    expr = (
        'cat(requireNamespace("knitr",quietly=TRUE), '
        'requireNamespace("rmarkdown",quietly=TRUE))'
    )
    rc, out, err = _run([rscript, "-e", expr])
    toks = re.findall(r"TRUE|FALSE", (out or "") + " " + (err or ""))
    if len(toks) < 2:
        return None
    return {"knitr": toks[0] == "TRUE", "rmarkdown": toks[1] == "TRUE"}


def _r_install_pkgs(rscript: str) -> tuple[int, str, str]:
    """Consent-gated install of EXACTLY knitr+rmarkdown into the user R lib."""
    repo = os.environ.get("OMR_CRAN_REPO", "https://cloud.r-project.org")
    expr = (
        'install.packages(c("knitr","rmarkdown"), repos="%s")' % repo
    )
    return _run([rscript, "-e", expr], timeout=_R_INSTALL_TIMEOUT)


def probe_r_packages(report: Report, want_fix: bool) -> None:
    """A9: probe knitr+rmarkdown; missing ⇒ NOT OK (blocks Stage 3/4 render
    like Quarto-absent). Consent-gated auto-install of ONLY those two via
    --fix or an interactive TTY prompt; NEVER silent.
    """
    report.add(
        "R 패키지 정책",
        PASS,
        "통계는 base-R/stats만 사용; knitr/rmarkdown 외 통계 패키지는 "
        "자동 설치하지 않음 (A9)",
    )

    rscript = _resolved_rscript()
    if rscript is None:
        # Rscript absent/below-floor: existing R FAIL already covers it.
        report.add(
            "R 패키지 (knitr/rmarkdown)",
            SKIP,
            "Rscript 부재 또는 버전 미달; 위의 R 검사 결과를 참조하세요",
        )
        return

    status = _probe_r_pkgs(rscript)
    if status is None:
        report.add(
            "R 패키지 (knitr/rmarkdown)",
            FAIL,
            f"requireNamespace 결과를 해석할 수 없음. 수동: {_R_PKG_REMEDIATION}",
        )
        return

    missing = [p for p in _R_PKGS if not status[p]]
    if not missing:
        report.add("R 패키지 knitr", PASS, "설치됨")
        report.add("R 패키지 rmarkdown", PASS, "설치됨")
        return

    # At least one missing. Decide consent.
    consent = False
    if want_fix:
        consent = True
    elif sys.stdin is not None and sys.stdin.isatty():
        try:
            sys.stdout.write(
                "knitr/rmarkdown 가 없습니다. 지금 설치할까요? [y/N]: "
            )
            sys.stdout.flush()
            answer = sys.stdin.readline().strip()
        except (EOFError, OSError):
            answer = ""
        consent = answer in ("y", "Y", "예")

    if not consent:
        # No consent (non-TTY w/o --fix, or declined): report + guide ONLY.
        for p in _R_PKGS:
            if status[p]:
                report.add(f"R 패키지 {p}", PASS, "설치됨")
            else:
                report.add(
                    f"R 패키지 {p}",
                    FAIL,
                    "없음 (Stage 3/4 렌더 차단). 설치: "
                    f"{_R_PKG_REMEDIATION}",
                )
        return

    # Consent given: install EXACTLY knitr+rmarkdown, then re-probe.
    rc, out, err = _r_install_pkgs(rscript)
    reprobe = _probe_r_pkgs(rscript) or status
    for p in _R_PKGS:
        if reprobe.get(p):
            report.add(
                f"R 패키지 {p}",
                PASS,
                "설치됨" if status[p] else "설치 완료 (동의 후 자동 설치)",
            )
        else:
            tail = " | ".join((err or "").strip().splitlines()[-3:]) or "(stderr 없음)"
            report.add(
                f"R 패키지 {p}",
                FAIL,
                f"설치 실패 (rc={rc}): {tail[:160]} — 수동: {_R_PKG_REMEDIATION}",
            )


def _codex_available() -> str | None:
    path = shutil.which("codex")
    return os.path.abspath(path) if path else None


_EV5_PROMPT = (
    "Do NOT invoke any omr skill. Call the omr_scholar MCP server's `version` "
    "tool and the omr_render MCP server's `version` tool directly. Then reply "
    "with the exact line: EV5_SCHOLAR=<scholar version> EV5_RENDER=<render "
    "version>"
)

# `codex exec` is non-interactive; close stdin and bound the wall-clock so the
# probe degrades to FAIL/SKIPPED rather than hanging. Override the budget with
# OMR_DOCTOR_CODEX_TIMEOUT (seconds).
_CODEX_TIMEOUT = int(os.environ.get("OMR_DOCTOR_CODEX_TIMEOUT", "90"))


def _codex_exec(codex: str, prompt: str, timeout: int) -> tuple[int, str, str]:
    """Invoke codex non-interactively with correct flags.

    Correct form (verified via `codex exec --help`):
        codex exec --full-auto -C <workdir> -s workspace-write "<prompt>"

    --full-auto       low-friction sandboxed automatic execution (no approval prompts)
    -C <dir>          working root for the agent
    -s workspace-write sandbox mode (writes confined to workspace)

    stdin is closed by _run() so the probe can never block on input.
    """
    workdir = os.getcwd()
    return _run(
        [codex, "exec", "--full-auto", "-C", workdir, "-s", "workspace-write", prompt],
        timeout=timeout,
    )


def ev5_session_global_gate(report: Report) -> None:
    """EV5: bare `codex exec` invoking no omr skill calls both .version tools."""
    codex = _codex_available()
    if not codex:
        report.add(
            "EV5 session-global MCP gate",
            SKIP,
            "PATH에 codex CLI 없음; /mcp를 수동으로 확인하세요",
        )
        report.add(
            "MCP privilege classification",
            SKIP,
            "codex CLI 없음; render.classify_privilege 미실행",
        )
        return

    rc, out, err = _codex_exec(codex, _EV5_PROMPT, _CODEX_TIMEOUT)
    combined = f"{out}\n{err}"
    scholar_ok = "EV5_SCHOLAR=" in combined and not re.search(
        r"EV5_SCHOLAR=\s*(?:$|EV5_RENDER)", combined
    )
    render_ok = "EV5_RENDER=" in combined and not re.search(
        r"EV5_RENDER=\s*$", combined.strip()
    )
    if rc == 0 and scholar_ok and render_ok:
        report.add(
            "EV5 session-global MCP gate",
            PASS,
            "스킬 없이 omr_scholar.version + omr_render.version 도달 가능",
        )
    else:
        snippet = combined.strip().splitlines()
        tail = " | ".join(snippet[-3:]) if snippet else "(출력 없음)"
        report.add(
            "EV5 session-global MCP gate",
            FAIL,
            f"두 .version 도구를 호출할 수 없음 (rc={rc}): {tail[:160]}",
        )

    # /mcp presence assertion (best-effort).
    rc2, out2, err2 = _codex_exec(
        codex,
        "List the MCP servers currently registered (the built-in /mcp view).",
        max(30, _CODEX_TIMEOUT // 2),
    )
    blob = f"{out2}\n{err2}"
    if "omr_scholar" in blob and "omr_render" in blob:
        report.add("MCP servers under /mcp", PASS,
                   "omr_scholar 및 omr_render 목록에 있음")
    else:
        report.add(
            "MCP servers under /mcp",
            WARN if rc2 != 0 else FAIL,
            "omr_scholar/omr_render 가 /mcp에 모두 보이지 않음",
        )

    classify_privilege(report, codex)


def classify_privilege(report: Report, codex: str) -> None:
    """render.classify_privilege semantics: host vs sandbox-confined verdict."""
    study_root = os.getcwd()
    prompt = (
        "Call omr_render's classify_privilege tool with "
        f"study_root={study_root!r} and reply with its raw JSON verdict only."
    )
    rc, out, err = _codex_exec(codex, prompt, _CODEX_TIMEOUT)
    blob = f"{out}\n{err}"
    verdict = None
    for token in ("host", "sandbox", "confined"):
        if re.search(rf"\b{token}\b", blob, re.IGNORECASE):
            verdict = token
            break
    # Try to surface a structured verdict if the server returned JSON.
    m = re.search(r"\{[^{}]*privilege[^{}]*\}", blob, re.IGNORECASE)
    if m:
        try:
            data = json.loads(m.group(0))
            verdict = str(data.get("privilege", verdict))
        except (json.JSONDecodeError, ValueError):
            pass
    if verdict:
        report.add(
            "MCP privilege classification",
            PASS,
            f"판정: {verdict} (권위 있는 경계는 서버 내부에 있음)",
        )
    else:
        report.add(
            "MCP privilege classification",
            WARN,
            f"render.classify_privilege가 판정을 반환하지 않음 (rc={rc})",
        )


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 10):
        print("omr-doctor는 Python >= 3.10 이 필요합니다", file=sys.stderr)
        return 2
    args = sys.argv[1:] if argv is None else argv
    skip_mcp = "--skip-mcp" in args
    want_fix = "--fix" in args
    want_fix_prereqs = "--fix-prereqs" in args
    if "-h" in args or "--help" in args:
        print(
            "사용법: doctor.py [--skip-mcp] [--fix] [--fix-prereqs]\n"
            "  --skip-mcp     환경/버전 프로브만; EV5 codex 게이트 건너뜀.\n"
            "  --fix          knitr/rmarkdown 부재 시 동의 없이 설치 (명시적 동의로 간주).\n"
            "  --fix-prereqs  누락/버전미달 선수도구(Python/R/pandoc)를 명시적 동의로\n"
            "                 OS 패키지 관리자(brew/winget)로 설치. sudo/admin 필요\n"
            "                 항목(예: macOS Quarto cask)은 자동 실행하지 않고 명령만 안내.\n"
            "                 --fix 와 동시 사용 가능.\n"
            "  환경변수: OMR_DOCTOR_CODEX_TIMEOUT (초, 기본 90),\n"
            "            OMR_CRAN_REPO (기본 https://cloud.r-project.org),\n"
            "            OMR_DOCTOR_R_INSTALL_TIMEOUT (초, 기본 600),\n"
            "            OMR_DOCTOR_PREREQ_TIMEOUT (초, 기본 900)."
        )
        return 0
    report = Report()
    needs_remediation = probe_tools(report)
    bootstrap_prereqs(report, needs_remediation, want_fix_prereqs)
    probe_r_packages(report, want_fix)
    if skip_mcp:
        report.add(
            "EV5 session-global MCP gate", SKIP, "--skip-mcp 요청됨"
        )
    else:
        ev5_session_global_gate(report)
    print(report.render())
    if report.has_hard_fail():
        return 1
    if any(c.status == FAIL and c.name.startswith("EV5") for c in report.checks):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
