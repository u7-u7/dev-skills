---
name: full-review
description: 完整代码审查工作流:代码质量分析 + 影响面评估 + 集成测试用例生成。当用户需要以下操作时使用此技能:(1) 生成包含基本信息、变更说明、影响面分析、问题清单和集成测试用例的完整审查报告,(2) 一次性完成代码变更的全面审查,(3) 确保风险点和影响点在问题清单和测试用例中都被覆盖。输出标准化的完整审查报告到.doc/{分支名}/目录。
type: composite
depends_on:
  - author-final-review
  - code-review
  - integration-test
tags: workflow, devops, general
author: youqi.sjh
created: 2026-03-05T13:09:51Z
updated: 2026-03-10T10:00:00Z
---

# 完整代码审查

## 技能关系

本技能是**组合技能**，调用以下基础技能：
- ✅ `author-final-review` - 生成前三章（基本信息、变更说明、影响面分析）
- ➕ `code-review` - 第四章问题清单（10个评估维度深度审查）
- ➕ `integration-test` - 第五章测试用例清单（P0/P1用例 + 覆盖度追溯表）

## 依赖检查

本技能依赖同仓库的 `author-final-review`、`code-review` 和 `integration-test`。

执行前必须确认 `skills/review/` 下三个依赖均可用；若有缺失，停止执行并列出缺失技能。

## 调用流程

1. 调用 `author-final-review` 完整流程 → 获得前三章
2. 基于前三章 → 调用 `code-review` 深度审查 → 生成第四章问题清单
3. 基于前三章 → 调用 `integration-test` 用例设计 → 生成第五章测试用例清单
4. 合并输出单一汇总报告文件

---

## 角色定位

你是一位资深审查专家,负责把变更聚合为主题、扩展必要上下文,并产出**完整代码审查报告**(严格模板闭合)。

## 概述

本工作流串联三个审查流程,生成**单一汇总报告**:
1. **审查报告**:基本信息、变更说明、影响面分析(基础)
2. **代码质量审查**:问题清单
3. **集成测试**:P0/P1 测试用例

## 执行流程

### Step 0: 读取关联文件

读取以下共享文件的完整内容:
- [references/review-report.md](references/review-report.md)
- [references/codeReview.md](references/codeReview.md)
- [references/integration-test.md](references/integration-test.md)

目的:确保后续步骤严格按各文件格式输出

### Step 1: 执行审查报告基础流程

> 调用 `author-final-review` 技能的完整流程（Phase 1-4）
>
> 详见：[author-final-review/SKILL.md](../author-final-review/SKILL.md)
> 或直接参考：[references/review-report.md](references/review-report.md)

**输入**: git diff / git status
**输出**:
- 第一~三章正文（按 review-report.md 模板）
- 风险评估表（❗/⚠️/👀）
- 核心影响点明细表
- 兼容性声明

**注意**: 严格按 review-report.md 的 Phase 1-4 执行，不得跳过任何步骤

**输入**: 当前分支代码变更(git diff / git status)

**行动**: 严格按 review-report.md 执行 Phase 1 ~ Phase 4

**输出**(供后续 Step 使用):
- 第一~三章正文(按模板)
- 变更主题列表
- 风险评估表(❗/⚠️/👀)
- 核心影响点明细表
- 兼容性声明(如有)

### Step 2: 代码变更深度审查

> 基于 Step 1 的产出物，调用 `code-review` 的深度审查流程
>
> 详见：[references/codeReview.md](references/codeReview.md)

**输入**: Step 1 产出物(第一~三章正文 + 风险评估/影响点/兼容性声明)

**行动**: 严格按 codeReview.md 执行 Step 2 ~ Step 3

**输出**:
- 第四章问题清单(按 codeReview.md 模板)
- 第三章 `3.2 接口与 RPC 专项评估`（可扩展性/效率/Dubbo 合理性/接口规范性）
- codeReview.md 自检项全部通过

### Step 3: 风险驱动集成测试用例

> 基于 Step 1 的产出物，调用 `integration-test` 的测试用例生成流程
>
> 详见：[references/integration-test.md](references/integration-test.md)

**输入**: Step 1 产出物(第一~三章正文 + 风险评估/影响点/兼容性声明)

