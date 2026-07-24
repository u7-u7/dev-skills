---
name: author-final-review
description: 当需要对一个或多个仓库中“单一指定作者”的最终态变更做全面 Bug 导向代码审查时使用。本技能基于 base..head 的最终代码状态审查，而不是逐个中间提交审查；适用于审查自己或他人的提交，但不适用于多人混合变更的整体审查。若作者、分支范围或应用范围缺失，先自动推断候选项并提出聚焦澄清问题。
tags: devops, general
author: youqi.sjh
created: 2026-03-05T13:09:51Z
updated: 2026-03-10T10:00:00Z
---

# Author Final Review

## Goal

Provide a comprehensive, bug-oriented review for **only one author's changes**, while avoiding false positives from early commits that were later fixed.

## Pain Points Solved

1. Avoids noisy findings from intermediate commits that were fixed later.
2. Focuses only on the target author's effective changes in final state.
3. Produces full issue list (not top-N), suitable for release readiness checks.

## Hard Constraints

1. Review scope must include only commits by the target author.
2. Analysis must be based on final state diff (`base..head`), not per-commit snapshots.
3. Do not report issues that do not exist in final code state.
4. Do not cap issue count (no "top 3-5" truncation).
5. Output must be a **full structured report**, not a short findings-only note.
6. Findings section must not be the only substantial section.

## Required Inputs

- `author`: unique identity (`email` preferred, fallback name)
- `base_ref`: baseline ref (e.g. `origin/main`, release branch)
- `head_ref`: final ref (e.g. `HEAD`, target release branch)
- `repos`: one or more repository paths involved in the project
- `apps` (optional but recommended): app/module list in scope

## Step 0: Input Completeness and Clarification (mandatory)

When user message does not provide full context, do not fail silently. Infer candidates first, then ask focused questions.

### 0.1 Infer candidates

```bash
python3 skills/review/author-final-review/scripts/infer_review_context.py \
  --repo "/path/repo-a" \
  --repo "/path/repo-b"
```

Inference includes:
- author suggestion: `git user.email`, `git user.name`, top authors in range
- branch suggestion: current branch, base candidates, resolved base/head
- app candidates: changed top-level/app modules in final diff range

### 0.2 Ask focused questions for missing inputs

If any key field is missing, ask one concise question each round until complete:

1. `author` missing:
   - "请确认本次审查作者（建议邮箱）。检测到候选：xxx@xx.com。"
2. `base_ref/head_ref` missing:
   - "请确认对比区间。检测到候选：base=origin/main, head=feature/xxx。是否使用？"
3. `repos/apps` missing:
   - "请确认涉及仓库与应用。检测到候选应用：apps/order, apps/cart。是否纳入？"

Question policy:
- Ask **one question per turn**.
- Prefer confirmation style with detected candidates.
- Do not start formal review until required fields are confirmed.

Only start review when author + branch range + repo scope are confirmed.

## Workflow

### Step 1: Build author scope

Run scope collector for all related repos:

```bash
python3 skills/review/author-final-review/scripts/collect_author_scope.py \
  --author "you@example.com" \
  --base "origin/main" \
  --head "HEAD" \
  --repo "/path/repo-a" \
  --repo "/path/repo-b"
```

Output includes:
- author commits
- files touched by author commits
- final-state diff stats for touched files
- collaborators touching same files in same range

### Step 2: Build review context from final-state impact (mandatory)

For each repo, summarize author-scope changes into business/technical themes (not per-file enumeration):

1. Aggregate related file changes into **change themes** (e.g., "预约消息消费链路重构").
2. Build entrypoint and dependency context for each theme:
   - entrypoints: HTTP/Dubbo/Job/MQ Consumer/internal scheduled task
   - downstream: DB/cache/MQ/external service
3. Produce risk candidates for each theme:
   - behavior compatibility
   - data consistency/idempotency
   - observability
4. Keep only evidence that belongs to author scope and final state.

### Step 3: Author-only final-state review

For each repo:

1. Build file set from author commits in `base..head`.
2. Compute final diff only in that file set:
   - `git diff base..head -- <author_file_set>`
3. If `apps` is provided, keep only files under selected apps/modules.
4. Review only final code content and final diff impact.
5. Ignore intermediate commit defects that are no longer present.
6. If file was touched by multiple authors, keep only hunks attributable to target author when stating evidence.

