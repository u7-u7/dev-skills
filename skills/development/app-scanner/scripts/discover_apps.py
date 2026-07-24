#!/usr/bin/env python3
"""
应用发现脚本

扫描工作区，找到所有后端和前端应用（支持 Java/Go/Node.js/Python 及 React/Vue/Angular 等前端框架）。
生成的技能文件同时支持 Claude Code (.claude/skills/)、Cursor (.cursor/skills/)、Codex (.codex/skills/)。
默认同时生成到所有三个目录。
"""

import os
import sys
import argparse
import json
from pathlib import Path
from typing import List, Dict, Optional


# 后端项目识别特征
BACKEND_MARKERS = {
    'pom.xml': 'java-maven',
    'build.gradle': 'java-gradle',
    'build.gradle.kts': 'java-gradle-kts',
    'go.mod': 'go',
    'requirements.txt': 'python',
    'pyproject.toml': 'python',
    'setup.py': 'python',
}

# 前端框架依赖关键词
FRONTEND_DEPENDENCIES = [
    'react', 'react-dom', 'react-router-dom',
    'vue', 'vue-router', 'vuex', 'pinia',
    '@angular/core', '@angular/common',
    'svelte', 'solid-js',
    'next', 'nuxt', 'remix', '@remix-run',
]

# 前端构建工具/配置文件
FRONTEND_CONFIG_FILES = [
    'vite.config.js', 'vite.config.ts',
    'vue.config.js',
    'angular.json',
    'next.config.js',
    'webpack.config.js', 'webpack.config.ts',
    'rollup.config.js', 'rollup.config.ts',
    'tailwind.config.js', 'tailwind.config.ts',
]

# 前端典型目录
FRONTEN_DIR_PATTERNS = [
    'src/pages',
    'src/views',
    'src/components',
    'public',
]


def detect_frontend_project(dir_path: Path) -> Optional[Dict[str, str]]:
    """检测是否为前端项目"""
    package_json = dir_path / 'package.json'
    if not package_json.exists():
        return None

    try:
        with open(package_json, 'r', encoding='utf-8') as f:
            package_data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    dependencies = {}
    dependencies.update(package_data.get('dependencies', {}))
    dependencies.update(package_data.get('devDependencies', {}))

    detected_frameworks = []
    for dep in FRONTEND_DEPENDENCIES:
        if dep in dependencies:
            if dep.startswith('react'):
                detected_frameworks.append('react')
            elif dep.startswith('vue'):
                detected_frameworks.append('vue')
            elif dep.startswith('@angular'):
                detected_frameworks.append('angular')
            elif dep in ['svelte']:
                detected_frameworks.append('svelte')
            elif dep in ['solid-js']:
                detected_frameworks.append('solid')
            elif dep in ['next']:
                detected_frameworks.append('next')
            elif dep in ['nuxt']:
                detected_frameworks.append('nuxt')
            elif dep in ['remix'] or dep.startswith('@remix-run'):
                detected_frameworks.append('remix')

    if not detected_frameworks:
        for config_file in FRONTEND_CONFIG_FILES:
            if (dir_path / config_file).exists():
                detected_frameworks.append('unknown-framework')

    if detected_frameworks:
        has_frontend_structure = any(
            (dir_path / pattern).exists() for pattern in FRONTEN_DIR_PATTERNS
        )

        if has_frontend_structure or detected_frameworks:
            framework = detected_frameworks[0] if detected_frameworks else 'unknown'
            return {
                'type': 'frontend',
                'framework': framework,
                'config': 'package.json'
            }

    return None


def detect_backend_project(dir_path: Path) -> Optional[Dict[str, str]]:
    """检测是否为后端项目"""
    for marker, framework in BACKEND_MARKERS.items():
        if (dir_path / marker).exists():
            return {
                'type': 'backend',
                'framework': framework,
                'config': marker
            }

    package_json = dir_path / 'package.json'
    if package_json.exists():
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                package_data = json.load(f)

            dependencies = package_data.get('dependencies', {})
            dev_dependencies = package_data.get('devDependencies', {})

            backend_keywords = [
                'express', 'koa', 'nest', 'fastify',
                'django', 'flask', 'fastapi',
                'spring-boot', '@nestjs/common'
            ]

            for keyword in backend_keywords:
                if keyword in dependencies or keyword in dev_dependencies:
                    return {
                        'type': 'backend',
                        'framework': f'nodejs-{keyword}',
                        'config': 'package.json'
                    }
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return None


