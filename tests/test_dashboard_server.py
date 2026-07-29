#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = REPO_ROOT / "skills" / "platform" / "skill-usage-tracker" / "scripts" / "dashboard_server.py"
SPEC = importlib.util.spec_from_file_location("dashboard_server", SERVER_SCRIPT)
dashboard_server = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(dashboard_server)


class DashboardServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.stats_file = Path(self.temp_dir.name) / "usage_stats.json"
        self.server = dashboard_server.build_server(port=0, stats_file=self.stats_file)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def request(self, path: str, method: str = "GET"):
        request = Request(f"{self.base_url}{path}", method=method)
        return urlopen(request, timeout=3)

    def test_missing_stats_returns_empty_real_payload(self) -> None:
        with self.request("/api/usage-stats") as response:
            payload = json.load(response)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(payload["skills"], {})
        self.assertEqual(payload["total_usage"], 0)
        self.assertEqual(payload["_meta"]["source_kind"], "real")

    def test_real_stats_are_normalized_and_total_is_recomputed(self) -> None:
        self.stats_file.write_text(
            json.dumps(
                {
                    "skills": {
                        "sample-skill": {
                            "count": 3,
                            "last_used": "2026-07-29T08:00:00+00:00",
                            "history": [
                                {
                                    "timestamp": "2026-07-29T08:00:00+00:00",
                                    "context": "示例调用",
                                }
                            ],
                        }
                    },
                    "total_usage": 999,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with self.request("/api/usage-stats?_t=1") as response:
            payload = json.load(response)
        self.assertEqual(payload["total_usage"], 3)
        self.assertEqual(payload["skills"]["sample-skill"]["count"], 3)

    def test_dashboard_health_description_and_static_boundary(self) -> None:
        with self.request("/api/health") as response:
            self.assertEqual(json.load(response), {"status": "ok", "mode": "real"})
        with self.request("/dashboard/") as response:
            html = response.read().decode("utf-8")
            self.assertIn('value="/api/usage-stats"', html)
            self.assertIn("使用频率 TOP 10", html)
            self.assertIn("rows.slice(0, 10)", html)
            self.assertIn("metric-mint", html)
        with self.request("/api/skill-description/skill-usage-tracker") as response:
            payload = json.load(response)
            self.assertTrue(payload["description"])
        for forbidden_path in ("/.git/config", "/../README.md", "/skills/platform/skill-usage-tracker/SKILL.md"):
            with self.assertRaises(HTTPError) as error:
                self.request(forbidden_path)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()

    def test_query_cannot_select_an_arbitrary_file(self) -> None:
        with self.assertRaises(HTTPError) as error:
            self.request("/api/usage-stats?path=README.md")
        self.assertEqual(error.exception.code, 400)
        error.exception.close()

    def test_invalid_json_returns_safe_error(self) -> None:
        self.stats_file.write_text("not-json", encoding="utf-8")
        with self.assertRaises(HTTPError) as error:
            self.request("/api/usage-stats")
        self.assertEqual(error.exception.code, 500)
        payload = json.loads(error.exception.read().decode("utf-8"))
        self.assertEqual(payload["error"], "统计文件不是有效 JSON")
        self.assertNotIn(str(self.stats_file), payload["error"])
        error.exception.close()

    def test_post_is_rejected(self) -> None:
        with self.assertRaises(HTTPError) as error:
            self.request("/api/usage-stats", method="POST")
        self.assertEqual(error.exception.code, 405)
        error.exception.close()


class DashboardMockTests(unittest.TestCase):
    def test_mock_500_is_exact_and_reproducible(self) -> None:
        now = datetime(2026, 7, 29, tzinfo=timezone.utc)
        first = dashboard_server.generate_mock_stats(500, seed=42, now=now)
        second = dashboard_server.generate_mock_stats(500, seed=42, now=now)
        self.assertEqual(first, second)
        self.assertEqual(first["total_usage"], 500)
        self.assertEqual(sum(item["count"] for item in first["skills"].values()), 500)
        self.assertEqual(first["_meta"]["source_kind"], "mock")
        self.assertTrue(all(len(item["history"]) <= 50 for item in first["skills"].values()))
        self.assertTrue(all(dashboard_server.find_skill_description(name) for name in first["skills"]))

    def test_mock_server_does_not_modify_real_stats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stats_file = Path(temp_dir) / "usage_stats.json"
            stats_file.write_text('{"sentinel": true}\n', encoding="utf-8")
            before = hashlib.sha256(stats_file.read_bytes()).hexdigest()
            server = dashboard_server.build_server(port=0, stats_file=stats_file, mock_count=500)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/api/usage-stats"
                with urlopen(url, timeout=3) as response:
                    payload = json.load(response)
                self.assertEqual(payload["total_usage"], 500)
                self.assertEqual(payload["_meta"]["source_kind"], "mock")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            after = hashlib.sha256(stats_file.read_bytes()).hexdigest()
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