### Step 4: Comprehensive bug detection (no limit)

Check all candidate issues under final state:

1. Logic correctness and boundary handling
2. Nullability and exception flow
3. API/DTO compatibility and contract drift
4. Data consistency (DB/cache/MQ)
5. Concurrency and idempotency
6. Transaction boundaries and rollback safety
7. Performance hotspots and N+1 patterns
8. Security (auth, injection, sensitive data)
9. Observability gaps (logs/metrics/tracing)
10. Test coverage gaps for changed behavior
11. API extensibility:
    - backward compatibility (optional fields/default values)
    - enum/code extensibility and unknown value handling
    - pagination/filter/sort contract stability
    - response schema evolution safety
12. Efficiency and cost:
    - hot-path latency and avoidable serialization/deserialization cost
    - redundant loops / repeated computation / unnecessary object copy
    - avoidable DB/Cache/RPC round-trips
13. Dubbo RPC rationality:
    - unnecessary RPC calls (duplicate/fan-out/chained over-depth)
    - timeout/retry/bulkhead/threads settings reasonableness
    - can batch/cache/merge calls to reduce hop count
    - idempotency and degraded behavior under downstream failures
14. Interface规范性:
    - naming/DTO字段语义一致性
    - error code / error message contract consistency
    - request validation and boundary constraints completeness

### Step 5: Build full report content (mandatory)

Generate a complete report with all chapters in the required order:

1. Basic info
2. Change summary (theme-based)
3. Impact analysis (with risk table)
4. Findings list (author final-state only)
5. Regression test recommendations
6. Review notes and scope appendix

Do not skip chapters even when issue count is small.

### Step 6: Generate structured artifacts (mandatory)

After generating Markdown report, produce machine-readable JSON and state artifacts:

```bash
python3 skills/review/author-final-review/scripts/review_state_manager.py \
  --review-json ".doc/<branch>/author-final-review-YYYYMMDD-HHmmss.json" \
  --scope-json ".doc/<branch>/author-final-review-scope.json" \
  --baseline ".doc/baseline/author-final-review-baseline.json" \
  --status-file ".doc/<branch>/author-final-review-status.json" \
  --update-baseline \
  --update-status
```

This step must:
1. enrich `scope` + complexity tier (`Tier-L/M/H`)
2. compute severity/statistics summary
3. classify findings by baseline (`new/existing/resolved`)
4. merge finding workflow status (`new/accepted/fixed/false-positive/wont-fix`)

### Step 7: Evaluate release gate (mandatory)

Run gate check from structured JSON:
- block when `P0 > 0`
- block when `P1` with `new/reopened` status exists
- pass only when no blocker remains

Optional strict mode:

```bash
python3 skills/review/author-final-review/scripts/review_state_manager.py \
  --review-json ".doc/<branch>/author-final-review-YYYYMMDD-HHmmss.json" \
  --strict-gate
```

## Output Requirements

Report must include all confirmed issues (no arbitrary truncation), and each issue must include:

- `repo`
- `severity`
- `file:line`
- `problem`
- `final-state evidence`
- `impact`
- `fix suggestion`
- `verification suggestion`

Also include:

- Total issue count by severity
- Zero-issue statement only if no confirmed issues exist
- Excluded intermediate findings count (issues fixed before final state)
- Scope appendix: commit count / file count / collaborator overlap
- Risk-to-coverage mapping table (each high/medium risk must map to finding or test case)
- API & RPC optimization table (extensibility / efficiency / dubbo rationality / spec compliance)
- Structured JSON summary (`meta/scope/summary/findings/gates`)
- Baseline classification summary (`new_count/existing_count/resolved_count`)
- Finding workflow status summary (`new/accepted/fixed/false-positive/wont-fix`)

Style/length constraints:
- Minimum sections: 6 top-level sections (as defined above)
- Findings can be zero, but report body cannot be shorter than Summary+Findings only
- Prefer Chinese for report body when user request is Chinese
- Avoid long dense paragraphs; prefer tables/checklists/cards

### Visual Style Requirements (mandatory)

Report must be visually scannable:

