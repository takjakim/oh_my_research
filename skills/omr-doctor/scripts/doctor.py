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
TOOLS: list[tuple[str, str, list[str], tuple[int, int] | None]] = [
    ("R", "Rscript", ["--version"], (4, 2)),
    ("quarto", "quarto", ["--version"], (1, 4)),
    ("pandoc", "pandoc", ["--version"], (3, 1)),
    ("python3", "python3", ["--version"], None),
]


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

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(Check(name, status, detail))

    def has_hard_fail(self) -> bool:
        return any(c.status == FAIL for c in self.checks)

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


def probe_tools(report: Report) -> None:
    for name, executable, args, floor in TOOLS:
        # Build candidate list: PATH first, then per-OS known install dirs.
        candidates = _find_candidates(executable)

        if not candidates:
            status = FAIL if floor else WARN
            report.add(name, status, "PATH 또는 알려진 설치 경로에서 찾을 수 없음")
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
            continue

        vstr = ".".join(str(p) for p in ver)
        if floor is not None and (ver[0], ver[1]) < floor:
            need = f"{floor[0]}.{floor[1]}"
            report.add(
                name,
                FAIL,
                f"{resolved_path} v{vstr} < 필요 버전 {need} (HARD FAIL)",
            )
        else:
            report.add(name, PASS, f"{resolved_path} v{vstr}")


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
    if "-h" in args or "--help" in args:
        print(
            "사용법: doctor.py [--skip-mcp]\n"
            "  --skip-mcp   환경/버전 프로브만; EV5 codex 게이트 건너뜀.\n"
            "  환경변수: OMR_DOCTOR_CODEX_TIMEOUT (초, 기본 90)."
        )
        return 0
    report = Report()
    probe_tools(report)
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
