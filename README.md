# DIY Agent Skills

这是一个只收录个人维护技能的轻量仓库。所有示例均使用中性命名，不依赖组织专用平台、私有域名、内部凭据或本机绝对路径。

## 技能目录

| 分类 | Skill | 用途 |
|---|---|---|
| Development | `brainstorming` | 开发前澄清需求、比较方案并确认设计 |
| Development | `ai-pair-programmer` | 分析代码库、实现改动并完成验证 |
| Development | `app-scanner` | 扫描多应用工作区并提取业务能力 |
| Review | `author-final-review` | 审查指定作者的最终代码状态 |
| Review | `code-review` | 检查代码质量、安全、性能和架构风险 |
| Review | `integration-test` | 根据变更风险设计集成测试用例 |
| Review | `full-review` | 汇总代码审查、影响分析和测试设计 |
| Review | `team-cr` | 为多人代码审查会议生成讨论清单 |
| Visualization | `diagram-creation` | 创建流程图、架构图、时序图和学习路线 |
| Platform | `git-worktree` | 创建和管理 Git worktree |
| Platform | `skill-usage-tracker` | 记录和查看本地技能使用统计 |

详细触发方式与依赖关系见 [skills/README.md](skills/README.md)。

## 推荐工作流

```text
brainstorming
    ↓
ai-pair-programmer ── app-scanner（多应用场景）
    ↓
author-final-review / code-review / integration-test
    ↓
full-review（需要汇总时）
```

## 安装

先预览安装动作：

```bash
make install-dry-run
```

安装 `config/profiles/diy.skills` 中的全部技能：

```bash
make install
```

卸载仓库创建的技能软链接：

```bash
make uninstall
```

## 仓库维护

```bash
make audit-skills   # 检查技能数量、重名和功能重叠
make stats          # 查看本地使用统计
make dashboard      # 打开本地统计看板
make clean          # 清理缓存文件
```

## 目录结构

```text
.
├── config/
│   ├── profiles/diy.skills
│   └── skills/repository-skills.manifest.json
├── docs/plans/
├── scripts/
└── skills/
    ├── development/
    ├── review/
    ├── visualization/
    └── platform/
```

## 维护原则

- 只保留个人持续维护的技能。
- 示例必须使用中性项目名、域名和数据。
- 禁止提交 token、cookie、密码、内部地址、生产数据和本机绝对路径。
- 删除或移动技能时，同步更新 profile、README、脚本路径和依赖说明。
