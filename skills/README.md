# DIY Skills Index

仓库当前包含 16 个技能，按职责分为四类。

## Development

| Skill | 触发场景 | 主要输出 |
|---|---|---|
| `brainstorming` | 新功能、行为修改或方案存在选择 | 经确认的设计与边界 |
| `app-scanner` | 多应用工作区需要能力盘点 | 应用能力清单与应用级 `SKILL.md` |
| `sdd-dev-workflow` | 复杂度 61-100，或中等复杂度且用户选择 SDD 时准备开发任务 | 需求基线、代码证据、技术方案、Plan 与 Tasks |
| `ai-pair-programmer` | 复杂度 0-30 的快速开发，或用户选择直接实现时编写、修改、重构或测试代码 | 可验证的代码改动 |
| `ai-pair-programmer-v1-1` | v1.1 fork：Ub Mode 三段式结对开发，与原版并存供评审 | 可验证的代码改动 |
| `developer-resume-writer` | 根据项目或现有简历整理项目经历 | 项目简介、技术栈和项目亮点 |

## Review

| Skill | 触发场景 | 依赖 |
|---|---|---|
| `author-final-review` | 聚焦单一作者的最终变更 | 无 |
| `code-review` | 深度检查质量与风险 | `author-final-review` |
| `integration-test` | 为变更设计集成测试 | `author-final-review` |
| `e2e-local-setup` | 准备或修复 e2e-inc/e2e 的 Node、依赖和浏览器环境 | 无 |
| `e2e-project-testing` | 为 Web 项目编写并执行浏览器 smoke 和回归 | 无硬依赖；环境问题可交给 `e2e-local-setup` |
| `full-review` | 需要统一审查报告 | `author-final-review`、`code-review`、`integration-test` |
| `team-cr` | 多人或多模块审查会议 | 无 |

## Visualization

| Skill | 触发场景 | 主要输出 |
|---|---|---|
| `diagram-creation` | 需要流程、结构或时序可视化 | Mermaid、PlantUML 或其他图表源码 |
| `sketchnote-infographic` | 将主题、文章或笔记做成手绘知识海报 | 白底淡彩、中文清晰的海报图片及最终提示词 |

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

🧪 E2E 技能的 Codex / Claude Code 安装、命令示例和排障见 [使用指南](../docs/e2e-skills.md)。
