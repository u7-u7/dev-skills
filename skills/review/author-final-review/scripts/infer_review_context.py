#!/usr/bin/env python3
"""Infer missing context for author-final-review.

Given repo paths, infer candidate author/head/base/apps so the skill can ask
focused clarification questions instead of failing on missing inputs.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path, allow_fail: bool = False) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0 and not allow_fail:
        raise RuntimeError(f"cmd failed: {' '.join(shlex.quote(c) for c in cmd)}\n{proc.stderr.strip()}")
    return proc.stdout if proc.returncode == 0 else ""


def first_non_empty(lines: list[str]) -> str:
    for line in lines:
        if line.strip():
            return line.strip()
    return ""


def git_value(repo: Path, key: str) -> str:
    return run(["git", "config", "--get", key], repo, allow_fail=True).strip()


def branch_current(repo: Path) -> str:
    return run(["git", "branch", "--show-current"], repo, allow_fail=True).strip() or "HEAD"


def remote_branches(repo: Path) -> list[str]:
    out = run(["git", "branch", "-r"], repo, allow_fail=True)
    return [x.strip() for x in out.splitlines() if x.strip()]


def base_candidates(repo: Path) -> list[str]:
    remotes = remote_branches(repo)
    candidates = [
        "origin/main",
        "origin/master",
        "main",
        "master",
        "origin/release",
    ]
    result: list[str] = []
    for c in candidates:
        if c in remotes or c in {"main", "master"}:
            result.append(c)

    # add top release branches if present
    release = [r for r in remotes if "/release" in r or "release/" in r]
    result.extend(sorted(release)[:3])

    dedup: list[str] = []
    seen: set[str] = set()
    for r in result:
        if r not in seen:
            dedup.append(r)
            seen.add(r)
    return dedup


def files_changed(repo: Path, base: str, head: str) -> list[str]:
    out = run(["git", "diff", "--name-only", f"{base}..{head}"], repo, allow_fail=True)
    return [x.strip() for x in out.splitlines() if x.strip()]


def top_authors(repo: Path, base: str, head: str) -> list[str]:
    out = run(["git", "shortlog", "-sne", f"{base}..{head}"], repo, allow_fail=True)
    rows = [x.strip() for x in out.splitlines() if x.strip()]
    return rows[:5]


def infer_apps(paths: list[str]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for p in paths:
        parts = p.split("/")
        if len(parts) >= 2 and parts[0] == "apps":
            key = f"apps/{parts[1]}"
        else:
            key = parts[0]
        if key:
            counter[key] += 1
    return [{"app": k, "file_count": v} for k, v in counter.most_common(20)]


def repo_payload(repo: Path, base_in: str, head_in: str) -> dict[str, Any]:
    if not (repo / ".git").exists():
        return {"repo": str(repo), "error": "not a git repo"}

    current = branch_current(repo)
    bases = base_candidates(repo)
    resolved_head = head_in or current or "HEAD"
    resolved_base = base_in or first_non_empty(bases) or "origin/main"

    changed = files_changed(repo, resolved_base, resolved_head)

    return {
        "repo": str(repo),
        "author_suggestion": {
            "git_user_email": git_value(repo, "user.email"),
            "git_user_name": git_value(repo, "user.name"),
            "top_authors_in_range": top_authors(repo, resolved_base, resolved_head),
        },
        "branch_suggestion": {
            "current_branch": current,
            "base_candidates": bases,
            "resolved_base": resolved_base,
            "resolved_head": resolved_head,
        },
        "app_candidates": infer_apps(changed),
        "changed_file_count": len(changed),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Infer missing context for author-final-review")
    parser.add_argument("--repo", action="append", required=True, help="Repository path, repeatable")
    parser.add_argument("--base", default="", help="Optional base ref override")
    parser.add_argument("--head", default="", help="Optional head ref override")
    parser.add_argument("--output", default="", help="Optional JSON output file")
    args = parser.parse_args()

    repos = [Path(x).resolve() for x in args.repo]
    payload = {
        "repos": [repo_payload(r, args.base, args.head) for r in repos],
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        p = Path(args.output).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(str(p))
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
