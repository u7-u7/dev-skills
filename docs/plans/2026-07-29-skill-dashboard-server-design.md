# Skill 使用统计看板本地服务设计

## 目标

解决浏览器无法自动读取用户目录中 `usage_stats.json` 的问题，并提供不会污染真实数据的几百次调用演示模式。

## 方案

- 使用 Python 标准库启动跨平台本地 HTTP 服务。
- 服务默认仅监听 `127.0.0.1`。
- `/api/usage-stats` 固定读取当前用户目录中的统计文件，不接受 Web 参数指定其他文件。
- `/api/skill-description/<name>` 仅返回仓库技能的 frontmatter 描述。
- 静态路由只提供看板 HTML，不将仓库根目录暴露为 Web 目录。
- `--mock-count N` 在内存中生成恰好 N 次演示调用，不读取、不修改真实统计。
- 页面保留手动导入 JSON，作为 `file://` 场景的备用方式。

## 跨平台入口

- macOS / Linux：`make dashboard`、`make dashboard-mock`
- Windows：使用 `py` 或 `python` 运行 `dashboard_server.py`

## 安全边界

- 默认拒绝非回环地址监听。
- 校验 Host，请求只允许只读 GET/HEAD。
- API 禁止任意路径参数，统计响应禁止缓存。
- 限制统计文件大小并隐藏本机绝对路径错误信息。
- Mock 模式不产生统计文件写入。

## 验证

- Mock 总数与各技能计数之和严格等于目标次数。
- 覆盖真实数据读取、缺失文件、错误 JSON 和 Mock 不改文件。
- 覆盖健康检查、技能简介、静态页面和路径越界拒绝。
- 在浏览器中打开 500 次 Mock 看板，检查指标、排行榜和数据来源标记。
