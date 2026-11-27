#!/usr/bin/env python3
"""Flag flaky or brittle patterns in Playwright specs (TS, JS, Python).

Usage:  python3 lint_spec.py <file-or-folder> [more ...]
Exit:   0 = no errors (warnings allowed), 1 = errors found, 2 = bad usage.

Suppress a finding on one line with a trailing comment:  // lint-ok: <reason>   or   # lint-ok: <reason>
"""
import re
import sys
from pathlib import Path

EXTS = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".py"}

# (level, rule id, regex, message)
RULES = [
    ("ERROR", "fixed-sleep", r"\bwaitForTimeout\s*\(|\bwait_for_timeout\s*\(|\btime\.sleep\s*\(|new Promise\s*\(\s*\(?\s*\w*\s*\)?\s*=>\s*setTimeout",
     "Fixed sleep. Wait on a condition instead (web-first assertion, waitForURL, waitForResponse)."),
    ("ERROR", "xpath", r"""(locator|\$\$?|wait_?[fF]or_?[sS]elector)\s*\(\s*(['"`])(xpath=|//|\(//)""",
     "XPath locator. Use getByRole / getByLabel / getByText / getByTestId."),
    ("ERROR", "focused-test", r"\b(test|it|describe)\.only\s*\(|@pytest\.mark\.only",
     "Focused test (.only) will skip the rest of the suite."),
    ("ERROR", "non-retrying-assert",
     r"expect\s*\(\s*await\s+.*?\.(textContent|innerText|inputValue|isVisible|isHidden|isEnabled|isChecked|getAttribute|count)\s*\(",
     "Non-retrying assertion on a one-off read. Use web-first: await expect(locator).toHaveText()/toBeVisible()/toHaveCount()."),
    ("ERROR", "non-retrying-assert-py",
     r"\bassert\s+[^#\n]*\.(text_content|inner_text|input_value|is_visible|is_hidden|is_enabled|is_checked|get_attribute|count)\s*\(",
     "Non-retrying assert on a one-off read. Use expect(locator).to_have_text()/to_be_visible()/to_have_count()."),
    ("ERROR", "hardcoded-secret",
     r"""(?i)(password|passwd|secret|token|api[_-]?key)[^\n]*\.(fill|type|press_?[sS]equentially)\s*\(\s*(['"`])(?!\s*\3)[^'"`$]{3,}\3""",
     "Hardcoded credential. Read it from an environment variable."),
    ("WARN", "force-action", r"force\s*[:=]\s*(true|True)",
     "force bypasses actionability checks and can hide real bugs. Justify with a lint-ok comment or remove."),
    ("WARN", "positional-css", r""":nth-(child|of-type)\(|(locator|\$\$?)\s*\(\s*(['"`])[^'"`]*\s>\s""",
     "Positional / structural CSS breaks on layout changes. Scope by role or text instead."),
    ("WARN", "index-pick", r"\.(first|last)\s*\(\s*\)|\.nth\s*\(",
     "Picking by index often hides an ambiguous locator. Prefer scoping with .filter({ hasText }) or exact: true."),
    ("WARN", "generated-class", r"""(['"`.\s])(css-[a-z0-9]{4,}|sc-[a-zA-Z]{5,}|jsx-\d+|_[a-zA-Z0-9]{5,}_[a-z0-9]{4,})""",
     "Looks like a generated class name; it changes between builds."),
    ("WARN", "legacy-handle", r"\bpage\.\$\$?\s*\(|\bwaitForSelector\s*\(|\bwait_for_selector\s*\(|\bquery_selector(_all)?\s*\(",
     "ElementHandle / waitForSelector API. Use locators and web-first assertions."),
    ("WARN", "networkidle", r"networkidle",
     "networkidle is discouraged (polling/analytics keep the network busy). Wait for a visible ready state instead."),
    ("WARN", "css-class-locator", r"""(locator)\s*\(\s*(['"`])\.[a-zA-Z]""",
     "Class-based locator. Prefer getByRole / getByLabel / getByTestId."),
]

TEST_START = re.compile(r"""^\s*(test|it)\s*\(\s*['"`]|^\s*(async\s+)?def\s+test_\w+\s*\(""")
EXPECT = re.compile(r"\bexpect\s*\(|\bassert\b|toHaveScreenshot|to_have_")


def is_comment(line: str, py: bool) -> bool:
    s = line.strip()
    return s.startswith("#") if py else (s.startswith("//") or s.startswith("*") or s.startswith("/*"))


def lint_file(path: Path):
    py = path.suffix == ".py"
    findings = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for no, line in enumerate(lines, 1):
        if is_comment(line, py) or "lint-ok" in line:
            continue
        for level, rule, rx, msg in RULES:
            if (rule.endswith("-py") and not py):
                continue
            if re.search(rx, line):
                findings.append((no, level, rule, msg))

    # Tests with no assertion at all.
    starts = [i for i, l in enumerate(lines) if TEST_START.search(l)]
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start + 1:end])
        if not EXPECT.search(body):
            findings.append((start + 1, "WARN", "no-assertion", "Test has no assertion; it can only fail on errors, not on wrong behaviour."))
    return sorted(findings)


def collect(targets):
    for t in targets:
        p = Path(t)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix in EXTS and "node_modules" not in f.parts and f.is_file():
                    yield f
        elif p.is_file():
            yield p
        else:
            print(f"not found: {t}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    errors = warns = files = 0
    for f in collect(sys.argv[1:]):
        files += 1
        for no, level, rule, msg in lint_file(f):
            print(f"{f}:{no}: {level} [{rule}] {msg}")
            errors += level == "ERROR"
            warns += level == "WARN"
    print(f"\n{files} file(s): {errors} error(s), {warns} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
