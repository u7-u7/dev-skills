#!/usr/bin/env python3
"""Manage structured outputs for author-final-review.

This script provides a machine-consumable post-processing pipeline:
1) enrich review JSON with scope/tier/severity summary
2) compare against baseline and classify findings (new/existing/resolved)
3) merge finding workflow statuses
4) evaluate release gate decision

The script is intentionally standalone (stdlib only) so it can run in CI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEVERITY_ORDER = ("P0", "P1", "P2", "P3")
ACTIVE_P1_STATES = {"new", "reopened"}
DEFAULT_FINDING_STATUS = "new"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: str) -> str:
    lowered = (text or "").strip().lower()
    return re.sub(r"\s+", " ", lowered)


def normalize_severity(raw: str) -> str:
    token = normalize_text(raw)
    mapping = {
        "p0": "P0",
        "critical": "P0",
        "blocker": "P0",
        "p1": "P1",
        "high": "P1",
        "p2": "P2",
        "medium": "P2",
        "p3": "P3",
        "low": "P3",
    }
    return mapping.get(token, "P2")


def parse_file_line(finding: dict[str, Any]) -> tuple[str, str]:
    file_path = str(finding.get("file", "") or finding.get("file_path", "")).strip()
    line = str(finding.get("line", "")).strip()
    if line:
        return file_path, line
    m = re.match(r"^(.*?):(\d+)$", file_path)
    if not m:
        return file_path, ""
    return m.group(1), m.group(2)


def finding_fingerprint(finding: dict[str, Any]) -> str:
    repo = normalize_text(str(finding.get("repo", "")))
    file_path, line = parse_file_line(finding)
    file_path = normalize_text(file_path)
    line = normalize_text(line)
    problem = normalize_text(str(finding.get("problem", "")))
    evidence = normalize_text(str(finding.get("final_state_evidence", "")))[:160]
    key = "|".join((repo, file_path, line, problem, evidence))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()  # noqa: S324
    return digest[:20]


def complexity_tier(commit_count: int, file_count: int) -> str:
    if commit_count >= 20 or file_count >= 40:
        return "Tier-H"
    if 8 <= commit_count <= 19 or 15 <= file_count <= 39:
        return "Tier-M"
    return "Tier-L"


def expected_finding_minimum(tier: str) -> int:
    if tier == "Tier-H":
        return 5
    if tier == "Tier-M":
        return 3
    return 0


def summarize_scope(scope_doc: dict[str, Any]) -> dict[str, Any]:
    repos = scope_doc.get("repos", []) if isinstance(scope_doc, dict) else []
    commit_count = sum(int(r.get("commit_count", 0)) for r in repos if isinstance(r, dict))
    file_count = sum(int(r.get("file_count", 0)) for r in repos if isinstance(r, dict))
    tier = complexity_tier(commit_count, file_count)
    return {
        "commit_count": commit_count,
        "file_count": file_count,
        "tier": tier,
        "expected_findings_minimum": expected_finding_minimum(tier),
        "repos": [r.get("repo", "") for r in repos if isinstance(r, dict)],
    }


def ensure_review_shape(review_doc: dict[str, Any]) -> dict[str, Any]:
    if "meta" not in review_doc or not isinstance(review_doc["meta"], dict):
        review_doc["meta"] = {}
    if "summary" not in review_doc or not isinstance(review_doc["summary"], dict):
        review_doc["summary"] = {}
    if "findings" not in review_doc or not isinstance(review_doc["findings"], list):
        review_doc["findings"] = []
    return review_doc


def enrich_findings(review_doc: dict[str, Any]) -> None:
    findings: list[dict[str, Any]] = []
    for raw in review_doc.get("findings", []):
        if not isinstance(raw, dict):
            continue
        finding = dict(raw)
        finding["severity"] = normalize_severity(str(finding.get("severity", "P2")))
        file_path, line = parse_file_line(finding)
        finding["file"] = file_path
        if line:
            finding["line"] = line
        finding["id"] = finding.get("id") or finding_fingerprint(finding)
        if "review_status" not in finding:
            finding["review_status"] = DEFAULT_FINDING_STATUS
        findings.append(finding)
    review_doc["findings"] = findings


def build_baseline_index(baseline_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = baseline_doc.get("items", [])
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        fingerprint = str(item.get("fingerprint", "")).strip()
        if fingerprint:
            index[fingerprint] = item
    return index


def apply_baseline(
    review_doc: dict[str, Any],
    baseline_doc: dict[str, Any],
    *,
    update_baseline: bool,
) -> dict[str, Any]:
    baseline_index = build_baseline_index(baseline_doc)
    now = now_iso()

    current_fps: set[str] = set()
    new_count = 0
    existing_count = 0
    for finding in review_doc["findings"]:
        fp = str(finding["id"])
        current_fps.add(fp)
        if fp in baseline_index:
            finding["baseline_state"] = "existing"
            existing_count += 1
            if update_baseline:
                baseline_index[fp]["last_seen"] = now
                baseline_index[fp]["last_severity"] = finding["severity"]
        else:
            finding["baseline_state"] = "new"
            new_count += 1
            if update_baseline:
                baseline_index[fp] = {
                    "fingerprint": fp,
                    "first_seen": now,
                    "last_seen": now,
                    "status": "active",
                    "last_severity": finding["severity"],
                    "problem": finding.get("problem", ""),
                    "repo": finding.get("repo", ""),
                    "file": finding.get("file", ""),
                }

    resolved = [fp for fp in baseline_index if fp not in current_fps]
    if update_baseline:
        for fp in resolved:
            item = baseline_index[fp]
            item["status"] = "resolved"
            item["last_seen"] = now

        baseline_doc["version"] = 1
        baseline_doc["updated_at"] = now
        baseline_doc["items"] = sorted(baseline_index.values(), key=lambda x: str(x.get("fingerprint", "")))

    return {
        "new_count": new_count,
        "existing_count": existing_count,
        "resolved_count": len(resolved),
    }


def build_status_index(status_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = status_doc.get("items", [])
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        fp = str(item.get("fingerprint", "")).strip()
        if fp:
            index[fp] = item
    return index


def apply_status(
    review_doc: dict[str, Any],
    status_doc: dict[str, Any],
    *,
    update_status: bool,
) -> Counter[str]:
    status_index = build_status_index(status_doc)
    now = now_iso()

    seen: set[str] = set()
    for finding in review_doc["findings"]:
        fp = str(finding["id"])
        seen.add(fp)
        item = status_index.get(fp)
        if item:
            finding["review_status"] = str(item.get("status", DEFAULT_FINDING_STATUS))
            if item.get("reason"):
                finding["status_reason"] = item["reason"]
        else:
            finding["review_status"] = DEFAULT_FINDING_STATUS
            if update_status:
                status_index[fp] = {
                    "fingerprint": fp,
                    "status": DEFAULT_FINDING_STATUS,
                    "reason": "",
                    "updated_at": now,
                }

    if update_status:
        for fp, item in status_index.items():
            if fp not in seen and item.get("status") == "new":
                item["status"] = "resolved"
                item["updated_at"] = now

        status_doc["version"] = 1
        status_doc["updated_at"] = now
        status_doc["items"] = sorted(status_index.values(), key=lambda x: str(x.get("fingerprint", "")))

    return Counter(str(f.get("review_status", DEFAULT_FINDING_STATUS)) for f in review_doc["findings"])


def evaluate_gate(review_doc: dict[str, Any]) -> dict[str, Any]:
    sev_counter = Counter(str(f.get("severity", "P2")) for f in review_doc["findings"])
    p0_count = int(sev_counter.get("P0", 0))
    active_p1 = sum(
        1
        for f in review_doc["findings"]
        if f.get("severity") == "P1" and str(f.get("review_status", DEFAULT_FINDING_STATUS)) in ACTIVE_P1_STATES
    )
    reasons: list[str] = []
    if p0_count > 0:
        reasons.append(f"存在 P0 问题 {p0_count} 条")
    if active_p1 > 0:
        reasons.append(f"存在未处理 P1 问题 {active_p1} 条（状态为 new/reopened）")
    return {
        "pass": len(reasons) == 0,
        "reasons": reasons,
    }


def update_summary(review_doc: dict[str, Any], baseline_summary: dict[str, Any], status_counter: Counter[str]) -> None:
    sev_counter = Counter(str(f.get("severity", "P2")) for f in review_doc["findings"])
    review_doc["summary"]["finding_total"] = len(review_doc["findings"])
    review_doc["summary"]["by_severity"] = {key: int(sev_counter.get(key, 0)) for key in SEVERITY_ORDER}
    review_doc["summary"]["baseline"] = baseline_summary
    review_doc["summary"]["by_status"] = dict(status_counter)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage author-final-review JSON/baseline/status artifacts")
    parser.add_argument("--review-json", required=True, help="Review JSON path")
    parser.add_argument("--scope-json", default="", help="Optional collect_author_scope output JSON")
    parser.add_argument("--baseline", default="", help="Optional baseline JSON path")
    parser.add_argument("--status-file", default="", help="Optional status JSON path")
    parser.add_argument("--output", default="", help="Optional output path, default overwrite --review-json")
    parser.add_argument("--update-baseline", action="store_true", help="Write baseline updates back to file")
    parser.add_argument("--update-status", action="store_true", help="Write status updates back to file")
    parser.add_argument("--strict-gate", action="store_true", help="Exit with code 2 when gate fails")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review_path = Path(args.review_json).resolve()
    output_path = Path(args.output).resolve() if args.output else review_path
    scope_path = Path(args.scope_json).resolve() if args.scope_json else None
    baseline_path = Path(args.baseline).resolve() if args.baseline else None
    status_path = Path(args.status_file).resolve() if args.status_file else None

    review_doc = read_json(review_path, default={})
    if not isinstance(review_doc, dict):
        raise SystemExit("review JSON must be an object")
    review_doc = ensure_review_shape(review_doc)
    review_doc["meta"]["review_time"] = review_doc["meta"].get("review_time") or now_iso()

    if scope_path:
        scope_doc = read_json(scope_path, default={})
        if isinstance(scope_doc, dict):
            review_doc["scope"] = summarize_scope(scope_doc)

    enrich_findings(review_doc)

    baseline_summary = {"new_count": 0, "existing_count": 0, "resolved_count": 0}
    baseline_doc: dict[str, Any] = {"version": 1, "items": []}
    if baseline_path:
        loaded = read_json(baseline_path, default=baseline_doc)
        if isinstance(loaded, dict):
            baseline_doc = loaded
        baseline_summary = apply_baseline(review_doc, baseline_doc, update_baseline=args.update_baseline)
        if args.update_baseline:
            write_json(baseline_path, baseline_doc)

    status_counter: Counter[str] = Counter()
    status_doc: dict[str, Any] = {"version": 1, "items": []}
    if status_path:
        loaded = read_json(status_path, default=status_doc)
        if isinstance(loaded, dict):
            status_doc = loaded
        status_counter = apply_status(review_doc, status_doc, update_status=args.update_status)
        if args.update_status:
            write_json(status_path, status_doc)
    else:
        status_counter = Counter(str(f.get("review_status", DEFAULT_FINDING_STATUS)) for f in review_doc["findings"])

    update_summary(review_doc, baseline_summary, status_counter)
    review_doc["gates"] = evaluate_gate(review_doc)

    write_json(output_path, review_doc)
    print(json.dumps({"output": str(output_path), "gates": review_doc["gates"], "summary": review_doc["summary"]}, ensure_ascii=False))

    if args.strict_gate and not review_doc["gates"]["pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