1. Use emoji in top-level section titles (e.g., `📌`, `🧭`, `⚠️`, `🧪`, `✅`).
2. Add a **first-screen summary table** with key stats (scope, findings, risk, readiness).
3. Findings must be rendered as **one issue per mini-table** (not dense bullet-only blocks).
4. Use compact one-line conclusions in each section before details.
5. Keep each paragraph within 3 lines where possible; use tables for structured fields.
6. For zero-issue cases, still output the same visual structure and explicit readiness statement.

### Minimum Output Density (mandatory)

Use author scope complexity to prevent under-reporting:

1. Determine complexity tier from scope (`commit_count`, `file_count`):
   - `Tier-L`: commits < 8 and files < 15
   - `Tier-M`: commits in [8, 19] or files in [15, 39]
   - `Tier-H`: commits >= 20 or files >= 40
2. Findings count expectation:
   - `Tier-L`: no hard minimum; zero-issue allowed with evidence
   - `Tier-M`: expected findings >= 3
   - `Tier-H`: expected findings >= 5
3. If expected minimum is not reached, report is still allowed only when adding a mandatory appendix:
   - `低问题数合理性说明`
   - include 10-dimension checklist with final-state evidence file/line
   - include top risky files/modules and why not upgraded to issue
   - include residual risks + targeted regression cases
4. Never output a short list (e.g. 1-3 findings) for `Tier-H` without the appendix above.
5. Do not fabricate issues to satisfy counts; use the appendix mechanism instead.

Severity scale (required):
- `P0`: release blocker / data corruption / security critical
- `P1`: high risk behavior bug
- `P2`: medium risk correctness/perf/observability gap
- `P3`: low risk maintainability issue

## Output Template (strict)

```markdown
# 作者最终态代码审查报告（Author Final Review）

## 📌 0. 首屏概览（先看结论）
一句话结论：<可发布 / 有条件发布 / 不可发布>，主要风险在 <模块/链路>。

| 维度 | 值 |
| :--- | :--- |
| Author | <email/name> |
| Range | <base..head> |
| Repos | <list> |
| Apps/Modules | <list or all> |
| Review Time | <YYYY-MM-DD HH:mm:ss> |
| Scope | commits=<n>, files=<n> |
| Findings | P0=<n> / P1=<n> / P2=<n> / P3=<n> |
| Excluded Intermediate Findings | <n> |
| 发布建议 | <✅ 可发 / ⚠️ 有条件 / ❌ 阻塞> |

## 🧭 1. 审查范围与方法
### 1.1 输入确认
| 项 | 值 |
| :--- | :--- |
| 作者 | <author> |
| 对比区间 | <base..head> |
| 仓库 | <repos> |
| 应用范围 | <apps or all> |

### 1.2 方法说明（最终态、作者范围）
- 仅统计作者提交触达文件。
- 仅基于 `base..head` 最终态验证问题。
- 中途已修复问题不计入问题清单。

## 🔧 2. 变更说明（作者范围）
### 2.1 变更主题总览（按主题聚合）
| 主题 | 涉及模块 | 入口点 | 下游依赖 | 变更性质 |
| :--- | :--- | :--- | :--- | :--- |

### 2.2 关键调用链路（可选 mermaid）
（可选）Mermaid 示例：
flowchart LR
  A[入口] --> B[服务层]
  B --> C[存储/MQ/外部依赖]

### 2.3 兼容性关注点
| 关注点 | 风险等级 | 说明 |
| :--- | :--- | :--- |

## ⚠️ 3. 影响面分析
### 3.1 技术影响半径
| 影响点 | 影响类型 | 风险等级 | 说明 |
| :--- | :--- | :--- | :--- |

### 3.2 接口与 RPC 专项评估（必填）
| 评估维度 | 当前状态 | 证据(file:line/调用链) | 优化建议 | 优先级 |
| :--- | :--- | :--- | :--- | :--- |
| 接口可扩展性 | <良好/一般/风险> | <evidence> | <suggestion> | <P1/P2/P3> |
| 效率与成本 | <良好/一般/风险> | <evidence> | <suggestion> | <P1/P2/P3> |
| Dubbo RPC 合理性 | <良好/一般/风险> | <evidence> | <suggestion> | <P1/P2/P3> |
| 接口规范性 | <良好/一般/风险> | <evidence> | <suggestion> | <P1/P2/P3> |

### 3.3 风险结论
- 高风险项：<n>
- 中风险项：<n>
- 低风险项：<n>
- 发布判定依据：<简述>

## 🐞 4. 问题清单（仅作者范围、仅最终态）
> 每个问题一个“卡片表格”，禁止只用大段文字。

### 4.1 [P1] <问题标题>
| 字段 | 内容 |
| :--- | :--- |
| Repo | <repo> |
| File | <path:line> |
| Problem | <what is wrong> |
| Final-state evidence | <code-path/behavior evidence> |
| Impact | <runtime/user/business impact> |
| Fix suggestion | <concrete fix> |
| Verification suggestion | <how to verify fix> |

### 4.2 [P2] <问题标题>
| 字段 | 内容 |
| :--- | :--- |
| Repo | <repo> |
| File | <path:line> |
| Problem | <what is wrong> |
| Final-state evidence | <code-path/behavior evidence> |
| Impact | <runtime/user/business impact> |
| Fix suggestion | <concrete fix> |
| Verification suggestion | <how to verify fix> |

## 🧪 5. 回归测试建议（发布前）
### 5.1 P0（必须执行）
| 用例 | 风险来源 | 预期结果 | 覆盖问题ID |
| :--- | :--- | :--- | :--- |

### 5.2 P1（建议执行）
| 用例 | 风险来源 | 预期结果 | 覆盖问题ID |
| :--- | :--- | :--- | :--- |

## ✅ 6. 覆盖度追溯
| 风险点来源 | 风险描述 | 对应问题/用例 | 覆盖状态 |
| :--- | :--- | :--- | :--- |

## 📝 7. 审查说明
| 项 | 说明 |
| :--- | :--- |
| Scope boundary | <边界> |
| Exclusions | <排除项> |
| Assumptions | <假设> |

## 🧾 8. 低问题数合理性说明（当发现数低于复杂度阈值时必填）
| 维度 | 结论 | 证据(file:line) | 未升级为问题原因 |
| :--- | :--- | :--- | :--- |
```

