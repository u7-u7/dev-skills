#!/usr/bin/env python3
"""Collect git changes for team CR.

Outputs:
- Changed files with stats
- Commit list with authors
- Entry points (HTTP/RPC/Job/MQ)
"""

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path) -> str:
    """Run command and return stdout."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def get_diff_stats(repo: Path, base: str, head: str) -> dict[str, Any]:
    """Get diff statistics."""
    out = run(["git", "diff", "--stat", f"{base}..{head}"], repo)
    return {"stat": out}


def get_commits(repo: Path, base: str, head: str) -> list[dict[str, str]]:
    """Get commit list with authors."""
    out = run(
        ["git", "log", "--no-merges", "--pretty=format:%H%x09%an%x09%ae%x09%s", f"{base}..{head}"],
        repo
    )
    commits = []
    for line in out.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 3)
        if len(parts) >= 4:
            commits.append({
                "sha": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "subject": parts[3]
            })
    return commits


def get_changed_files(repo: Path, base: str, head: str) -> list[str]:
    """Get list of changed files."""
    out = run(["git", "diff", "--name-only", f"{base}..{head}"], repo)
    return [f for f in out.strip().split("\n") if f]


def find_entry_points(repo: Path, base: str, head: str) -> dict[str, list[str]]:
    """Find entry points in changed files."""
    files = get_changed_files(repo, base, head)
    entry_points = {"http": [], "rpc": [], "job": [], "mq": []}

    for file_path in files:
        if not file_path.endswith((".java", ".kt")):
            continue

        full_path = repo / file_path
        if not full_path.exists():
            continue

        content = run(["git", "show", f"{head}:{file_path}"], repo)

        # HTTP endpoints
        for match in re.finditer(r'@(?:Get|Post|Put|Delete|Request)Mapping\(["\']([^"\']+)["\']', content):
            entry_points["http"].append(f"{file_path}:{match.group(1)}")

        # RPC services
        for match in re.finditer(r'@DubboService|interface\s+(\w+Service)', content):
            entry_points["rpc"].append(f"{file_path}")

        # Scheduled jobs
        for match in re.finditer(r'@(?:Scheduled|XxlJob)', content):
            entry_points["job"].append(f"{file_path}")

        # MQ listeners
        for match in re.finditer(r'@RocketMQMessageListener', content):
            entry_points["mq"].append(f"{file_path}")

    return entry_points


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = {
        "diff_stats": get_diff_stats(args.repo, args.base, args.head),
        "commits": get_commits(args.repo, args.base, args.head),
        "changed_files": get_changed_files(args.repo, args.base, args.head),
        "entry_points": find_entry_points(args.repo, args.base, args.head),
    }

    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
