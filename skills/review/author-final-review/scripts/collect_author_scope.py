#!/usr/bin/env python3
"""Collect author-only review scope in final-state model.

Given author + base/head + repos, output:
- author commits
- files touched by author commits
- final-state diff stats on touched files
- other contributors touching same files in the same range
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(shlex.quote(c) for c in cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def parse_commit_line(line: str) -> dict[str, str]:
    parts = line.split("\t", 3)
    if len(parts) < 4:
        return {}
    return {
        "sha": parts[0],
        "author_name": parts[1],
        "author_email": parts[2],
        "subject": parts[3],
    }


def get_author_commits(repo: Path, base: str, head: str, author: str) -> list[dict[str, str]]:
    out = run(
        [
            "git",
            "log",
            "--no-merges",
            "--pretty=format:%H%x09%an%x09%ae%x09%s",
            f"{base}..{head}",
            f"--author={author}",
        ],
        repo,
    )
    rows = [parse_commit_line(x) for x in out.splitlines() if x.strip()]
    return [r for r in rows if r]


def files_from_commits(repo: Path, shas: list[str]) -> list[str]:
    files: set[str] = set()
    for sha in shas:
        out = run(["git", "show", "--pretty=", "--name-only", sha], repo)
        for line in out.splitlines():
            line = line.strip()
            if line:
                files.add(line)
    return sorted(files)


def final_numstat_for_files(repo: Path, base: str, head: str, files: list[str]) -> list[dict[str, Any]]:
    if not files:
        return []
    cmd = ["git", "diff", "--numstat", f"{base}..{head}", "--", *files]
    out = run(cmd, repo)
    result: list[dict[str, Any]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        ins, dele, path = parts
        result.append({"insertions": ins, "deletions": dele, "path": path})
    return result


def collaborators_on_files(repo: Path, base: str, head: str, files: list[str], author: str) -> list[str]:
    if not files:
        return []
    out = run(["git", "log", "--no-merges", "--pretty=format:%an <%ae>", f"{base}..{head}", "--", *files], repo)
    names = {x.strip() for x in out.splitlines() if x.strip()}
    lower_author = author.lower()
    filtered = [n for n in sorted(names) if lower_author not in n.lower()]
    return filtered


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def collect_repo(repo: Path, author: str, base: str, head: str) -> dict[str, Any]:
    if not is_git_repo(repo):
        raise RuntimeError(f"not a git repo: {repo}")

    commits = get_author_commits(repo, base, head, author)
    shas = [c["sha"] for c in commits]
    files = files_from_commits(repo, shas)
    numstat = final_numstat_for_files(repo, base, head, files)
    collaborators = collaborators_on_files(repo, base, head, files, author)

    return {
        "repo": str(repo),
        "author": author,
        "base_ref": base,
        "head_ref": head,
        "commit_count": len(commits),
        "commits": commits,
        "file_count": len(files),
        "files": files,
        "final_numstat": numstat,
        "collaborators_on_same_files": collaborators,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect author-only final-state review scope")
    parser.add_argument("--author", required=True, help="Author email or name for git --author filter")
    parser.add_argument("--base", default="origin/main", help="Base ref")
    parser.add_argument("--head", default="HEAD", help="Head ref")
    parser.add_argument("--repo", action="append", required=True, help="Repository path, repeatable")
    parser.add_argument("--output", default="", help="Output JSON path")
    args = parser.parse_args()

    repos = [Path(p).resolve() for p in args.repo]
    payload: dict[str, Any] = {
        "author": args.author,
        "base_ref": args.base,
        "head_ref": args.head,
        "repos": [],
        "errors": [],
    }

    for repo in repos:
        try:
            payload["repos"].append(collect_repo(repo, args.author, args.base, args.head))
        except Exception as exc:  # noqa: BLE001
            payload["errors"].append({"repo": str(repo), "error": str(exc)})

    output = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(str(out_path))
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
