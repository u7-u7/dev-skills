#!/usr/bin/env python3
"""Analyze author attribution for changed files."""

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


def run_git_blame(repo: Path, file_path: str, start_line: int, end_line: int) -> str:
    """Run git blame for a line range.

    NOTE: This function is reserved for future enhancements.
    It will be needed for more granular author attribution at the line level.
    Currently not used in the main workflow but kept for upcoming features.
    """
    result = subprocess.run(
        ["git", "blame", "-L", f"{start_line},{end_line}", file_path],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def extract_author_from_blame(blame_output: str) -> str:
    """Extract author from git blame output.

    NOTE: This function is reserved for future enhancements.
    It will be needed for more granular author attribution at the line level.
    Currently not used in the main workflow but kept for upcoming features.
    """
    if not blame_output:
        return "unknown"
    # Git blame format: hash (author_name date) line content
    # Find the first author name in parentheses
    match = re.search(r'\(([^)]+\s+\d{4}-\d{2}-\d{2})', blame_output)
    if match:
        author_part = match.group(1)
        # Extract just the name (before the date)
        name = re.sub(r'\s*\d{4}-\d{2}-\d{2}.*', '', author_part).strip()
        return name
    return "unknown"


def analyze_author_file_map(repo: Path, base: str, head: str) -> dict[str, list[str]]:
    """Analyze which authors modified which files."""
    author_files = defaultdict(list)

    # Get files changed by each author using a more reliable parsing approach
    # Format: author name followed by list of files, then next author, etc.
    log_output = subprocess.run(
        ["git", "log", "--no-merges", "--pretty=format:%an", "--name-only", f"{base}..{head}"],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )

    # Parse the output more reliably
    # Git log format: author1\nfile1\nfile2\n\nauthor2\nfile3\nfile4
    lines = log_output.stdout.strip().split("\n")
    current_author = None

    for line in lines:
        line = line.strip()
        if not line:
            # Empty line resets author (separator between commits)
            continue

        # A line is an author name if it doesn't look like a file path
        # Files typically have extensions or directory separators
        is_file_path = "/" in line or "." in line

        if not is_file_path and len(line) < 80:
            # This is likely an author name
            current_author = line
        elif current_author:
            # This is a file path
            author_files[current_author].append(line)

    return {k: list(set(v)) for k, v in author_files.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = {
        "author_file_map": analyze_author_file_map(args.repo, args.base, args.head),
        "author_commits": {},  # Could be extended
    }

    try:
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, IOError) as e:
        print(f"Error writing to output file {args.output}: {e}")
        raise


if __name__ == "__main__":
    main()
