"""
Pre-push check for the Executive Pulse repository.

Runs everything CI runs, plus the checks that catch the things CI
cannot see (secrets, machine-specific paths, stale fixtures, junk that
would be committed).

    python scripts/pre_push_check.py

Exit code 0 means it is safe to push.

Each check is independent: a failure is reported and the remaining
checks still run, so one problem does not hide another.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = REPO_ROOT / "web"

IS_WINDOWS = os.name == "nt"
NPM = "npm.cmd" if IS_WINDOWS else "npm"
NPX = "npx.cmd" if IS_WINDOWS else "npx"

# ANSI colours, disabled when the output is piped.
_COLOUR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOUR else text


GREEN = lambda t: _c("32", t)
RED = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
DIM = lambda t: _c("2", t)
BOLD = lambda t: _c("1", t)


@dataclass
class Result:
    name: str
    passed: bool
    detail: str = ""
    skipped: bool = False


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI colour codes so output can be parsed."""
    return ANSI.sub("", text)


def run(
    command: list[str],
    cwd: Path,
    timeout: int = 900,
) -> tuple[int, str]:
    """Run a command, returning (exit code, combined output)."""
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError:
        return 127, f"command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s: {' '.join(command)}"

    output = strip_ansi((completed.stdout or "") + (completed.stderr or ""))
    return completed.returncode, output.strip()


def tail(text: str, lines: int = 12) -> str:
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_python_tests() -> Result:
    code, out = run([sys.executable, "-m", "pytest", "tests/", "-q"], REPO_ROOT)
    if code == 127:
        return Result("Python reference engine tests", True, "pytest not installed", skipped=True)
    summary = next(
        (line for line in out.splitlines() if "passed" in line or "failed" in line),
        out.splitlines()[-1] if out else "",
    )
    return Result("Python reference engine tests", code == 0, summary)


def check_web_tests() -> Result:
    code, out = run([NPX, "vitest", "run"], WEB_ROOT)
    if code == 127:
        return Result("TypeScript test suites", True, "vitest not installed", skipped=True)
    summary = next(
        (line for line in out.splitlines() if "Tests " in line),
        out.splitlines()[-1] if out else "",
    )
    return Result("TypeScript test suites", code == 0, summary.strip())


def check_typecheck() -> Result:
    code, out = run([NPX, "tsc", "--noEmit"], WEB_ROOT)
    return Result(
        "TypeScript type check",
        code == 0,
        "clean" if code == 0 else tail(out, 10),
    )


def check_build() -> Result:
    code, out = run([NPM, "run", "build"], WEB_ROOT, timeout=1200)
    if code == 0:
        return Result("Production build", True, "built successfully")
    return Result("Production build", False, tail(out, 15))


def check_fixtures_in_sync() -> Result:
    """The committed golden fixtures must match the Python engine.

    CI asserts the same thing. If they drift, the parity suite is
    testing a stale expectation.
    """
    fixture = WEB_ROOT / "tests" / "fixtures" / "engine-golden.json"
    if not fixture.exists():
        return Result("Golden fixtures in sync", False, "fixture file is missing")

    before = fixture.read_bytes()
    code, out = run(
        [sys.executable, "scripts/generate_golden_fixtures.py"], REPO_ROOT
    )
    if code != 0:
        return Result("Golden fixtures in sync", False, tail(out, 8))

    after = fixture.read_bytes()
    if before == after:
        return Result("Golden fixtures in sync", True, "reproducible")
    # Restore so the working tree is left as it was.
    fixture.write_bytes(before)
    return Result(
        "Golden fixtures in sync",
        False,
        "fixtures changed when regenerated — run scripts/generate_golden_fixtures.py and commit the result",
    )


def check_lockfile_in_sync() -> Result:
    """`npm ci` fails if package-lock.json is out of step with package.json."""
    code, out = run([NPM, "ci", "--dry-run"], WEB_ROOT, timeout=600)
    if code == 127:
        return Result("npm lockfile in sync", True, "npm not available", skipped=True)
    return Result(
        "npm lockfile in sync",
        code == 0,
        "in sync" if code == 0 else tail(out, 8),
    )


