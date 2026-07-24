---
name: skill-usage-tracker
description: 本仓库中每次执行任意技能都必须先触发本技能。调用任何其他技能（含本技能自身）前，先执行统一入口记录使用，再继续执行目标技能；同时用于查看与重置技能统计和排行。
tags: platform, general
author: youqi.sjh
created: 2026-03-05T13:09:51Z
updated: 2026-03-10T10:00:00Z
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