**行动**: 严格按 integration-test.md 执行 Step 2 ~ Step 3

**输出**:
- 第五章测试用例清单(按 integration-test.md 模板)
- 覆盖度追溯表
- integration-test.md 自检项全部通过

### Step 4: 汇总输出

**前置条件**: Step 1、Step 2、Step 3 完成

**行动**: 合并为单一报告文件

**输出**: `.doc/{分支名}/full-review-{时间戳}.md`

### Step 5: 自检与回退(不通过则丢弃并重写)

#### 格式自检
- 以本文件下方"输出模板(严格遵循)"为唯一标准
- 第一章、第二章、第三章:引用 review-report.md 的模板输出
- 第四章:引用 codeReview.md 的模板输出
- 第五章:引用 integration-test.md 的模板输出
- 命中任一禁项(新增章节/过程解释/推测性结论/百科式长清单)=> 丢弃并重写

#### 串联一致性自检(关键)
- **风险一致性**:review-report 风险评估表中的每个❗/⚠️风险点,在第四章或第五章至少被覆盖一次(问题或用例)
- **影响点一致性**:review-report 核心影响点明细表中的每个影响点,在第四章或第五章至少被覆盖一次(问题或用例)
- **追溯表完整**:第五章覆盖度追溯表中所有项均为✅已覆盖
- **接口与RPC一致性**:第三章 `3.2 接口与 RPC 专项评估` 中每个中高风险项，在第四章或第五章至少覆盖一次

## 输出格式

### 输出文件
- **目录**: `.doc/{分支名}/`
- **文件名格式**: `full-review-{时间戳}.md`
- **时间格式**: YYYYMMDD-HHmmss

### 输出模板(严格遵循)

```markdown
# 完整代码审查报告

## 📌 0. 首屏概览（先看结论）

| 维度 | 值 |
| :--- | :--- |
| 审查结论 | <✅ 可发 / ⚠️ 有条件 / ❌ 阻塞> |
| 主要风险 | <模块/链路> |
| Findings | Critical=<n>, High=<n>, Medium=<n>, Low=<n> |
| 测试覆盖结论 | <充分/部分/不足> |

## 一、基本信息

> 完整内容参考 review-report.md 模板

## 二、变更说明

> 完整内容参考 review-report.md 模板

## 三、影响面分析

> 完整内容参考 review-report.md 模板

### 3.2 接口与 RPC 专项评估（必填）
| 评估维度 | 当前状态 | 证据(file:line/调用链) | 优化建议 | 优先级 |
| :--- | :--- | :--- | :--- | :--- |
| 接口可扩展性 | <良好/一般/风险> | <evidence> | <suggestion> | <High/Medium/Low> |
| 效率与成本 | <良好/一般/风险> | <evidence> | <suggestion> | <High/Medium/Low> |
| Dubbo RPC 合理性 | <良好/一般/风险> | <evidence> | <suggestion> | <High/Medium/Low> |
| 接口规范性 | <良好/一般/风险> | <evidence> | <suggestion> | <High/Medium/Low> |

## 四、问题清单

> 完整内容参考 codeReview.md 模板

## 五、集成测试用例清单

> 完整内容参考 integration-test.md 模板
```

## 质量门禁补充（必过）

1. 第三章必须包含 `3.2 接口与 RPC 专项评估`，不得留空。
2. 若 Dubbo RPC 合理性存在中高风险，第四章或第五章必须给出对应问题或测试用例。
3. 若识别到无用/重复 RPC，必须给出至少一条优化建议（批量化/聚合/缓存/降级等）。

## 参考资料说明

本技能依赖以下共享文件:

- **[references/review-report.md](references/review-report.md)**: 审查报告基础流程（Phase 1-4），包含上下文扩展分析、影响面分析等方法论。
- **[references/codeReview.md](references/codeReview.md)**: 代码质量审查的完整流程和10个评估维度，包含问题等级定义和输出原则。
- **[references/integration-test.md](references/integration-test.md)**: 集成测试用例生成的完整流程，包含P0/P1用例优先级定义和生成规则。

执行时必须完整读取这些文件，确保输出的各章节严格遵循其模板格式。
