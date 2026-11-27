#!/usr/bin/env python3
"""Turn a Playwright JSON report from repeated runs into a flakiness report: which tests fail, how often,
with which error, at which step, plus the likely root cause for each error pattern.

1. Reproduce:   npx playwright test <spec> --repeat-each=20 --workers=4 --retries=0 --reporter=json > report.json
                (--retries=1 also works: a test that fails then passes on retry is counted as flaky)
2. Analyse:     python3 flaky_report.py report.json [--json out.json] [--min-runs 5]

Exit code: 0 if every test passed every run, 1 if anything failed (handy in CI).
"""
import json
import re
import sys
from collections import Counter, defaultdict

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# (regex on the normalized error, label, likely cause and fix)
HINTS = [
    (r"strict mode violation", "ambiguous locator",
     "The locator matches several elements, often only sometimes (while a list re-renders). Scope it to a container "
     "(row/card/dialog) with .filter() or use exact: true. Don't paper over it with .first()."),
    (r"toHaveCount|toHaveText|toContainText|toHaveValue|toHaveURL",
     "state not settled",
     "The assertion saw a different value than expected within the timeout. Usual cause: acting before data finished "
     "loading, so a late update overwrites the result (e.g. searching before the initial list renders). Assert the "
     "loaded state first, then act. Check whether the expected value itself is time- or data-dependent."),
    (r"intercepts pointer events|element is not stable|element is outside of the viewport",
     "element covered or moving",
     "An overlay, toast, spinner or animation covers the element. Wait for the overlay to disappear "
     "(expect(overlay).toBeHidden()) or close it. Don't use force: true."),
    (r"not attached to the dom|detached",
     "element re-rendered",
     "The element was replaced during the action. Use a locator (not an ElementHandle) and assert the final state "
     "before interacting."),
    (r"waiting for (locator|getBy)|locator\.\w+: timeout|timeout \d+ms exceeded",
     "element never appeared",
     "The element did not appear in time. Check the locator against the live page, then check whether the app is "
     "slow only under parallel load (shared backend, rate limits). Wait on a condition, not a sleep."),
    (r"net::err|econnrefused|socket hang up|fetch failed|status(?: code)?:? ?5\d\d|\b50[234] (bad gateway|service unavailable|gateway)",
     "network / backend",
     "The app or an API failed. Check the server logs for the failing runs; mock unstable third-party APIs with "
     "page.route(); give each test its own data."),
    (r"target page, context or browser has been closed|has been closed",
     "test ended early",
     "Usually a missing await, or the page navigated or closed before the action finished. Check every page call is awaited."),
    (r"duplicate|already exists|unique constraint|409",
     "shared test data",
     "Tests collide on the same data when run in parallel. Generate unique data per test (Date.now(), test.info().workerIndex)."),
]


def clean(msg):
    msg = ANSI.sub("", msg or "")
    return msg


def signature(msg):
    """First meaningful line(s) with volatile numbers removed, so the same failure groups together."""
    lines = [l.strip() for l in clean(msg).splitlines() if l.strip()]
    head = lines[0] if lines else "(no error message)"
    detail = next((l for l in lines[1:4] if l.startswith(("Locator", "Expected", "Received"))), "")
    sig = f"{head} {detail}".strip()
    sig = re.sub(r"\d+ms", "Nms", sig)
    sig = re.sub(r"(localhost|127\.0\.0\.1):\d+", r"\1:PORT", sig)
    return sig[:220]


def hint_for(msg):
    low = clean(msg).lower()
    for rx, label, advice in HINTS:
        if re.search(rx, low, re.I):
            return label, advice
    return "unclassified", "Read the full error and trace (npx playwright show-trace) for one failing run."


def failing_step(result):
    """Deepest step that has an error, e.g. the test.step() title where it broke."""
    best = None

    def walk(steps, path):
        nonlocal best
        for s in steps or []:
            p = path + [s.get("title", "")]
            if s.get("error"):
                best = p
            walk(s.get("steps"), p)
    walk(result.get("steps"), [])
    if best:
        named = [t for t in best if not t.startswith(("expect", "locator", "page.", "Expect", "Wait"))]
        return " › ".join(named[-2:] or best[-1:])
    return None


def iter_specs(suite, parents=()):
    title = suite.get("title", "")
    path = parents + ((title,) if title and not title.endswith((".ts", ".js", ".mjs", ".py")) else ())
    for spec in suite.get("specs", []):
        yield path, spec
    for child in suite.get("suites", []):
        yield from iter_specs(child, path)


