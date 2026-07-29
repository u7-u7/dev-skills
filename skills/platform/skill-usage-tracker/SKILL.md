---
name: skill-usage-tracker
description: 本仓库中每次执行任意技能都必须先触发本技能。调用任何其他技能（含本技能自身）前，先执行统一入口记录使用，再继续执行目标技能；同时用于查看与重置技能统计和排行。
tags: platform, general
author: youqi.sjh
created: 2026-03-05T13:09:51Z
updated: 2026-07-29T16:30:00Z
---

# Skill Usage Tracker

## Overview

This skill provides deterministic skill-usage tracking for this repository.

Core rule: **explicit record first, then execute the skill**.

## Mandatory Rule

Before executing any skill, run:

```bash
bash "$SKILL_DIR/scripts/skill-stats" record --skill "<skill-name>" --context "<short scenario>"
```

Then execute the target skill.

Do not rely on passive or implicit tracking.

## Canonical Commands

### Record

```bash
bash "$SKILL_DIR/scripts/skill-stats" record --skill "brainstorming" --context "梳理需求与方案"
```

### View all stats

```bash
bash "$SKILL_DIR/scripts/skill-stats" view
```

### View one skill

```bash
bash "$SKILL_DIR/scripts/skill-stats" view --skill "brainstorming"
```

### Reset

```bash
bash "$SKILL_DIR/scripts/skill-stats" reset --skill "brainstorming"
bash "$SKILL_DIR/scripts/skill-stats" reset
```

### Repair (history backfill)

```bash
bash "$SKILL_DIR/scripts/skill-stats" repair
```

### Refresh README snapshot

```bash
bash "$SKILL_DIR/scripts/skill-stats" sync-readme
```

## 本地可视化看板

仓库内置跨平台本地服务，浏览器通过固定只读接口自动加载当前用户的 `~/usage_stats.json`：

```bash
# macOS / Linux：真实统计
make dashboard

# macOS / Linux：500 次内存 Mock 数据
make dashboard-mock
```

Windows PowerShell：

```powershell
# 真实统计
py .\skills\platform\skill-usage-tracker\scripts\dashboard_server.py --open

# 500 次内存 Mock 数据
py .\skills\platform\skill-usage-tracker\scripts\dashboard_server.py --open --mock-count 500
```

约束：

- 默认只监听 `127.0.0.1`，不上传数据，也不暴露整个仓库。
- Mock 数据只存在于服务内存中，不读取、不修改真实统计文件。
- 直接以 `file://` 打开页面时，使用“导入本地 JSON”作为备用方式。
- 全部时间使用累计 `count`；7/30 天窗口基于每技能最近保留的 50 条 `history`，可能低于真实窗口次数。

## Data Path

唯一统计文件：

1. User home file: `~/usage_stats.json`

执行要求：

- 只使用 `~/usage_stats.json`
- 首次切换时可从仓库根目录旧文件迁移
- 不再支持 skill 包内 legacy data 路径

README snapshot sync is manual by design:

- `record/reset/repair` only update stats data
- `sync-readme` updates the `README.md` live snapshot block when needed

## Integration Snippet

For any other skill, add this at skill start:

```bash
bash "$SKILL_DIR/scripts/skill-stats" record --skill "<current-skill-name>" --context "<short scenario>"
```

## Notes

- `bash "$SKILL_DIR/scripts/skill-stats"` is the single stable entrypoint (不依赖当前 cwd)。
- 若在当前仓库根目录执行，`scripts/skill-stats` 也可使用。
- If needed, direct command is:

```bash
python3 skills/platform/skill-usage-tracker/scripts/update_stats.py <action> [args]
```