# Patterns that indicate a real secret rather than the word appearing in
# code, a comment, or an environment-variable reference.
SECRET_PATTERNS = [
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"gho_[A-Za-z0-9]{30,}"), "GitHub OAuth token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{50,}"), "GitHub fine-grained token"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "OpenAI-style key"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "Google API key"),
]

# A bearer token with a long, high-entropy value.
BEARER = re.compile(r"[Bb]earer\s+([A-Za-z0-9._\-]{24,})")

# Environment-variable references are safe.
ENV_REFERENCE = re.compile(r"process\.env\.|os\.environ|getenv\(")

SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".yml", ".yaml", ".md", ".txt", ".env"}
SKIP_DIRS = {"node_modules", ".next", ".git", "__pycache__", ".pytest_cache", "dist", "build"}


def _scannable_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SCAN_SUFFIXES or path.name.startswith(".env"):
            files.append(path)
    return files


def check_no_secrets() -> Result:
    findings: list[str] = []

    for path in _scannable_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_number, line in enumerate(text.splitlines(), 1):
            if ENV_REFERENCE.search(line):
                continue

            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}  {label}"
                    )

            for match in BEARER.finditer(line):
                value = match.group(1)
                # A value that is obviously a placeholder is fine.
                if any(marker in value.lower() for marker in ("test", "fake", "example", "your", "xxx")):
                    continue
                findings.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number}  bearer token"
                )

    if findings:
        return Result("No secrets committed", False, "\n      " + "\n      ".join(findings[:10]))
    return Result("No secrets committed", True, "clean")


ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:\\\\?Users\\\\?|/Users/[A-Za-z0-9._-]+/library|/home/[A-Za-z0-9._-]+/)"
)


def check_no_machine_paths() -> Result:
    """Machine-specific paths break CI and other people's clones."""
    findings: list[str] = []

    for path in _scannable_files():
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".mjs", ".yml", ".yaml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_number, line in enumerate(text.splitlines(), 1):
            if ABSOLUTE_PATH.search(line):
                findings.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number}  {line.strip()[:80]}"
                )

    if findings:
        return Result(
            "No machine-specific paths",
            False,
            "\n      " + "\n      ".join(findings[:8]),
        )
    return Result("No machine-specific paths", True, "clean")


JUNK = (
    "node_modules/",
    ".next/",
    "__pycache__/",
    ".pytest_cache/",
    ".snapshot",
    ".snapshots/",
    "tsbuildinfo",
    ".env",
    "coverage/",
    ".DS_Store",
)


def check_no_junk_staged() -> Result:
    """Nothing that should be ignored is about to be committed."""
    code, out = run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], REPO_ROOT)
    if code == 127:
        return Result("No build artifacts staged", True, "git not available", skipped=True)

    offenders = []
    for line in out.splitlines():
        normalised = line.replace("\\", "/")
        if any(marker in normalised for marker in JUNK):
            offenders.append(normalised)

    if offenders:
        return Result(
            "No build artifacts staged",
            False,
            "\n      " + "\n      ".join(offenders[:10]),
        )
    return Result("No build artifacts staged", True, "clean")


def check_repo_size() -> Result:
    """A very large file usually means a mistake."""
    code, out = run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], REPO_ROOT
    )
    if code == 127:
        return Result("No oversized files", True, "git not available", skipped=True)

    offenders = []
    for line in out.splitlines():
        path = REPO_ROOT / line
        if path.is_file():
            size = path.stat().st_size
            if size > 2_000_000:
                offenders.append(f"{line}  ({size / 1_000_000:.1f} MB)")

    if offenders:
        return Result(
            "No oversized files",
            False,
            "\n      " + "\n      ".join(offenders[:8]),
        )
    return Result("No oversized files", True, "clean")


