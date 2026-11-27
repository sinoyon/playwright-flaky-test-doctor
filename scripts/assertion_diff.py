#!/usr/bin/env python3
"""Review a change to a test file (by a person, an AI agent, or Playwright's healer agent) for
changes that make a test pass by testing LESS: removed or loosened assertions, new sleeps,
force clicks, skips, or broader locators.

Usage:
  python3 assertion_diff.py old.spec.ts new.spec.ts
  python3 assertion_diff.py --git tests/cart.spec.ts [--base HEAD]     # compare the working copy with git

Exit code: 1 if any WEAKENED finding, else 0.
"""
import difflib
import re
import subprocess
import sys
from pathlib import Path

ASSERT = re.compile(r"\bexpect(\.soft|\.poll)?\s*\(|\bto_\w+\(|\bassert\b")
CHECKS = [  # (regex on an ADDED line, level, message)
    (r"waitForTimeout\s*\(|wait_for_timeout\s*\(|time\.sleep\s*\(", "WEAKENED", "added a fixed sleep"),
    (r"force\s*[:=]\s*(true|True)", "WEAKENED", "added force: true (skips actionability checks)"),
    (r"\b(test|it|describe)\.(skip|fixme|fail)\s*\(|@pytest\.mark\.skip", "WEAKENED", "skipped or marked a test as expected to fail"),
    (r"\.(first|last)\s*\(\s*\)|\.nth\s*\(", "REVIEW", "picks an element by index; check the locator was not made ambiguous"),
    (r"timeout\s*[:=]\s*\d{5,}", "REVIEW", "raised a timeout to 10s or more; check it hides no real slowness"),
    (r"\.catch\s*\(\s*\(\s*\)\s*=>|except\s*(Exception)?\s*:\s*pass", "WEAKENED", "swallows an error"),
    (r"toBeTruthy\(\)|toBeDefined\(\)", "REVIEW", "very loose assertion"),
    (r"\{\s*name\s*:\s*/[^/]{0,3}/", "REVIEW", "very short regex in a locator name; may match unintended elements"),
]
LOOSENED = [  # (old pattern, new pattern, message)
    (r"toHaveText\(", r"toContainText\(", "toHaveText loosened to toContainText"),
    (r"exact\s*:\s*true", None, "removed exact: true from a locator"),
    (r"toHaveCount\(\s*\d+", r"toHaveCount\(\s*expect\.|toBeGreaterThan", "exact count loosened"),
    (r"toBeVisible\(\)", r"toBeAttached\(\)", "toBeVisible loosened to toBeAttached"),
    (r"toHaveURL\(\s*['\"`]", r"toHaveURL\(\s*/", "exact URL loosened to a regex"),
]


def code_lines(text):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s and not s.startswith(("//", "#", "*", "/*")):
            out.append((n, line))
    return out


def review(old_text, new_text):
    findings = []
    old_l, new_l = code_lines(old_text), code_lines(new_text)
    old_assert = sum(1 for _, l in old_l if ASSERT.search(l))
    new_assert = sum(1 for _, l in new_l if ASSERT.search(l))
    sm = difflib.SequenceMatcher(a=[l.strip() for _, l in old_l], b=[l.strip() for _, l in new_l], autojunk=False)
    removed, added = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            removed += old_l[i1:i2]
        if tag in ("insert", "replace"):
            added += new_l[j1:j2]
    for n, l in removed:
        if ASSERT.search(l):
            findings.append(("WEAKENED" if new_assert < old_assert else "REVIEW", f"old:{n}", f"assertion removed or changed: {l.strip()[:140]}"))
    for n, l in added:
        if "lint-ok" in l:
            continue
        for rx, level, msg in CHECKS:
            if re.search(rx, l):
                findings.append((level, f"new:{n}", f"{msg}: {l.strip()[:140]}"))
    rem_text = "\n".join(l for _, l in removed)
    add_text = "\n".join(l for _, l in added)
    for old_rx, new_rx, msg in LOOSENED:
        if re.search(old_rx, rem_text) and (new_rx is None or re.search(new_rx, add_text)):
            findings.append(("WEAKENED", "-", msg))
    if new_assert < old_assert:
        findings.append(("WEAKENED", "-", f"assertion count dropped from {old_assert} to {new_assert}"))
    return old_assert, new_assert, len(removed), len(added), findings


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    if a[0] == "--git":
        path = a[1]
        base = a[a.index("--base") + 1] if "--base" in a else "HEAD"
        old_text = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout
        new_text = Path(path).read_text(encoding="utf-8")
        label = f"{path} ({base} → working copy)"
    else:
        old_text, new_text = Path(a[0]).read_text(encoding="utf-8"), Path(a[1]).read_text(encoding="utf-8")
        label = f"{a[0]} → {a[1]}"
    old_n, new_n, rem, add, findings = review(old_text, new_text)
    print(f"{label}\nassertions: {old_n} → {new_n} · lines removed {rem} · added {add}")
    for level, where, msg in findings:
        print(f"  {level:8} {where:8} {msg}")
    weakened = sum(1 for f in findings if f[0] == "WEAKENED")
    print(f"\n{weakened} weakening change(s), {len(findings) - weakened} to review"
          + ("" if findings else ". No weakening detected"))
    sys.exit(1 if weakened else 0)


if __name__ == "__main__":
    main()
