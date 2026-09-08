# Skills Workflow

## 开发链路

1. 需求仍处于开放探索阶段时，先用 `brainstorming` 明确目标、边界和方案取舍。
2. `sdd-dev-workflow` 把原始需求或 PRD 整理为结构化需求，并强制扫描工作区代码。
3. 多应用工作区由 `app-scanner` 补充应用能力、依赖关系和影响范围；单仓直接读取真实代码证据。
4. `sdd-dev-workflow` 继续生成技术方案、`plan.md` 和 `tasks.md`，默认在任务拆分处收口。
5. 用户明确要求实现后，`ai-pair-programmer` 承接任务、代码修改、测试和交付说明。

## 审查链路

1. `author-final-review` 收集最终变更与影响范围。
2. `code-review` 深入检查质量、安全、性能和架构风险。
3. `integration-test` 根据风险点生成测试用例。
4. `full-review` 在需要单一汇总报告时编排前三项。
5. `team-cr` 在多人审查场景生成会议讨论清单。

## 辅助能力

- `diagram-creation`：按需为技术方案补充流程图、架构图或时序图。
- `skill-usage-tracker`：记录本地使用数据。