def analyse(report):
    tests = defaultdict(lambda: {"runs": 0, "passed": 0, "failed": 0, "flaky": 0, "errors": Counter(), "steps": Counter(),
                                 "durations": [], "sample": {}})
    for top in report.get("suites", []):
        for path, spec in iter_specs(top):
            for t in spec.get("tests", []):
                key = (spec.get("file") or top.get("file"), " › ".join(path + (spec["title"],)), t.get("projectName") or "")
                rec = tests[key]
                rec["line"] = spec.get("line")
                results = t.get("results", [])
                if not results or t.get("status") == "skipped":
                    continue
                rec["runs"] += 1
                final = results[-1]["status"]
                any_fail = any(r["status"] in ("failed", "timedOut", "interrupted") for r in results)
                if final == "passed" and not any_fail:
                    rec["passed"] += 1
                elif final == "passed":
                    rec["flaky"] += 1   # failed, then passed on retry
                else:
                    rec["failed"] += 1
                for r in results:
                    rec["durations"].append(r.get("duration", 0))
                    if r["status"] in ("failed", "timedOut"):
                        errs = r.get("errors") or ([r["error"]] if r.get("error") else [])
                        msg = (errs[0] or {}).get("message", "") if errs else f"status: {r['status']}"
                        if r["status"] == "timedOut" and not msg:
                            msg = "Test timeout exceeded"
                        sig = signature(msg)
                        rec["errors"][sig] += 1
                        rec["sample"].setdefault(sig, clean(msg)[:1200])
                        step = failing_step(r)
                        if step:
                            rec["steps"][step] += 1
    return tests


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    with open(args[0], encoding="utf-8") as fh:
        report = json.load(fh)
    min_runs = int(args[args.index("--min-runs") + 1]) if "--min-runs" in args else 1
    tests = analyse(report)
    rows = []
    for (file, title, project), r in tests.items():
        if r["runs"] < min_runs:
            continue
        bad = r["failed"] + r["flaky"]
        rows.append({"file": file, "line": r.get("line"), "test": title, "project": project, "runs": r["runs"],
                     "passed_first_try": r["passed"], "failed": r["failed"], "flaky_on_retry": r["flaky"],
                     "failure_rate": round(bad / r["runs"], 3) if r["runs"] else 0,
                     "avg_seconds": round(sum(r["durations"]) / len(r["durations"]) / 1000, 2) if r["durations"] else None,
                     "errors": [{"signature": s, "count": c, "cause": hint_for(r["sample"][s])[0],
                                 "advice": hint_for(r["sample"][s])[1], "sample": r["sample"][s]}
                                for s, c in r["errors"].most_common()],
                     "failing_steps": dict(r["steps"].most_common())})
    rows.sort(key=lambda x: (-x["failure_rate"], x["file"] or "", x["test"]))
    unstable = [x for x in rows if x["failure_rate"] > 0]
    total_runs = sum(x["runs"] for x in rows)

    print(f"{len(rows)} test(s), {total_runs} run(s): {len(unstable)} unstable, {len(rows) - len(unstable)} stable\n")
    for x in unstable:
        kind = "BROKEN" if x["passed_first_try"] == 0 and x["flaky_on_retry"] == 0 else "FLAKY"
        print(f"{kind} {x['failure_rate'] * 100:.0f}% · {x['test']} [{x['project']}]  ({x['file']}:{x['line']})")
        print(f"   runs {x['runs']} · passed {x['passed_first_try']} · failed {x['failed']} · passed only on retry {x['flaky_on_retry']}"
              f" · avg {x['avg_seconds']}s")
        if x["failing_steps"]:
            print("   failing step: " + ", ".join(f"{s} ({c}x)" for s, c in x["failing_steps"].items()))
        for e in x["errors"]:
            print(f"   {e['count']}x {e['signature']}")
            print(f"      likely cause: {e['cause']}. {e['advice']}")
        print()
    if not unstable:
        print("All tests passed every run. If you expected a flake, increase --repeat-each or add --workers to raise load.")
    if "--json" in args:
        with open(args[args.index("--json") + 1], "w", encoding="utf-8") as fh:
            json.dump({"tests": rows, "stats": report.get("stats")}, fh, indent=2)
    sys.exit(1 if unstable else 0)


if __name__ == "__main__":
    main()
