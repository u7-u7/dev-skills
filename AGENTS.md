# Agents & Skills 管理

最后更新：2026-07-29

## 强制规则

- 执行任何技能前，先使用 `skill-usage-tracker` 记录本次调用。
- 仓库只收录个人维护的 DIY skills，不引入第三方技能副本或组织专用集成。
- 文档、示例和测试数据必须使用中性名称，禁止出现私有域名、凭据、生产数据和本机绝对路径。
- 未经用户明确要求，不提交、不推送、不修改远端仓库。

## Development

- **brainstorming** - 需求分析与方案设计
- **ai-pair-programmer** - AI 结对编程
- **app-scanner** - 应用扫描与能力提取
- **sdd-dev-workflow** - 需求、代码扫描、技术方案、Plan 与 Tasks 编排

## Review

- **author-final-review** - 指定作者最终态审查
- **code-review** - 代码质量审查
- **integration-test** - 集成测试设计
- **full-review** - 完整审查工作流
- **team-cr** - 团队审查会议准备

## Visualization

- **diagram-creation** - 流程图、架构图和时序图

## Platform

- **skill-usage-tracker** - 本地技能使用统计

## 目录约束

- 技能源码只放在 `skills/<category>/<skill-name>/`。
- 每个技能必须包含有效的 `SKILL.md`。
- 组合技能的 `depends_on` 必须指向仓库中真实存在的技能。
- 默认安装清单由 `config/profiles/diy.skills` 维护。
