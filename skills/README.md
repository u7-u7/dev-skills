# DIY Skills Index

仓库当前包含 12 个技能，按职责分为四类。

## Development

| Skill | 触发场景 | 主要输出 |
|---|---|---|
| `brainstorming` | 新功能、行为修改或方案存在选择 | 经确认的设计与边界 |
| `app-scanner` | 多应用工作区需要能力盘点 | 应用能力清单与应用级 `SKILL.md` |
| `sdd-dev-workflow` | 从原始需求或 PRD 准备开发任务 | 需求基线、代码证据、技术方案、Plan 与 Tasks |
| `ai-pair-programmer` | 编写、修改、重构或测试代码 | 可验证的代码改动 |
| `developer-resume-writer` | 根据项目或现有简历整理项目经历 | 项目简介、技术栈和项目亮点 |

## Review

| Skill | 触发场景 | 依赖 |
|---|---|---|
| `author-final-review` | 聚焦单一作者的最终变更 | 无 |
| `code-review` | 深度检查质量与风险 | `author-final-review` |
| `integration-test` | 为变更设计集成测试 | `author-final-review` |
| `full-review` | 需要统一审查报告 | `author-final-review`、`code-review`、`integration-test` |
| `team-cr` | 多人或多模块审查会议 | 无 |

## Visualization

| Skill | 触发场景 | 主要输出 |
|---|---|---|
| `diagram-creation` | 需要流程、结构或时序可视化 | Mermaid、PlantUML 或其他图表源码 |

## Platform

| Skill | 触发场景 | 主要输出 |
|---|---|---|
| `skill-usage-tracker` | 执行技能或查看统计 | `~/usage_stats.json` 中的本地统计 |

## 目录

```text
skills/
├── development/
├── review/
├── visualization/
└── platform/
```

每个技能目录必须自包含运行所需的说明、脚本、参考资料和模板。
