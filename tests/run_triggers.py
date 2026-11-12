#!/usr/bin/env python3
"""Trigger evals: does each skill fire for the prompts it should, and stay quiet for near misses?

  python3 tests/run_triggers.py [--skill autoshift-review] [--runs 3] [--model MODEL]

Every skill in skills/ is installed together into a throwaway project, so the skills compete with
each other the way they do for a real user. Each query runs headless through the Claude Code CLI
(`claude -p`); a query counts as triggered when the first tool call loads the skill under test. These
are real, billed model runs. The trigger sets in tests/triggers/ use the format skill-creator's
description optimizer reads, so they can also drive that tool.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def first_skill_call(query: str, project: Path, model: str | None, timeout: int) -> str | None:
    """Return the skill name the first tool call loads, '' for another tool, None for no tool."""
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose", "--max-turns", "2"]
    if model:
        cmd += ["--model", model]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = subprocess.Popen(cmd, cwd=project, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    try:
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "assistant":
                continue
            for block in event.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue
                inp = block.get("input", {})
                if block.get("name") == "Skill":
                    return str(inp.get("skill", "")).split(":")[-1]
                if block.get("name") == "Read" and "SKILL.md" in str(inp.get("file_path", "")):
                    return Path(inp["file_path"]).parent.name
                return ""
        return None
    finally:
        proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", action="append", help="limit to these skills")
    ap.add_argument("--runs", type=int, default=3, help="runs per query; triggered means a majority")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if not shutil.which("claude"):
        sys.exit("needs the Claude Code CLI (claude) on PATH")

    project = Path(tempfile.mkdtemp(prefix="autoshift-triggers-"))
    (project / ".claude" / "skills").mkdir(parents=True)
    for skill in (ROOT / "skills").iterdir():
        if skill.is_dir():
            (project / ".claude" / "skills" / skill.name).symlink_to(skill)

    jobs = []
    for tf in sorted((ROOT / "tests" / "triggers").glob("*.json")):
        if args.skill and tf.stem not in args.skill:
            continue
        for item in json.loads(tf.read_text()):
            jobs.append((tf.stem, item["query"], item["should_trigger"]))

    def run(job):
        skill, query, want = job
        hits = sum(first_skill_call(query, project, args.model, args.timeout) == skill
                   for _ in range(args.runs))
        return skill, query, want, hits

    failed = 0
    results = {}
    with ThreadPoolExecutor(args.workers) as pool:
        for skill, query, want, hits in pool.map(run, jobs):
            got = hits * 2 > args.runs
            ok = got == want
            failed += not ok
            results.setdefault(skill, []).append(ok)
            print(f"{'ok  ' if ok else 'FAIL'} {skill:18} want={str(want):5} hits={hits}/{args.runs}  {query[:70]}")
    for skill, oks in results.items():
        print(f"{skill}: {sum(oks)}/{len(oks)} correct")
    shutil.rmtree(project)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
