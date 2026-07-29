#!/usr/bin/env python3
"""跨平台的 Skill Usage Tracker 本地看板服务。"""

from __future__ import annotations

import argparse
import json
import random
import re
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


SCRIPT_FILE = Path(__file__).resolve()
REPO_ROOT = SCRIPT_FILE.parents[4]
DASHBOARD_FILE = REPO_ROOT / "skills" / "platform" / "skill-usage-tracker" / "dashboard" / "index.html"
SKILLS_ROOT = REPO_ROOT / "skills"
DEFAULT_STATS_FILE = Path.home() / "usage_stats.json"
MAX_STATS_BYTES = 10 * 1024 * 1024
MAX_HISTORY = 50
SAFE_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MOCK_SKILLS = (
    "ai-pair-programmer",
    "app-scanner",
    "author-final-review",
    "brainstorming",
    "code-review",
    "diagram-creation",
    "full-review",
    "git-worktree",
    "integration-test",
    "sdd-dev-workflow",
    "skill-usage-tracker",
    "team-cr",
)
MOCK_WEIGHTS = (50, 49, 47, 45, 44, 43, 42, 41, 39, 37, 34, 29)


def empty_stats() -> dict[str, Any]:
    return {"skills": {}, "total_usage": 0}


def normalize_stats(raw: Any) -> dict[str, Any]:
    """只保留看板需要的安全、稳定字段，并重新计算总数。"""
    if not isinstance(raw, dict):
        return empty_stats()

    normalized: dict[str, Any] = {"skills": {}, "total_usage": 0}
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        return normalized

    for name, value in skills.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            continue
        try:
            count = max(0, int(value.get("count", 0)))
        except (TypeError, ValueError):
            count = 0

        history = []
        source_history = value.get("history", [])
        if isinstance(source_history, list):
            for item in source_history[:MAX_HISTORY]:
                if not isinstance(item, dict):
                    continue
                timestamp = str(item.get("timestamp", "")).strip()
                if not timestamp:
                    continue
                history.append(
                    {
                        "timestamp": timestamp,
                        "context": str(item.get("context", ""))[:500],
                    }
                )

        last_used = value.get("last_used")
        normalized["skills"][name] = {
            "count": count,
            "last_used": str(last_used) if last_used else None,
            "history": history,
        }

    normalized["total_usage"] = sum(item["count"] for item in normalized["skills"].values())
    return normalized


def load_stats(stats_file: Path) -> dict[str, Any]:
    if not stats_file.exists():
        result = empty_stats()
    else:
        if stats_file.stat().st_size > MAX_STATS_BYTES:
            raise ValueError("统计文件超过 10MB，已拒绝读取")
        try:
            with stats_file.open("r", encoding="utf-8") as file_obj:
                result = normalize_stats(json.load(file_obj))
        except json.JSONDecodeError as exc:
            raise ValueError("统计文件不是有效 JSON") from exc
        except OSError as exc:
            raise ValueError("统计文件暂时无法读取") from exc

    result["_meta"] = {
        "source_kind": "real",
        "source_label": "🏠 本机统计 ~/usage_stats.json",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history_limit": MAX_HISTORY,
    }
    return result


def _allocate_mock_counts(total: int) -> list[int]:
    weight_total = sum(MOCK_WEIGHTS)
    raw_counts = [total * weight / weight_total for weight in MOCK_WEIGHTS]
    counts = [int(value) for value in raw_counts]
    remainder = total - sum(counts)
    order = sorted(range(len(counts)), key=lambda i: (raw_counts[i] - counts[i], -i), reverse=True)
    for index in order[:remainder]:
        counts[index] += 1
    return counts


def generate_mock_stats(
    total: int,
    seed: int = 42,
    now: datetime | None = None,
) -> dict[str, Any]:
    """在内存中生成可重复分布的演示数据，绝不写入真实统计文件。"""
    if total < 1 or total > 10_000:
        raise ValueError("Mock 次数必须在 1 到 10000 之间")

    rng = random.Random(seed)
    current = now or datetime.now(timezone.utc)
    skills: dict[str, Any] = {}
    for skill_name, count in zip(MOCK_SKILLS, _allocate_mock_counts(total)):
        events = []
        for event_index in range(count):
            seconds_ago = rng.randint(0, 45 * 24 * 60 * 60)
            timestamp = (current - timedelta(seconds=seconds_ago)).isoformat()
            events.append(
                {
                    "timestamp": timestamp,
                    "context": f"Mock 演示调用 #{event_index + 1}",
                }
            )
        events.sort(key=lambda item: item["timestamp"], reverse=True)
        skills[skill_name] = {
            "count": count,
            "last_used": events[0]["timestamp"] if events else None,
            "history": events[:MAX_HISTORY],
        }

    return {
        "skills": skills,
        "total_usage": total,
        "_meta": {
            "source_kind": "mock",
            "source_label": f"🧪 Mock 演示数据（{total} 次）",
            "generated_at": current.isoformat(),
            "history_limit": MAX_HISTORY,
            "seed": seed,
        },
    }