def find_apps(root_dir: str, exclude_dirs: List[str] = None) -> List[Dict[str, str]]:
    """查找所有应用（后端和前端）"""
    if exclude_dirs is None:
        exclude_dirs = [
            'node_modules', 'target', 'build', 'dist', 'out',
            '__pycache__', '.git', '.idea', '.vscode', 'vendor',
            'openspec/changes/archive',
        ]

    apps = []
    root_path = Path(root_dir).resolve()
    seen_names = {}

    for dir_path in root_path.rglob('*'):
        if not dir_path.is_dir():
            continue

        if any(excluded in str(dir_path) for excluded in exclude_dirs):
            continue

        if dir_path == root_path:
            continue

        project_info = None

        frontend_info = detect_frontend_project(dir_path)
        if frontend_info:
            project_info = frontend_info

        if not project_info:
            backend_info = detect_backend_project(dir_path)
            if backend_info:
                project_info = backend_info

        if project_info:
            app_name = dir_path.name

            if app_name in seen_names:
                app_name = f"{dir_path.relative_to(root_path).as_posix().replace('/', '-')}"

            project_info['name'] = app_name
            project_info['path'] = str(dir_path)
            project_info['relative_path'] = str(dir_path.relative_to(root_path))

            apps.append(project_info)
            seen_names[app_name] = project_info

    apps.sort(key=lambda x: (x['name'], x['type'] == 'backend', x['type']))
    return apps


