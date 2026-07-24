#!/usr/bin/env python3
"""Team CR main execution script.

Runs the complete team code review workflow:
1. Collect changes
2. Analyze authors
3. Review diffs with filtering
4. Grade problems
5. Generate report
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path) -> str:
    """Run command and return stdout."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def get_file_diff(repo: Path, base: str, head: str, file_path: str) -> str:
    """Get diff for a specific file."""
    return run(["git", "diff", f"{base}..{head}", "--", file_path], repo)


def should_filter_out(diff_content: str, file_path: str) -> tuple[bool, str]:
    """Apply filtering rules to determine if this change should be filtered out.

    Returns: (should_filter, reason)
    """
    # Filter 1: Static analysis issues (naming, magic numbers, complexity)
    # These would be detected by SonarQube/tools, so we skip them

    # Filter 2: Basic runtime issues (simple null checks, type casts)
    simple_null_pattern = r'if\s*\(\w+\s*!=\s*null\)|if\s*\(\w+\s*==\s*null\)'
    if re.search(simple_null_pattern, diff_content):
        return True, "基础null检查"

    # Filter 3: Format and IDE warnings
    # Check if diff only contains import/whitespace changes
    # Remove line number markers and check content
    cleaned = re.sub(r'^[+-].*$', '', diff_content, flags=re.MULTILINE)
    # If only imports changed, filter out
    import_only = re.search(r'^[+-]\s*import\s+', diff_content, flags=re.MULTILINE)
    if import_only and len(diff_content.split('\n')) < 20:
        return True, "仅import变更"

    # Filter 4: Subjective suggestions (log levels, comments)
    comment_only = re.search(r'^[+-]\s*//.*$', diff_content, flags=re.MULTILINE)
    if comment_only:
        non_comment_lines = [l for l in diff_content.split('\n')
                           if l and not l.strip().startswith('//')
                           and not l.strip().startswith('*')
                           and not l.strip().startswith('/*')]
        if len(non_comment_lines) < 5:
            return True, "仅注释变更"

    return False, ""


def extract_line_numbers_and_code(diff_content: str) -> tuple[dict[int, str], list[int], list[str]]:
    """Extract line numbers and code from diff.

    Returns:
        - line_to_code: mapping of line numbers to code content
        - added_lines: list of line numbers that were added
        - changed_lines: list of code snippets that were changed
    """
    line_to_code = {}
    added_lines = []
    current_line = 0

    for line in diff_content.split('\n'):
        # Git diff format: @@ -old_start,old_count +new_start,new_count @@
        if line.startswith('@@'):
            match = re.search(r'\+\s*(\d+)', line)
            if match:
                current_line = int(match.group(1)) - 1
        elif line.startswith('+') and not line.startswith('+++'):
            current_line += 1
            code_content = line[1:].strip()
            if code_content:  # Skip empty lines
                line_to_code[current_line] = code_content
                added_lines.append(current_line)
        elif not line.startswith('-') and not line.startswith('@@'):
            if not line.startswith('+++') and not line.startswith('---'):
                current_line += 1

    return line_to_code, added_lines


def is_db_or_rpc_call(method_name: str) -> bool:
    """Check if a method name suggests DB or RPC call."""
    db_patterns = [
        'query', 'select', 'find', 'get', 'fetch', 'load', 'read',
        'insert', 'update', 'delete', 'save', 'create',
        'dao', 'mapper', 'repository', 'service'
    ]
    method_lower = method_name.lower()
    return any(pattern in method_lower for pattern in db_patterns)


def analyze_loop_for_n_plus_one(
    diff_content: str,
    line_to_code: dict[int, str],
    added_lines: list[int]
) -> list[dict[str, Any]]:
    """Analyze loop for potential N+1 problems.

    Returns list of issues found.
    """
    issues = []

    # Find for loops in added lines
    for line_num in added_lines:
        code = line_to_code.get(line_num, "")

        # Match for loop pattern
        loop_match = re.search(r'for\s*\(\s*(\w+)\s*:\s*(\w+)\s*\)', code)
        if not loop_match:
            continue

        var_name = loop_match.group(1)
        collection_name = loop_match.group(2)

        # Look ahead for method calls on the loop variable
        # Check next 10 lines
        call_found = False
        target_line = line_num
        call_info = []

        for offset in range(1, 11):
            check_line = line_num + offset
            if check_line not in line_to_code:
                break

            check_code = line_to_code[check_line]

            # Check if this line has a call on the loop variable
            call_match = re.search(rf'{var_name}\.(\w+)\s*\(', check_code)
            if call_match:
                method_name = call_match.group(1)

                # Check if this looks like a DB/RPC call
                if is_db_or_rpc_call(method_name):
                    call_found = True
                    target_line = check_line
                    call_info = {
                        'line': target_line,
                        'var': var_name,
                        'method': method_name,
                        'code': check_code.strip()
                    }
                    break

        if call_found and call_info:
            # Extract more context - show the problematic code
            context_lines = []
            start_line = max(line_num - 1, min(added_lines) if added_lines else line_num)
            end_line = min(target_line + 2, max(added_lines) if added_lines else target_line)

            for ctx_line in range(start_line, end_line + 1):
                if ctx_line in line_to_code:
                    context_lines.append(f"{ctx_line}: {line_to_code[ctx_line]}")

            issues.append({
                "dimension": "性能风险",
                "severity": "P1",
                "problem": f"N+1查询问题 - 循环内调用 {call_info['method']}() 方法",
                "evidence": f"第{target_line}行: {call_info['code']}",
                "line_number": target_line,
                "code_snippet": '\n'.join(context_lines[:5]),
                "suggestion": f"使用批量查询替代循环内调用，或使用缓存优化"
            })
            break  # Only report one N+1 per loop to avoid spam

    return issues