## Output Path

Write consolidated artifacts:

1. Markdown report:
   - `.doc/<branch>/author-final-review-YYYYMMDD-HHmmss.md`
2. Structured JSON report:
   - `.doc/<branch>/author-final-review-YYYYMMDD-HHmmss.json`
3. Scope snapshot (from Step 1 output):
   - `.doc/<branch>/author-final-review-scope.json`
4. Branch-level status ledger:
   - `.doc/<branch>/author-final-review-status.json`
5. Global baseline ledger:
   - `.doc/baseline/author-final-review-baseline.json`

## Quality Gates

Before final output:

1. Verify every issue exists in final state.
2. Verify issue belongs to author-touched scope.
3. Remove duplicates with same root cause.
4. Keep distinct manifestations when impact differs.
5. Verify selected apps/modules are fully covered in author scope.
6. Verify output has all required top-level chapters in correct order.
7. Verify each P1/P2 risk is covered by a finding or explicit regression test item.
8. Reject per-file dump style; require theme-based summary.
9. Reject short-form output missing impact analysis or testing recommendations.
10. Apply complexity tier (`Tier-L/M/H`) using commit/file counts.
11. If findings below tier expectation, require Section VIII (`低问题数合理性说明`) with complete evidence.
12. For `Tier-H`, reject outputs with <=3 findings unless Section VIII is present and complete.
13. Ensure "do not fabricate issues" rule is respected; use explicit exclusion rationale instead.
14. Ensure Section `3.2 接口与 RPC 专项评估` is present and populated (no empty placeholders).
15. Ensure every `Dubbo RPC 合理性` high/medium risk maps to finding or regression test item.
16. Ensure at least one explicit optimization recommendation when redundant RPC is observed.
17. Ensure JSON report and Markdown findings count/severity are consistent.
18. Ensure every finding has stable fingerprint (`id`) for baseline/status tracking.
19. Ensure baseline classification exists (`new/existing/resolved`) when baseline file is configured.
20. Ensure gate decision is explicit in JSON (`gates.pass + gates.reasons`).

## Notes

- Use author email first for accurate filtering.
- For GitLab MRs, map MR -> commits -> final diff, then apply same rules.
- If `base_ref` is wrong or uncertain, ask user to confirm before review.
- If user asks to "参考 full-review 写法", keep author-only scope but adopt full structured narrative depth.