def check_readme_claims() -> Result:
    """The README states test counts. Keep them honest."""
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        return Result("README test counts accurate", False, "README.md is missing")

    text = readme.read_text(encoding="utf-8", errors="replace")

    claims = re.findall(r"(\d+)\s+tests?\s+[—-]\s+", text)
    if not claims:
        return Result("README test counts accurate", True, "no counts claimed")

    code, out = run([sys.executable, "-m", "pytest", "tests/", "-q"], REPO_ROOT)
    if code == 127:
        return Result("README test counts accurate", True, "pytest not available", skipped=True)
    if code != 0:
        return Result(
            "README test counts accurate",
            False,
            "could not count: the Python test suite is failing (see the test check)",
        )

    actual_python = 0
    for line in out.splitlines():
        match = re.search(r"(\d+) passed", line)
        if match:
            actual_python = int(match.group(1))
            break

    code, out = run([NPX, "vitest", "run"], WEB_ROOT)
    if code == 127:
        return Result("README test counts accurate", True, "vitest not available", skipped=True)
    if code != 0:
        return Result(
            "README test counts accurate",
            False,
            "could not count: the TypeScript test suite is failing (see the test check)",
        )

    actual_web = 0
    for line in out.splitlines():
        match = re.search(r"Tests\s+(\d+) passed", line)
        if match:
            actual_web = int(match.group(1))
            break

    problems = []
    for claimed in claims:
        value = int(claimed)
        if value not in (actual_python, actual_web):
            problems.append(
                f"README claims {value} tests; actual is {actual_python} Python / {actual_web} TypeScript"
            )

    if problems:
        return Result("README test counts accurate", False, "; ".join(problems))
    return Result(
        "README test counts accurate",
        True,
        f"{actual_python} Python / {actual_web} TypeScript",
    )


def check_env_example() -> Result:
    """An example env file makes deployment obvious."""
    example = REPO_ROOT / "web" / ".env.example"
    if not example.exists():
        return Result(
            "Deployment env vars documented",
            False,
            "web/.env.example is missing — add it so deployment variables are discoverable",
        )
    return Result("Deployment env vars documented", True, "web/.env.example present")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS = [
    check_python_tests,
    check_web_tests,
    check_typecheck,
    check_fixtures_in_sync,
    check_lockfile_in_sync,
    check_no_secrets,
    check_no_machine_paths,
    check_no_junk_staged,
    check_repo_size,
    check_readme_claims,
    check_env_example,
    check_build,  # last: it is the slowest
]


def main() -> int:
    # Some terminals cannot encode the box characters used in output.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    print()
    print(BOLD("  Executive Pulse — pre-push check"))
    print(DIM("  " + "─" * 56))
    print()

    results: list[Result] = []

    for check in CHECKS:
        print(f"  {DIM('›')} {check.__name__.replace('check_', '').replace('_', ' ')}…", end="", flush=True)
        try:
            result = check()
        except Exception as error:  # a broken check must not hide the rest
            result = Result(check.__name__, False, f"check raised: {error}")
        results.append(result)

        if result.skipped:
            print(f"\r  {YELLOW('○')} {result.name:<32} {DIM('skipped — ' + result.detail)}")
        elif result.passed:
            print(f"\r  {GREEN('✓')} {result.name:<32} {DIM(result.detail)}")
        else:
            print(f"\r  {RED('✗')} {result.name:<32} {RED('FAILED')}")

    failed = [r for r in results if not r.passed]

    print()
    print(DIM("  " + "─" * 56))
    if failed:
        print()
        for result in failed:
            print(f"  {RED('✗')} {BOLD(result.name)}")
            for line in result.detail.splitlines():
                print(f"      {line}")
            print()
        print(f"  {RED(BOLD(f'{len(failed)} check(s) failed'))} — do not push yet.")
        print()
        return 1

    skipped = len([r for r in results if r.skipped])
    suffix = f" ({skipped} skipped)" if skipped else ""
    print(f"  {GREEN(BOLD('All checks passed'))}{suffix} — safe to push.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