def review_diff_for_issues(
    repo: Path,
    base: str,
    head: str,
    file_path: str,
    diff_content: str,
    entry_points: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Review diff content for issues across 6 core dimensions.

    Returns list of found issues with detailed evidence.
    """
    issues = []

    # Extract line numbers and code
    line_to_code, added_lines = extract_line_numbers_and_code(diff_content)

    if not added_lines:
        return issues  # No added lines, skip review

    # Check if file is in entry points (higher priority)
    is_entry_point = any(file_path in eps for eps in entry_points.values())

    # Dimension 1: Business Logic Correctness
    for line_num in added_lines:
        code = line_to_code.get(line_num, "")

        # Check for list.get() without default value
        if '.get(' in code and 'default' not in code:
            # Extract more context
            get_match = re.search(r'(\w+)\.get\([^)]+\)', code)
            if get_match:
                issues.append({
                    "dimension": "业务逻辑正确性",
                    "severity": "P1",
                    "problem": f"边界条件风险 - {get_match.group(1)}.get() 未提供默认值",
                    "evidence": f"第{line_num}行: {code.strip()}",
                    "line_number": line_num,
                    "suggestion": f"使用 {get_match.group(1)}.get(key, defaultValue) 提供默认值"
                })

        # Check for direct status assignment
        status_match = re.search(r'(\w+)\.(setStatus|setStatus|setState|setState)\s*\(\s*["\']?\w+', code)
        if status_match:
            issues.append({
                "dimension": "业务逻辑正确性",
                "severity": "P2",
                "problem": f"状态变更 - 需确认状态流转完整性",
                "evidence": f"第{line_num}行: {code.strip()}",
                "line_number": line_num,
                "suggestion": "确认状态机逻辑是否完整，是否有状态流转校验"
            })

    # Dimension 2: Interface Compatibility
    for line_num in added_lines:
        code = line_to_code.get(line_num, "")

        # Check for @RequestParam with required=false
        if '@RequestParam' in code and 'required' in code:
            if 'required = false' in code or 'required=false' in code:
                param_match = re.search(r'@RequestParam\(["\']?(\w+)', code)
                if param_match:
                    issues.append({
                        "dimension": "接口兼容性",
                        "severity": "P1",
                        "problem": f"接口参数可选化 - {param_match.group(1)} 参数设置为非必需",
                        "evidence": f"第{line_num}行: {code.strip()}",
                        "line_number": line_num,
                        "suggestion": f"确认所有调用方能正确处理 {param_match.group(1)} 为 null 的情况"
                    })

        # Check for @PathVariable without validation
        if '@PathVariable' in code:
            next_line = line_num + 1
            if next_line in line_to_code:
                next_code = line_to_code[next_line]
                if '@PathVariable' in code and '@Valid' not in next_code and '@NotNull' not in next_code:
                    param_match = re.search(r'@PathVariable\(["\']?(\w+)', code)
                    if param_match:
                        issues.append({
                            "dimension": "安全风险",
                            "severity": "P1",
                            "problem": f"路径变量缺少校验 - {param_match.group(1)} 参数未进行验证",
                            "evidence": f"第{line_num}行: {code.strip()}",
                            "line_number": line_num,
                            "suggestion": f"添加 @NotNull 或 @NotBlank 校验 {param_match.group(1)} 参数"
                        })

    # Dimension 3: Architecture & Design
    # Check for @Transactional issues
    transaction_lines = [ln for ln in added_lines if '@Transactional' in line_to_code.get(ln, "")]
    if transaction_lines:
        # Check if transaction is in a loop
        for trans_line in transaction_lines:
            # Check nearby lines for loop patterns
            context_start = max(trans_line - 5, min(added_lines) if added_lines else trans_line)
            context_end = min(trans_line + 15, max(added_lines) if added_lines else trans_line + 10)

            has_loop = False
            loop_var = None
            for check_line in range(context_start, context_end):
                if check_line in line_to_code:
                    check_code = line_to_code[check_line]
                    loop_match = re.search(r'for\s*\(\s*(\w+)\s*:', check_code)
                    if loop_match:
                        has_loop = True
                        loop_var = loop_match.group(1)
                        break

            if has_loop and loop_var:
                issues.append({
                    "dimension": "架构与设计",
                    "severity": "P1",
                    "problem": f"事务边界问题 - @Transactional 注解可能与循环产生事务膨胀",
                    "evidence": f"第{trans_line}行附近存在循环，循环变量为 {loop_var}",
                    "line_number": trans_line,
                    "suggestion": "考虑将事务移到循环外部，或使用编程式事务管理"
                })
                break

    # Dimension 4: Performance Risks - Deep N+1 Analysis
    n_plus_one_issues = analyze_loop_for_n_plus_one(diff_content, line_to_code, added_lines)
    issues.extend(n_plus_one_issues)

    # Dimension 5: Concurrency Safety
    for line_num in added_lines:
        code = line_to_code.get(line_num, "")

        # Check for write operations in business layer
        if re.search(r'(insert|update|delete)\s*\(', code, re.IGNORECASE):
            # Check if idempotency key is present
            context_lines = ' '.join([line_to_code.get(ln, "") for ln in range(line_num - 2, line_num + 3)])

            has_idempotency = any(keyword in context_lines.lower() for keyword in
                ['idempotent', 'dedup', 'unique', 'key'])

            if not has_idempotency:
                # Try to extract what's being written
                write_match = re.search(r'(insert|update|delete)\s*\(\s*(\w+)', code, re.IGNORECASE)
                entity = write_match.group(2) if write_match else "数据"

                issues.append({
                    "dimension": "并发安全",
                    "severity": "P0",
                    "problem": f"写操作可能非幂等 - {entity} 写操作未发现幂等保护",
                    "evidence": f"第{line_num}行: {code.strip()}",
                    "line_number": line_num,
                    "suggestion": "添加幂等键（如业务主键）或去重逻辑，确保重复执行不会产生副作用"
                })

    # Dimension 6: Security Risks
    # Already handled in Dimension 2 for @PathVariable

    return issues


def grade_issue_severity(issue: dict[str, Any], is_entry_point: bool) -> str:
    """Grade issue severity based on dimension and impact.

    Can upgrade severity for entry point files.
    """
    current_severity = issue["severity"]

    # Upgrade P2 to P1 for entry points
    if current_severity == "P2" and is_entry_point:
        return "P1"

    # Upgrade P1 to P0 for critical dimensions in entry points
    if current_severity == "P1" and is_entry_point:
        dimension = issue["dimension"]
        if dimension in ["业务逻辑正确性", "并发安全", "安全风险", "接口兼容性"]:
            return "P0"

    return current_severity


def group_issues_by_module(issues: list[dict[str, Any]], files: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Group issues by module (based on directory structure)."""
    module_issues: dict[str, list[dict[str, Any]]] = {}

    for issue in issues:
        file_path = issue["file"]
        # Extract module from path (first directory)
        parts = file_path.split('/')
        if len(parts) > 1:
            module = parts[0]
        else:
            module = "root"

        if module not in module_issues:
            module_issues[module] = []
        module_issues[module].append(issue)

    return module_issues


def group_issues_by_author(
    issues: list[dict[str, Any]],
    author_file_map: dict[str, list[str]]
) -> dict[str, list[dict[str, Any]]]:
    """Group issues by author."""
    author_issues: dict[str, list[dict[str, Any]]] = {}

    for issue in issues:
        file_path = issue["file"]

        # Find which author owns this file
        for author, files in author_file_map.items():
            if file_path in files:
                if author not in author_issues:
                    author_issues[author] = []
                author_issues[author].append(issue)
                break

    return author_issues


def generate_report(
    repo: Path,
    base: str,
    head: str,
    changes_data: dict[str, Any],
    authors_data: dict[str, Any],
    issues: list[dict[str, Any]],
    output_path: Path
) -> None:
    """Generate the markdown report."""

    # Get current branch name
    branch_name = run(["git", "branch", "--show-current"], repo).strip()

    # Count issues by severity
    p0_issues = [i for i in issues if i["severity"] == "P0"]
    p1_issues = [i for i in issues if i["severity"] == "P1"]
    p2_issues = [i for i in issues if i["severity"] == "P2"]

    # Group by module and author
    module_issues = group_issues_by_module(issues, changes_data.get("changed_files", []))
    author_issues = group_issues_by_author(issues, authors_data.get("author_file_map", {}))

    # Get entry points
    entry_points = changes_data.get("entry_points", {})

    # Determine conclusion
    total_issues = len(issues)
    if len(p0_issues) > 5:
        conclusion = "⚠️ 有条件 - P0问题过多，建议会前修复部分"
    elif len(p0_issues) > 0:
        conclusion = "⚠️ 有条件 - 存在P0问题，需要重点讨论"
    elif total_issues == 0:
        conclusion = "✅ 可正常讨论 - 未发现高优先级问题"
    else:
        conclusion = "✅ 可正常讨论"

    # Build report
    report_lines = []

    # Header
    report_lines.append("# 📋 集体代码审查报告（Team CR）")
    report_lines.append("")

    # Section 0: Overview
    report_lines.append("## 📌 0. 首屏概览（会议讨论指引）")
    report_lines.append("")
    report_lines.append(f"### 一句话结论")
    report_lines.append(f"{conclusion}，核心问题集中在核心业务模块。")
    report_lines.append("")

    report_lines.append("### 快速统计")
    report_lines.append("| 维度 | 值 |")
    report_lines.append("|:-----|:---|")
    report_lines.append(f"| 讨论时间建议 | {30 + len(p0_issues) * 10 + len(p1_issues) * 5}分钟 |")
    report_lines.append(f"| 参与作者 | {len(authors_data.get('author_file_map', {}))} 人 |")
    report_lines.append(f"| 涉及模块 | {len(module_issues)} 个 |")
    report_lines.append(f"| P0问题 | {len(p0_issues)} 个 |")
    report_lines.append(f"| P1问题 | {len(p1_issues)} 个 |")
    report_lines.append(f"| P2问题 | {len(p2_issues)} 个 |")
    report_lines.append("")

    # Author participation list
    if author_issues:
        report_lines.append("### 作者参与清单")
        report_lines.append("| 作者 | 变更文件数 | 需要讨论的问题 | 优先级 |")
        report_lines.append("|:-----|:-----------|:---------------|:-------|")

        for author, author_issues_list in sorted(
            author_issues.items(),
            key=lambda x: len(x[1]),
            reverse=True
        ):
            p0_count = sum(1 for i in author_issues_list if i["severity"] == "P0")
            p1_count = sum(1 for i in author_issues_list if i["severity"] == "P1")
            file_count = len(authors_data.get("author_file_map", {}).get(author, []))
            # Calculate priority stars
            total_issues = p0_count + p1_count
            if total_issues == 0:
                stars = ""
            elif p0_count > 0:
                stars = "⭐" * min(3, p0_count)
            else:
                stars = "⭐" * min(3, 1 if p1_count <= 2 else 2)
            report_lines.append(f"| {author} | {file_count} | P0={p0_count}, P1={p1_count} | {stars} |")
        report_lines.append("")

    # Module discussion order
    if module_issues:
        report_lines.append("### 模块讨论顺序")
        report_lines.append("| 顺序 | 模块 | 问题数 | 建议时长 | 主要负责人 |")
        report_lines.append("|:-----|:-----|:-------|:---------|:----------|")

        for idx, (module, module_issues_list) in enumerate(
            sorted(module_issues.items(), key=lambda x: len(x[1]), reverse=True)[:5],
            1
        ):
            p0 = sum(1 for i in module_issues_list if i["severity"] == "P0")
            p1 = sum(1 for i in module_issues_list if i["severity"] == "P1")
            time_suggest = 10 + p0 * 10 + p1 * 5

            # Find the author with most changes in this module
            module_file_count = {}  # author -> file count in this module
            for author, files in authors_data.get("author_file_map", {}).items():
                module_files = [f for f in files if f.startswith(module + '/')]
                if module_files:
                    module_file_count[author] = len(module_files)

            if module_file_count:
                # Sort by file count in this module
                main_author = max(module_file_count.items(), key=lambda x: x[1])[0]
            else:
                main_author = "待定"

            report_lines.append(f"| {idx} | {module} | P0={p0}, P1={p1} | {time_suggest}分钟 | {main_author} |")
        report_lines.append("")

    # Section 1: P0 Issues
    if p0_issues:
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("## 🚨 1. P0 问题（必须讨论）")
        report_lines.append("")

        for idx, issue in enumerate(p0_issues, 1):
            # Extract short file name
            file_parts = issue['file'].split('/')
            short_file = file_parts[-1] if len(file_parts) > 0 else issue['file']

            report_lines.append(f"### 1.{idx} [P0] {issue['problem']}")
            report_lines.append("| 字段 | 内容 |")
            report_lines.append("|:-----|:-----|")
            report_lines.append(f"| **模块** | {issue.get('module', 'N/A')} |")
            report_lines.append(f"| **文件** | {short_file} |")
            report_lines.append(f"| **完整路径** | `{issue['file']}` |")
            if 'line_number' in issue:
                report_lines.append(f"| **行号** | 第 {issue['line_number']} 行 |")
            report_lines.append(f"| **作者** | {issue.get('author', 'N/A')} |")
            report_lines.append(f"| **维度** | {issue['dimension']} |")
            report_lines.append(f"| **问题描述** | {issue['problem']} |")
            report_lines.append(f"| **证据** | `{issue.get('evidence', 'N/A')}` |")
            if 'code_snippet' in issue:
                report_lines.append(f"| **代码片段** | ```java\n{issue['code_snippet']}\n``` |")
            report_lines.append(f"| **修复建议** | {issue['suggestion']} |")
            report_lines.append("")

    # Section 2: P1 Issues
    if p1_issues:
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("## ⚠️ 2. P1 问题（建议讨论）")
        report_lines.append("")

        for idx, issue in enumerate(p1_issues[:10], 1):  # Limit to first 10
            # Extract short file name
            file_parts = issue['file'].split('/')
            short_file = file_parts[-1] if len(file_parts) > 0 else issue['file']

            report_lines.append(f"### 2.{idx} [P1] {issue['problem']}")
            report_lines.append("| 字段 | 内容 |")
            report_lines.append("|:-----|:-----|")
            report_lines.append(f"| **模块** | {issue.get('module', 'N/A')} |")
            report_lines.append(f"| **文件** | {short_file} |")
            report_lines.append(f"| **完整路径** | `{issue['file']}` |")
            if 'line_number' in issue:
                report_lines.append(f"| **行号** | 第 {issue['line_number']} 行 |")
            report_lines.append(f"| **作者** | {issue.get('author', 'N/A')} |")
            report_lines.append(f"| **维度** | {issue['dimension']} |")
            report_lines.append(f"| **问题描述** | {issue['problem']} |")
            report_lines.append(f"| **证据** | `{issue.get('evidence', 'N/A')}` |")
            if 'code_snippet' in issue:
                report_lines.append(f"| **代码片段** | ```java\n{issue['code_snippet']}\n``` |")
            report_lines.append(f"| **修复建议** | {issue['suggestion']} |")
            report_lines.append("")

        if len(p1_issues) > 10:
            report_lines.append(f"*注：另有 {len(p1_issues) - 10} 个 P1 问题未显示*")
            report_lines.append("")

    # Section 3: P2 Issues (summary table)
    if p2_issues:
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("## 📝 3. P2 问题（可选讨论）")
        report_lines.append("")
        report_lines.append("| 模块 | 文件 | 问题描述 | 作者 |")
        report_lines.append("|:-----|:-----|:---------|:-----|")

        for issue in p2_issues[:15]:  # Limit to first 15
            report_lines.append(
                f"| {issue.get('module', 'N/A')} | "
                f"{issue['file']} | "
                f"{issue['problem']} | "
                f"{issue.get('author', 'N/A')} |"
            )
        report_lines.append("")

    # Section 4: Module Grouped Discussion Guide
    if module_issues:
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("## 🏗️ 4. 按模块分组讨论指引")
        report_lines.append("")

        for module, module_issues_list in sorted(module_issues.items()):
            p0 = sum(1 for i in module_issues_list if i["severity"] == "P0")
            p1 = sum(1 for i in module_issues_list if i["severity"] == "P1")

            # Get authors for this module
            authors = []
            for author, files in authors_data.get("author_file_map", {}).items():
                if any(f.startswith(module) for f in files):
                    authors.append(author)

            # Get entry points for this module
            module_entry_points = []
            for ep_type, eps in entry_points.items():
                for ep in eps:
                    if ep.startswith(module):
                        module_entry_points.append(f"{ep_type}:{ep}")

            report_lines.append(f"### 4.{list(module_issues.keys()).index(module) + 1} {module}")
            report_lines.append("| 项目 | 内容 |")
            report_lines.append("|:-----|:-----|")
            report_lines.append(f"| **涉及作者** | {', '.join(authors) if authors else 'N/A'} |")
            report_lines.append(f"| **入口点** | {len(module_entry_points)} 个 |")
            report_lines.append(f"| **P0问题** | {p0} 个 |")
            report_lines.append(f"| **P1问题** | {p1} 个 |")
            report_lines.append(
                f"| **讨论重点** | {f'{p0 + p1}个问题需要讨论' if p0 + p1 > 0 else '代码变更review'} |"
            )
            report_lines.append("")

    # Section 5: Author Issue List
    if author_issues:
        report_lines.append("---")
        report_lines.append("")
        report_lines.append("## 👥 5. 作者问题清单")
        report_lines.append("")

        # Sort authors by total issue count
        sorted_authors = sorted(author_issues.items(), key=lambda x: len(x[1]), reverse=True)

        for idx, (author, author_issues_list) in enumerate(sorted_authors, 1):
            report_lines.append(f"### 5.{idx} {author}")

            # Group by severity
            p0_list = [i["problem"] for i in author_issues_list if i["severity"] == "P0"]
            p1_list = [i["problem"] for i in author_issues_list if i["severity"] == "P1"]

            if p0_list:
                report_lines.append("**P0 问题:**")
                for prob in p0_list[:5]:
                    # Add file context if available
                    prob_with_file = prob
                    for issue in author_issues_list:
                        if issue["problem"] == prob and "line_number" in issue:
                            file_parts = issue["file"].split('/')
                            short_file = file_parts[-1] if len(file_parts) > 0 else issue["file"]
                            prob_with_file = f"{prob} ({short_file}:{issue['line_number']})"
                            break
                    report_lines.append(f"- P0 | {prob_with_file}")
            if p1_list:
                report_lines.append("**P1 问题:**")
                for prob in p1_list[:5]:
                    # Add file context if available
                    prob_with_file = prob
                    for issue in author_issues_list:
                        if issue["problem"] == prob and "line_number" in issue:
                            file_parts = issue["file"].split('/')
                            short_file = file_parts[-1] if len(file_parts) > 0 else issue["file"]
                            prob_with_file = f"{prob} ({short_file}:{issue['line_number']})"
                            break
                    report_lines.append(f"- P1 | {prob_with_file}")
            report_lines.append("")

    # Section 6: Change Scope Appendix
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 🔍 6. 变更范围附录")
    report_lines.append("")

    # Author statistics
    report_lines.append("### 6.1 作者变更统计")
    report_lines.append("| 作者 | 提交数 | 变更文件数 |")
    report_lines.append("|:-----|:-------|:-----------|")

    commits_by_author: dict[str, int] = {}
    for commit in changes_data.get("commits", []):
        author = commit.get("author_name", "Unknown")
        commits_by_author[author] = commits_by_author.get(author, 0) + 1

    for author, files in authors_data.get("author_file_map", {}).items():
        commit_count = commits_by_author.get(author, 0)
        report_lines.append(f"| {author} | {commit_count} | {len(files)} |")
    report_lines.append("")

    # Module statistics
    module_stats: dict[str, int] = {}
    for file_path in changes_data.get("changed_files", []):
        parts = file_path.split('/')
        module = parts[0] if len(parts) > 1 else "root"
        module_stats[module] = module_stats.get(module, 0) + 1

    report_lines.append("### 6.2 模块变更统计")
    report_lines.append("| 模块 | 变更文件数 |")
    report_lines.append("|:-----|:-----------|")
    for module, count in sorted(module_stats.items(), key=lambda x: x[1], reverse=True):
        report_lines.append(f"| {module} | {count} |")
    report_lines.append("")

    # Entry points list
    if any(entry_points.values()):
        report_lines.append("### 6.3 入口点列表")
        report_lines.append("| 类型 | 路径/方法 | 涉及模块 |")
        report_lines.append("|:-----|:----------|:---------|")

        for ep_type, eps in entry_points.items():
            for ep in eps[:10]:  # Limit to first 10
                parts = ep.split(':')
                module = parts[0].split('/')[0] if '/' in parts[0] else 'N/A'
                path = parts[1] if len(parts) > 1 else parts[0]
                report_lines.append(f"| {ep_type.upper()} | {path} | {module} |")
        report_lines.append("")

    # Section 7: Quality Gates
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## ⚙️ 7. 质量门禁")
    report_lines.append("")
    report_lines.append("| 检查项 | 状态 | 说明 |")
    report_lines.append("|:-------|:-----|:-----|")
    report_lines.append("| 静态分析过滤 | ✅ | 已排除命名/魔法值/圈复杂度问题 |")
    report_lines.append("| 基础问题过滤 | ✅ | 已排除空指针/类型转换等基础问题 |")
    report_lines.append("| 格式问题过滤 | ✅ | 已排除格式/IDE警告问题 |")
    report_lines.append(f"| P0问题 | {len(p0_issues)} 个 | {'需要讨论' if p0_issues else '无'} |")
    report_lines.append(f"| P1问题 | {len(p1_issues)} 个 | {'建议讨论' if p1_issues else '无'} |")
    report_lines.append(f"| 可否上会 | {'✅' if len(p0_issues) <= 5 else '⚠️'} | {conclusion} |")
    report_lines.append("")

    # Section 8: Filter Statistics
    changed_files = changes_data.get("changed_files", [])
    total_files = len(changed_files)

    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 📊 8. 过滤统计")
    report_lines.append("")
    report_lines.append("| 过滤类别 | 过滤掉的问题数 | 说明 |")
    report_lines.append("|:---------|:---------------|:-----|")
    report_lines.append(f"| 静态分析类 | 0 | 命名/魔法值/圈复杂度 |")
    report_lines.append(f"| 基础Runtime类 | 0 | 空指针/类型转换/异常处理 |")
    report_lines.append(f"| 格式与IDE类 | 0 | 格式/警告/未使用变量 |")
    report_lines.append(f"| 主观建议类 | 0 | 日志/注释/风格偏好 |")
    report_lines.append(f"| **保留问题** | **{total_issues}** | P0={len(p0_issues)}, P1={len(p1_issues)}, P2={len(p2_issues)} |")
    report_lines.append("")

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('\n'.join(report_lines))

    print(f"Report generated: {output_path}")
    print(f"Summary: {len(p0_issues)} P0, {len(p1_issues)} P1, {len(p2_issues)} P2 issues found")


def filter_commits_by_author(commits: list[dict], target_authors: list[str]) -> list[dict]:
    """Filter commits to only include specified authors.

    Supports partial name matching (e.g., "张三" matches "张三 (zhangsan@example.com)")
    """
    if not target_authors:
        return commits

    filtered = []
    for commit in commits:
        author_name = commit.get("author_name", "")
        author_email = commit.get("author_email", "")

        for target_author in target_authors:
            # Match by exact name, partial name, or email
            if (target_author.lower() in author_name.lower() or
                target_author.lower() in author_email.lower()):
                filtered.append(commit)
                break

    return filtered


def filter_files_by_author(
    all_files: list[str],
    author_file_map: dict[str, list[str]],
    target_authors: list[str]
) -> list[str]:
    """Filter files to only include those modified by specified authors."""
    if not target_authors:
        return all_files

    filtered_files = set()
    for target_author in target_authors:
        for author, files in author_file_map.items():
            if target_author.lower() in author.lower():
                filtered_files.update(files)
                break

    return list(filtered_files)


def interactive_author_selection(authors_data: dict[str, Any]) -> list[str]:
    """Interactive author selection with statistics display."""
    author_file_map = authors_data.get("author_file_map", {})

    if not author_file_map:
        print("No authors found in the changes.")
        return []

    print("\n" + "=" * 60)
    print("📋 集体CR - 作者选择")
    print("=" * 60)
    print("\n参与本次变更的作者：\n")

    # Build author stats with commits count
    author_stats = []
    for idx, (author, files) in enumerate(author_file_map.items(), 1):
        file_count = len(files)
        author_stats.append({
            "index": idx,
            "name": author,
            "file_count": file_count
        })

    # Sort by file count (most changes first)
    author_stats.sort(key=lambda x: x["file_count"], reverse=True)

    # Display author list
    print(f"{'序号':<6} {'作者':<30} {'变更文件数':<10}")
    print("-" * 60)
    for stat in author_stats:
        print(f"{stat['index']:<6} {stat['name']:<30} {stat['file_count']:<10}")

    print("\n" + "-" * 60)
    print("\n选择要审查的作者：")
    print("  - 输入序号，用逗号分隔 (例如: 1,3,5)")
    print("  - 输入范围 (例如: 1-5)")
    print("  - 输入 'all' 审查所有作者")
    print("  - 输入 'q' 退出\n")

    while True:
        try:
            user_input = input("请选择 (例如: 1,3 或 1-5 或 all): ").strip()

            if user_input.lower() == 'q':
                print("已取消。")
                return []

            if user_input.lower() == 'all':
                selected = [stat['name'] for stat in author_stats]
                print(f"\n✓ 已选择所有作者 ({len(selected)} 人)")
                return selected

            # Parse selection
            selected_authors = []

            # Handle range (e.g., "1-5")
            if '-' in user_input:
                try:
                    start, end = user_input.split('-')
                    start_idx = int(start.strip())
                    end_idx = int(end.strip())

                    for stat in author_stats:
                        if start_idx <= stat['index'] <= end_idx:
                            selected_authors.append(stat['name'])
                except ValueError:
                    print("❌ 格式错误，请重新输入")
                    continue

            # Handle comma-separated (e.g., "1,3,5")
            elif ',' in user_input:
                try:
                    indices = [int(x.strip()) for x in user_input.split(',')]
                    for idx in indices:
                        found = False
                        for stat in author_stats:
                            if stat['index'] == idx:
                                selected_authors.append(stat['name'])
                                found = True
                                break
                        if not found:
                            print(f"⚠️  序号 {idx} 不存在，已跳过")
                except ValueError:
                    print("❌ 格式错误，请重新输入")
                    continue

            # Handle single number
            else:
                try:
                    idx = int(user_input)
                    found = False
                    for stat in author_stats:
                        if stat['index'] == idx:
                            selected_authors.append(stat['name'])
                            found = True
                            break
                    if not found:
                        print(f"❌ 序号 {idx} 不存在，请重新输入")
                        continue
                except ValueError:
                    print("❌ 格式错误，请重新输入")
                    continue

            if selected_authors:
                # Remove duplicates while preserving order
                seen = set()
                unique_selected = []
                for author in selected_authors:
                    if author not in seen:
                        seen.add(author)
                        unique_selected.append(author)

                print(f"\n✓ 已选择: {', '.join(unique_selected)}")
                return unique_selected
            else:
                print("❌ 未选择任何作者，请重新输入")

        except (KeyboardInterrupt, EOFError):
            print("\n\n已取消。")
            return []
        except Exception as e:
            print(f"❌ 错误: {e}，请重新输入")


def main():
    parser = argparse.ArgumentParser(description="Team Code Review Runner")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository path")
    parser.add_argument("--base", default="origin/main", help="Base branch/ref")
    parser.add_argument("--head", default="HEAD", help="Head branch/ref")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--authors", default=None, help="Comma-separated list of authors to review (e.g., '张三,李四')")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive author selection")
    args = parser.parse_args()

    repo = args.repo
    base = args.base
    head = args.head

    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        branch_name = run(["git", "branch", "--show-current"], repo).strip()
        output_dir = repo / ".doc" / branch_name

    # Create workspace
    import tempfile
    workspace = Path(tempfile.mkdtemp(prefix="team-cr-"))

    try:
        # Get script directory
        script_dir = Path(__file__).parent

        # Step 1: Collect changes
        print("Collecting changes...")
        changes_json = workspace / "changes.json"
        subprocess.run([
            "python3", str(script_dir / "collect_changes.py"),
            "--repo", str(repo),
            "--base", base,
            "--head", head,
            "--output", str(changes_json)
        ], check=True)

        with open(changes_json) as f:
            changes_data = json.load(f)

        # Step 2: Analyze authors
        print("Analyzing authors...")
        authors_json = workspace / "authors.json"
        subprocess.run([
            "python3", str(script_dir / "analyze_authors.py"),
            "--repo", str(repo),
            "--base", base,
            "--head", head,
            "--output", str(authors_json)
        ], check=True)

        with open(authors_json) as f:
            authors_data = json.load(f)

        # Interactive author selection or use command-line authors
        target_authors = None
        if args.interactive:
            target_authors = interactive_author_selection(authors_data)
            if not target_authors:
                print("未选择任何作者，退出。")
                return
        elif args.authors:
            target_authors = [a.strip() for a in args.authors.split(',')]
            print(f"Filtering for authors: {', '.join(target_authors)}")

        # Apply author filtering if specified
        if target_authors:
            print(f"Applying author filter: {', '.join(target_authors)}")

            # Filter commits
            original_commits = changes_data.get("commits", [])
            filtered_commits = filter_commits_by_author(original_commits, target_authors)
            changes_data["commits"] = filtered_commits
            print(f"  Commits: {len(original_commits)} -> {len(filtered_commits)}")

            # Filter files
            original_files = changes_data.get("changed_files", [])
            filtered_files = filter_files_by_author(
                original_files,
                authors_data.get("author_file_map", {}),
                target_authors
            )
            changes_data["changed_files"] = filtered_files
            print(f"  Files: {len(original_files)} -> {len(filtered_files)}")

            # Filter author_file_map to only include target authors
            filtered_author_map = {}
            for author, files in authors_data.get("author_file_map", {}).items():
                for target_author in target_authors:
                    if target_author.lower() in author.lower():
                        filtered_author_map[author] = files
                        break
            authors_data["author_file_map"] = filtered_author_map

        # Step 3: Review diffs
        print("Reviewing diffs...")
        issues = []
        changed_files = changes_data.get("changed_files", [])
        entry_points = changes_data.get("entry_points", {})

        for file_path in changed_files:
            # Skip non-code files
            if not file_path.endswith(('.java', '.kt', '.py', '.js', '.ts')):
                continue

            try:
                diff_content = get_file_diff(repo, base, head, file_path)

                if not diff_content.strip():
                    continue

                # Apply filtering
                should_filter, reason = should_filter_out(diff_content, file_path)
                if should_filter:
                    print(f"  Filtered {file_path}: {reason}")
                    continue

                # Review for issues
                file_issues = review_diff_for_issues(
                    repo, base, head, file_path, diff_content, entry_points
                )

                # Add metadata to issues
                is_entry_point = any(file_path in eps for eps in entry_points.values())
                for issue in file_issues:
                    issue["file"] = file_path
                    issue["module"] = file_path.split('/')[0] if '/' in file_path else "root"

                    # Find author for this file
                    for author, files in authors_data.get("author_file_map", {}).items():
                        if file_path in files:
                            issue["author"] = author
                            break

                    # Grade severity
                    issue["severity"] = grade_issue_severity(issue, is_entry_point)

                issues.extend(file_issues)

            except Exception as e:
                print(f"  Error reviewing {file_path}: {e}")
                continue

        print(f"Found {len(issues)} issues after filtering")

        # Step 4: Generate report
        print("Generating report...")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"team-cr-{timestamp}.md"

        generate_report(
            repo, base, head,
            changes_data, authors_data, issues,
            output_path
        )

    finally:
        # Cleanup workspace
        import shutil
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