def reduce_to_project_level(apps: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """将模块级结果压缩为项目级结果（每个一级目录保留一个应用）。"""
    groups: Dict[str, List[Dict[str, str]]] = {}
    for app in apps:
        relative_path = app.get('relative_path', '')
        top_dir = relative_path.split('/', 1)[0] if relative_path else relative_path
        groups.setdefault(top_dir, []).append(app)

    project_level_apps: List[Dict[str, str]] = []
    for top_dir, group in groups.items():
        # 优先使用一级目录本身（如 booking-manager）
        exact_top = [a for a in group if a.get('relative_path') == top_dir]
        if exact_top:
            project_level_apps.append(exact_top[0])
            continue

        # 否则选择最浅路径作为项目代表
        selected = sorted(
            group,
            key=lambda a: (
                a.get('relative_path', '').count('/'),
                len(a.get('relative_path', '')),
                a.get('name', '')
            )
        )[0]
        project_level_apps.append(selected)

    project_level_apps.sort(key=lambda x: (x['name'], x['type'] == 'backend', x['type']))
    return project_level_apps


def print_apps(apps: List[Dict[str, str]], format: str = 'table'):
    """打印应用列表"""
    if format == 'json':
        print(json.dumps(apps, indent=2, ensure_ascii=False))
    elif format == 'markdown':
        print("# 发现的应用\n")

        backend_apps = [a for a in apps if a.get('type') == 'backend']
        frontend_apps = [a for a in apps if a.get('type') == 'frontend']

        if backend_apps:
            print("## 后端应用\n")
            for i, app in enumerate(backend_apps, 1):
                type_icon = "☕" if 'java' in app.get('framework', '') else "🐹" if 'go' in app.get('framework', '') else "🐍" if 'python' in app.get('framework', '') else "📦"
                print(f"{i}. **{app['name']}** {type_icon}")
                print(f"   - 框架: `{app.get('framework', 'unknown')}`")
                print(f"   - 路径: `{app['relative_path']}`")
                print()

        if frontend_apps:
            print("## 前端应用\n")
            for i, app in enumerate(frontend_apps, 1):
                framework_icons = {
                    'react': '⚛️', 'vue': '💚', 'angular': '🅰️',
                    'svelte': '🔥', 'next': '▲', 'nuxt': '🟢',
                }
                icon = framework_icons.get(app.get('framework', ''), '🌐')
                print(f"{i}. **{app['name']}** {icon}")
                print(f"   - 框架: `{app.get('framework', 'unknown')}`")
                print(f"   - 路径: `{app['relative_path']}`")
                print()

        if not backend_apps and not frontend_apps:
            print("未找到任何应用")
    elif format == 'table':
        if not apps:
            print("未找到任何应用")
            return

        max_name_len = max(len(app['name']) for app in apps)
        max_type_len = max(len(app.get('type', '')) for app in apps)
        max_framework_len = max(len(app.get('framework', '')) for app in apps)
        max_path_len = max(len(app['relative_path']) for app in apps)

        print(f"{'序号':<4} {'应用名称':<{max_name_len}} {'类型':<{max_type_len}} {'框架':<{max_framework_len}} {'相对路径'}")
        print("-" * (max_name_len + max_type_len + max_framework_len + max_path_len + 15))

        for i, app in enumerate(apps, 1):
            type_str = app.get('type', '')
            framework_str = app.get('framework', '')
            type_icon = "后端" if type_str == 'backend' else "前端" if type_str == 'frontend' else type_str
            print(f"{i:<4} {app['name']:<{max_name_len}} {type_icon:<{max_type_len}} {framework_str:<{max_framework_len}} {app['relative_path']}")


def main():
    parser = argparse.ArgumentParser(
        description='发现工作区中的所有应用（支持后端和前端项目）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                              # 扫描当前目录
  %(prog)s /path/to/workspace           # 扫描指定目录
  %(prog)s --format json                # 输出 JSON 格式
  %(prog)s --format markdown            # 输出 Markdown 格式
  %(prog)s --granularity project        # 项目级（默认，按一级目录聚合）
  %(prog)s --granularity module         # 模块级（不聚合）
  %(prog)s --output apps.txt            # 保存到文件
  %(prog)s --exclude tmp --exclude logs # 排除目录

生成的技能文件同时输出到:
  - Claude Code: .claude/skills/
  - Cursor: .cursor/skills/
  - Codex: .codex/skills/
        """
    )
    parser.add_argument('root_dir', nargs='?', default='.', help='工作区根目录（默认为当前目录）')
    parser.add_argument('-f', '--format', choices=['table', 'json', 'markdown'], default='table', help='输出格式（默认：table）')
    parser.add_argument('--granularity', choices=['project', 'module'], default='project', help='扫描粒度（默认：project）')
    parser.add_argument('-o', '--output', help='输出到文件')
    parser.add_argument('--exclude', action='append', help='要排除的目录（可多次指定）')

    args = parser.parse_args()

    exclude_dirs = [
        'node_modules', 'target', 'build', 'dist', 'out',
        '__pycache__', '.git', '.idea', '.vscode', 'vendor',
        'openspec/changes/archive'
    ]
    if args.exclude:
        exclude_dirs.extend(args.exclude)

    apps = find_apps(args.root_dir, exclude_dirs)
    if args.granularity == 'project':
        apps = reduce_to_project_level(apps)

    output = ""
    if args.format == 'json':
        output = json.dumps(apps, indent=2, ensure_ascii=False)
    elif args.format == 'markdown':
        lines = ["# 发现的应用\n"]

        backend_apps = [a for a in apps if a.get('type') == 'backend']
        frontend_apps = [a for a in apps if a.get('type') == 'frontend']

        if backend_apps:
            lines.append("## 后端应用\n")
            for i, app in enumerate(backend_apps, 1):
                lines.append(f"{i}. **{app['name']}**")
                lines.append(f"   - 框架: `{app.get('framework', 'unknown')}`")
                lines.append(f"   - 路径: `{app['relative_path']}`")
                lines.append(f"   - 绝对路径: `{app['path']}`")
                lines.append("")

        if frontend_apps:
            lines.append("## 前端应用\n")
            for i, app in enumerate(frontend_apps, 1):
                lines.append(f"{i}. **{app['name']}**")
                lines.append(f"   - 框架: `{app.get('framework', 'unknown')}`")
                lines.append(f"   - 路径: `{app['relative_path']}`")
                lines.append(f"   - 绝对路径: `{app['path']}`")
                lines.append("")

        if not backend_apps and not frontend_apps:
            lines.append("未找到任何应用")

        output = "\n".join(lines)
    else:
        if not apps:
            output = "未找到任何应用"
        else:
            max_name_len = max(len(app['name']) for app in apps)
            max_type_len = max(len(app.get('type', '')) for app in apps)
            max_framework_len = max(len(app.get('framework', '')) for app in apps)
            max_path_len = max(len(app['relative_path']) for app in apps)

            lines = []
            lines.append(f"{'序号':<4} {'应用名称':<{max_name_len}} {'类型':<{max_type_len}} {'框架':<{max_framework_len}} {'相对路径'}")
            lines.append("-" * (max_name_len + max_type_len + max_framework_len + max_path_len + 15))

            for i, app in enumerate(apps, 1):
                type_str = app.get('type', '')
                framework_str = app.get('framework', '')
                type_icon = "后端" if type_str == 'backend' else "前端" if type_str == 'frontend' else type_str
                lines.append(f"{i:<4} {app['name']:<{max_name_len}} {type_icon:<{max_type_len}} {framework_str:<{max_framework_len}} {app['relative_path']}")

            output = "\n".join(lines)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"结果已保存到: {args.output}")
    else:
        print(output)

    backend_count = len([a for a in apps if a.get('type') == 'backend'])
    frontend_count = len([a for a in apps if a.get('type') == 'frontend'])
    print(f"\n发现 {len(apps)} 个应用 (后端: {backend_count}, 前端: {frontend_count})", file=sys.stderr)
    print("生成目录: .claude/skills/, .cursor/skills/, .codex/skills/", file=sys.stderr)


if __name__ == '__main__':
    main()
