#!/usr/bin/env python3
"""
技能使用统计器 - 更新脚本
特性：
1) 并发安全（文件锁）
2) 原子写入（临时文件 + replace）
3) 仅使用用户根目录单一主文件存储（~/usage_stats.json）
4) 支持 repair：从 Git 历史回填丢失计数
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


MAX_HISTORY = 50
DEFAULT_STATS = {"skills": {}, "total_usage": 0}

SCRIPT_FILE = Path(__file__).resolve()


def _repo_root() -> Path | None:
    current = SCRIPT_FILE
    for p in [current] + list(current.parents):
        git_marker = p / ".git"
        if git_marker.exists():
            return p
    return None


REPO_ROOT = _repo_root()
LEGACY_REPO_DATA_FILE = (REPO_ROOT / "usage_stats.json").resolve() if REPO_ROOT else None
DEFAULT_HOME_DATA_FILE = Path(os.path.expanduser("~/usage_stats.json")).resolve()
README_FILE = (REPO_ROOT / "README.md").resolve() if REPO_ROOT else None
README_STATS_START = "<!-- SKILL_STATS_LIVE:START -->"
README_STATS_END = "<!-- SKILL_STATS_LIVE:END -->"
README_TOP_N = 10


def _safe_stats(value) -> Dict:
    if not isinstance(value, dict):
        return {"skills": {}, "total_usage": 0}
    skills = value.get("skills", {})
    if not isinstance(skills, dict):
        skills = {}
    out = {"skills": skills, "total_usage": value.get("total_usage", 0)}
    out["total_usage"] = _recompute_total(out)
    return out


def _recompute_total(stats: Dict) -> int:
    total = 0
    for skill_data in stats.get("skills", {}).values():
        try:
            total += int(skill_data.get("count", 0))
        except Exception:
            continue
    return total


def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {"skills": {}, "total_usage": 0}
    try:
        with path.open("r", encoding="utf-8") as f:
            return _safe_stats(json.load(f))
    except Exception:
        return {"skills": {}, "total_usage": 0}


def _atomic_write_json(path: Path, stats: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(stats, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def _resolve_data_file() -> Path:
    return DEFAULT_HOME_DATA_FILE


DATA_FILE = _resolve_data_file()
_lock_name = "skill-usage-tracker-" + hashlib.sha1(str(DATA_FILE).encode("utf-8")).hexdigest()[:12] + ".lock"
LOCK_FILE = Path(tempfile.gettempdir()) / _lock_name


def _maybe_migrate_repo_stats() -> None:
    if LEGACY_REPO_DATA_FILE is None or not LEGACY_REPO_DATA_FILE.exists():
        return
    if DATA_FILE.exists():
        return
    try:
        stats = _read_json(LEGACY_REPO_DATA_FILE)
        _atomic_write_json(DATA_FILE, stats)
    except Exception:
        return


@contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as fp:
        if fcntl is not None:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)


def _load_for_update() -> Dict:
    _maybe_migrate_repo_stats()
    return _read_json(DATA_FILE)


def _save_for_update(stats: Dict) -> None:
    stats = _safe_stats(stats)
    stats["total_usage"] = _recompute_total(stats)
    _atomic_write_json(DATA_FILE, stats)


def _sort_skills(stats: Dict) -> List[Tuple[str, Dict]]:
    return sorted(
        stats.get("skills", {}).items(),
        key=lambda x: (int(x[1].get("count", 0)), x[0]),
        reverse=True,
    )


def _escape_md_cell(value: str, max_len: int = 80) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text.replace("|", "\\|")


def _format_last_used(ts: str | None) -> str:
    text = str(ts or "").strip()
    if not text:
        return "N/A"
    # ISO 时间展示到秒
    return text[:19].replace("T", " ")


def _latest_context(skill: Dict) -> str:
    history = skill.get("history", [])
    if isinstance(history, list):
        for item in history:
            if isinstance(item, dict):
                context = str(item.get("context", "")).strip()
                if context:
                    return context
    return "-"


def _build_readme_snapshot(stats: Dict) -> str:
    stats = _safe_stats(stats)
    rows = _sort_skills(stats)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"- 更新时间：`{generated_at}`",
        f"- 总调用次数：`{_recompute_total(stats)}`",
        f"- 已记录技能数：`{len(rows)}`",
        "",
        "| 排名 | Skill | 次数 | 最后使用 | 最近场景 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    if not rows:
        lines.append("| - | - | 0 | N/A | 暂无数据 |")
    else:
        for idx, (name, data) in enumerate(rows[:README_TOP_N], 1):
            count = int(data.get("count", 0))
            last_used = _format_last_used(data.get("last_used"))
            context = _latest_context(data)
            lines.append(
                f"| {idx} | `{_escape_md_cell(name)}` | {count} | {_escape_md_cell(last_used)} | {_escape_md_cell(context)} |"
            )
    lines.append("")
    lines.append("_该区块由 `scripts/skill-stats sync-readme` 手动刷新。_")
    return "\n".join(lines)


def _sync_readme_snapshot(stats: Dict | None = None) -> bool:
    if README_FILE is None or not README_FILE.exists():
        return False

    snapshot = _build_readme_snapshot(stats if stats is not None else _read_json(DATA_FILE))
    replacement = f"{README_STATS_START}\n{snapshot}\n{README_STATS_END}"

    try:
        original = README_FILE.read_text(encoding="utf-8")
        pattern = re.compile(
            rf"{re.escape(README_STATS_START)}.*?{re.escape(README_STATS_END)}",
            re.DOTALL,
        )
        if pattern.search(original):
            updated = pattern.sub(replacement, original, count=1)
        else:
            updated = original.rstrip() + "\n\n## 📈 README 实时统计\n\n" + replacement + "\n"

        if updated != original:
            README_FILE.write_text(updated, encoding="utf-8")
        return True
    except Exception:
        return False


def _upsert_skill(stats: Dict, skill_name: str) -> Dict:
    skills = stats.setdefault("skills", {})
    if skill_name not in skills or not isinstance(skills[skill_name], dict):
        skills[skill_name] = {"count": 0, "last_used": None, "history": []}
    skill = skills[skill_name]
    if not isinstance(skill.get("history"), list):
        skill["history"] = []
    return skill


def record_usage(skill_name: str, context: str = "") -> int:
    with _exclusive_lock(LOCK_FILE):
        stats = _load_for_update()
        skill = _upsert_skill(stats, skill_name)

        skill["count"] = int(skill.get("count", 0)) + 1
        now = datetime.now().isoformat()
        skill["last_used"] = now
        skill["history"].insert(0, {"timestamp": now, "context": context})
        skill["history"] = skill["history"][:MAX_HISTORY]

        _save_for_update(stats)
        return skill["count"]


def get_stats(skill_name: str | None = None) -> Dict:
    _maybe_migrate_repo_stats()
    stats = _safe_stats(_read_json(DATA_FILE))
    if skill_name:
        return stats["skills"].get(
            skill_name, {"count": 0, "last_used": None, "history": []}
        )

    sorted_skills = sorted(
        stats["skills"].items(),
        key=lambda x: int(x[1].get("count", 0)),
        reverse=True,
    )
    return {"skills": dict(sorted_skills), "total_usage": stats["total_usage"]}


def reset_stats(skill_name: str | None) -> Tuple[bool, int]:
    with _exclusive_lock(LOCK_FILE):
        stats = _load_for_update()
        if skill_name:
            if skill_name not in stats.get("skills", {}):
                return False, 0
            stats["skills"][skill_name] = {"count": 0, "last_used": None, "history": []}
            _save_for_update(stats)
            return True, 1

        _save_for_update({"skills": {}, "total_usage": 0})
        return True, len(stats.get("skills", {}))


def _git_show_json(repo_root: Path, commit_hash: str, pathspec: str) -> Dict:
    ref = f"{commit_hash}:{pathspec}"
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "show", ref],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"skills": {}, "total_usage": 0}
    try:
        return _safe_stats(json.loads(proc.stdout))
    except Exception:
        return {"skills": {}, "total_usage": 0}


def _load_history_snapshots(limit: int = 300) -> List[Dict]:
    repo_root = _repo_root()
    if repo_root is None or LEGACY_REPO_DATA_FILE is None:
        return []
    try:
        pathspec = LEGACY_REPO_DATA_FILE.relative_to(repo_root).as_posix()
    except Exception:
        return []

    proc = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--format=%H", f"--max-count={limit}", "--", pathspec],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if proc.returncode != 0:
        return []

    hashes = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
    snapshots: List[Dict] = []
    for commit_hash in hashes:
        snapshot = _git_show_json(repo_root, commit_hash, pathspec)
        if snapshot.get("skills"):
            snapshots.append(snapshot)
    return snapshots


def _merge_history(old_history: List[Dict], new_history: List[Dict]) -> List[Dict]:
    merged = {}
    for item in old_history + new_history:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("timestamp", "")).strip()
        ctx = str(item.get("context", "")).strip()
        if not ts:
            continue
        merged[(ts, ctx)] = {"timestamp": ts, "context": ctx}
    ordered = sorted(merged.values(), key=lambda x: x["timestamp"], reverse=True)
    return ordered[:MAX_HISTORY]


def _merge_stats(base: Dict, incoming: Dict) -> Dict:
    out = _safe_stats(base)
    in_stats = _safe_stats(incoming)

    for skill_name, incoming_skill in in_stats.get("skills", {}).items():
        base_skill = out.get("skills", {}).get(skill_name, {"count": 0, "last_used": None, "history": []})
        if not isinstance(base_skill, dict):
            base_skill = {"count": 0, "last_used": None, "history": []}
        if not isinstance(incoming_skill, dict):
            continue

        base_count = int(base_skill.get("count", 0))
        in_count = int(incoming_skill.get("count", 0))
        count = max(base_count, in_count)

        base_last = str(base_skill.get("last_used") or "")
        in_last = str(incoming_skill.get("last_used") or "")
        last_used = max(base_last, in_last) or None

        history = _merge_history(
            base_skill.get("history", []) if isinstance(base_skill.get("history"), list) else [],
            incoming_skill.get("history", []) if isinstance(incoming_skill.get("history"), list) else [],
        )

        out["skills"][skill_name] = {
            "count": count,
            "last_used": last_used,
            "history": history,
        }

    out["total_usage"] = _recompute_total(out)
    return out


def repair_from_git_history(limit: int = 300) -> Tuple[int, int, int]:
    with _exclusive_lock(LOCK_FILE):
        current = _load_for_update()
        current_total = _recompute_total(current)
        snapshots = _load_history_snapshots(limit=limit)
        merged = current
        for snapshot in snapshots:
            merged = _merge_stats(merged, snapshot)
        merged_total = _recompute_total(merged)

        if merged != current:
            _save_for_update(merged)
        return current_total, merged_total, len(snapshots)


def main() -> None:
    parser = argparse.ArgumentParser(description="技能使用统计器")
    parser.add_argument(
        "action",
        choices=["record", "view", "reset", "repair", "sync-readme"],
        help="操作类型：record(记录), view(查看), reset(重置), repair(历史回填修复), sync-readme(刷新README统计块)",
    )
    parser.add_argument("--skill", help="技能名称")
    parser.add_argument("--context", help="使用场景", default="")
    parser.add_argument("--limit", type=int, default=300, help="repair 时扫描历史提交上限")
    parser.add_argument("--show-file", action="store_true", help="显示当前统计文件路径")
    args = parser.parse_args()

    if args.show_file:
        print(f"stats_file={DATA_FILE}")

    if args.action == "record":
        if not args.skill:
            print("错误：记录使用需要提供 --skill 参数")
            return
        count = record_usage(args.skill, args.context)
        print(f"✅ 已记录：{args.skill} (第 {count} 次使用)")
        return

    if args.action == "view":
        stats = get_stats(args.skill)
        if args.skill:
            print(f"\n📊 {args.skill} 使用统计")
            print(f"使用次数: {stats['count']}")
            print(f"最后使用: {stats['last_used'] or '从未使用'}")
            return

        print(f"\n📊 技能使用总排行 (总计 {stats['total_usage']} 次)")
        print("-" * 60)
        for skill, data in stats["skills"].items():
            last = data["last_used"][:10] if data["last_used"] else "N/A"
            print(f"{skill:30} | {int(data['count']):5} 次 | 最后使用: {last}")
        return

    if args.action == "reset":
        ok, touched = reset_stats(args.skill)
        if args.skill:
            if ok:
                print(f"✅ 已重置：{args.skill}")
            else:
                print(f"⚠️  技能不存在：{args.skill}")
            return

        print(f"✅ 已重置所有统计数据 (skills={touched})")
        return

    if args.action == "repair":
        before, after, snapshots = repair_from_git_history(limit=args.limit)
        if after > before:
            print(f"✅ 修复完成：total_usage {before} -> {after} (snapshots={snapshots})")
        else:
            print(f"ℹ️ 无需修复：total_usage={after} (snapshots={snapshots})")
        return

    if args.action == "sync-readme":
        ok = _sync_readme_snapshot(_read_json(DATA_FILE))
        if ok:
            print("✅ 已刷新 README 统计快照")
        else:
            print("⚠️  README 刷新失败（可能未在仓库内或 README 不存在）")
        return


if __name__ == "__main__":
    main()