def parse_skill_description(markdown: str) -> str:
    frontmatter = re.match(r"^---\s*\n(.*?)\n---", markdown, re.DOTALL)
    if not frontmatter:
        return ""
    lines = frontmatter.group(1).replace("\r", "").split("\n")
    for index, line in enumerate(lines):
        match = re.match(r"^description:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value in {"|", "|-", "|+", ">", ">-", ">+"}:
            block = []
            for next_line in lines[index + 1 :]:
                if next_line and not next_line.startswith(("  ", "\t")):
                    break
                block.append(next_line.strip())
            return " ".join(part for part in block if part).strip()
        return value.strip("'\"")
    return ""


def find_skill_description(skill_name: str) -> str | None:
    if not SAFE_SEGMENT.fullmatch(skill_name):
        return None
    for skill_file in sorted(SKILLS_ROOT.glob(f"*/{skill_name}/SKILL.md")):
        try:
            skill_file.resolve().relative_to(SKILLS_ROOT.resolve())
            return parse_skill_description(skill_file.read_text(encoding="utf-8")) or "暂无技能说明"
        except (OSError, ValueError):
            continue
    return None


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        stats_file: Path,
        mock_stats: dict[str, Any] | None,
    ) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.stats_file = stats_file
        self.mock_stats = mock_stats


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "SkillDashboard/1.0"

    def log_message(self, format_string: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format_string % args}")

    def _host_is_safe(self) -> bool:
        host_header = self.headers.get("Host", "")
        if not host_header:
            return True
        hostname = urlsplit(f"//{host_header}").hostname
        return hostname in {"127.0.0.1", "localhost", "::1"}

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        cache_control: str = "no-store",
        head_only: bool = False,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any], *, head_only: bool = False) -> None:
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", head_only=head_only)

    def _send_error_json(self, status: int, message: str, *, head_only: bool = False) -> None:
        self._send_json(status, {"error": message}, head_only=head_only)

    def _query_is_safe(self, query: str) -> bool:
        return set(parse_qs(query, keep_blank_values=True)) <= {"_t"}

    def _handle(self, *, head_only: bool = False) -> None:
        if not self._host_is_safe():
            self._send_error_json(403, "仅允许通过 localhost 访问", head_only=head_only)
            return

        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path in {"/", "/dashboard", "/dashboard/"}:
            if path == "/":
                self.send_response(302)
                self.send_header("Location", "/dashboard/")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            path = "/dashboard/index.html"

        if path in {
            "/dashboard/index.html",
            "/skills/platform/skill-usage-tracker/dashboard/index.html",
        }:
            try:
                body = DASHBOARD_FILE.read_bytes()
            except OSError:
                self._send_error_json(500, "看板页面暂时无法读取", head_only=head_only)
                return
            self._send_bytes(200, body, "text/html; charset=utf-8", head_only=head_only)
            return

        if path == "/api/health":
            if not self._query_is_safe(parsed.query):
                self._send_error_json(400, "不支持的查询参数", head_only=head_only)
                return
            mode = "mock" if self.server.mock_stats is not None else "real"
            self._send_json(200, {"status": "ok", "mode": mode}, head_only=head_only)
            return

        if path == "/api/usage-stats":
            if not self._query_is_safe(parsed.query):
                self._send_error_json(400, "不支持的查询参数", head_only=head_only)
                return
            try:
                payload = self.server.mock_stats or load_stats(self.server.stats_file)
            except ValueError as exc:
                self._send_error_json(500, str(exc), head_only=head_only)
                return
            self._send_json(200, payload, head_only=head_only)
            return

        prefix = "/api/skill-description/"
        if path.startswith(prefix):
            if not self._query_is_safe(parsed.query):
                self._send_error_json(400, "不支持的查询参数", head_only=head_only)
                return
            skill_name = path[len(prefix) :]
            description = find_skill_description(skill_name)
            if description is None:
                self._send_error_json(404, "未找到技能说明", head_only=head_only)
                return
            self._send_json(
                200,
                {"name": skill_name, "description": description},
                head_only=head_only,
            )
            return

        self._send_error_json(404, "未找到资源", head_only=head_only)

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle(head_only=True)

    def do_POST(self) -> None:  # noqa: N802
        self._send_error_json(405, "仅支持只读请求")


def build_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    stats_file: Path = DEFAULT_STATS_FILE,
    mock_count: int | None = None,
    seed: int = 42,
) -> DashboardServer:
    mock_payload = generate_mock_stats(mock_count, seed=seed) if mock_count is not None else None
    return DashboardServer((host, port), stats_file=stats_file, mock_stats=mock_payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动 Skill 使用统计本地看板")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认仅本机")
    parser.add_argument("--port", type=int, default=8000, help="监听端口，默认 8000")
    parser.add_argument("--stats-file", type=Path, default=DEFAULT_STATS_FILE, help=argparse.SUPPRESS)
    parser.add_argument("--mock-count", "--mock", dest="mock_count", type=int, help="生成指定次数的内存 Mock 数据")
    parser.add_argument("--seed", type=int, default=42, help="Mock 随机种子，默认 42")
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--allow-remote", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_remote:
        raise SystemExit("为保护本地统计，非回环地址需要显式添加 --allow-remote")
    if args.mock_count is not None and not 1 <= args.mock_count <= 10_000:
        raise SystemExit("--mock-count 必须在 1 到 10000 之间")

    server = build_server(
        host=args.host,
        port=args.port,
        stats_file=args.stats_file.expanduser(),
        mock_count=args.mock_count,
        seed=args.seed,
    )
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/dashboard/"
    mode_label = f"Mock {args.mock_count} 次" if args.mock_count is not None else "真实统计"
    print(f"📊 看板已启动：{url}")
    print(f"🔒 仅本机访问 · 数据模式：{mode_label} · 按 Ctrl+C 停止")
    if args.open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 看板已停止")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
