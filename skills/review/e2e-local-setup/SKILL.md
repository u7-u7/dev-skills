---
name: e2e-local-setup
description: 为 e2e-inc/e2e Web 测试检查和准备 Node.js、项目依赖与 Chromium 环境，排查版本、PATH 和浏览器缺失。适用于首次配置或修复本地 E2E 环境；为具体项目编写和执行测试时使用 e2e-project-testing。
---

# 🧰 E2E 本地环境准备

让 Codex 和 Claude Code 为当前项目准备可复现的 Web 测试环境。运行环境以实际检查为准，不假设某个盘符、操作系统、模型订阅或已安装软件存在。

## 定位脚本

本文的 `<skill-dir>` 指本文件所在目录，不是当前工作目录。根据客户端实际加载的路径定位；Claude Code 也可使用 `${CLAUDE_SKILL_DIR}`。不要把变量替换语法当成两种客户端都会自动提供的环境变量。

配套脚本适用于 macOS/Linux Bash 和 Windows Git Bash。PowerShell 用户可以从 Git Bash 执行脚本；没有 Bash 时，根据下面流程使用原生命令，不要求 WSL、Docker 或虚拟化。

## 1. 检查现有项目与环境

- 读取项目约定、`package.json`、锁文件和现有 E2E 配置；保留已有框架、包管理器和版本。
- 检查 `node --version`、包管理器版本，以及项目内 `e2e`、`@e2e-dev/web` 的实际版本和 `engines`。本包脚手架以 **e2e 0.23.0** 为兼容基线，其他版本先核对官方类型与迁移说明。
- 检查浏览器是否已经安装，以及 `PLAYWRIGHT_BROWSERS_PATH` 是否与安装时一致。不要因为系统安装了 Chrome 就认定框架所需的 Chromium 已就绪。
- 区分“在 Codex/Claude Code 中执行测试”和“测试内调用模型”：普通 locator/expect smoke 不需要模型 Key，AI 步骤按框架单独配置。不要假设客户端登录能自动提供框架凭据。

## 2. 激活可选的便携环境

系统 Node 已满足依赖要求时，直接使用。需要便携环境时显式设置 `E2E_HOME`，结构可包含 `node/`（或 `node/bin/`）、`npm-global/`、`browsers/`。这些目录不会自动创建或下载。

```bash
# 可选：设置到用户自己的便携工具目录
export E2E_HOME="$HOME/tools/e2e-runtime"
source "<skill-dir>/scripts/e2e-env.sh"
```

脚本仅在当前 shell 调整 PATH，并在存在 `browsers/` 且用户未设置浏览器路径时启用它；不修改 shell 配置或全局 npm 设置。`source` 后的环境仅在当前 shell 生效；独立终端工具调用需重新激活，或在同一次调用内运行后续命令。

## 3. 按项目约定安装

已有依赖优先使用锁文件恢复。首次引入本框架且项目使用 npm 时，可在被测项目根目录执行：

```bash
npm install --save-dev --save-exact e2e@0.23.0 @e2e-dev/web@0.15.5
npx --no-install @e2e-dev/web install chromium
```

这两个包的版本号不要求相同；此配对要求 Node `^22.22.3 || >=24.8.0`。pnpm/yarn/bun 项目使用对应命令并保留自己的锁文件；不要混用包管理器。其他版本以包元数据、CLI 帮助和[官方文档](https://e2e.com/docs)为准。通过已安装的 Web 引擎下载匹配的 Chromium，避免临时下载最新版 Playwright 造成 revision 不匹配。依赖、浏览器或系统库安装失败时报告具体阻碍，不自动使用 sudo 或绕过环境限制。

## 4. 验证后交接

在被测项目中使用本地 CLI（npm 项目可用 `./node_modules/.bin/e2e --version`），运行 `e2e doctor` 检查配置和运行依赖；先检查命令帮助，避免无意调用全局不同版本。项目还没有配置时，只完成环境检查，再交给 `e2e-project-testing` 初始化。

输出实际的系统/Node/框架版本、浏览器状态、依赖或锁文件改动、未完成项。不能仅凭安装成功就宣称 E2E 已通过。

## 🩺 排障

| 现象 | 检查 |
|---|---|
| Node engines 不匹配 | 确认当前 shell 的 Node 路径与安装包的 engines |
| 浏览器缺失或重复下载 | 对齐安装与运行时的浏览器缓存路径和 revision |
| `CONFIG_NOT_FOUND` | 确认在被测项目根目录运行，或先生成配置 |
| Windows 启动脚本报 spawn 错误 | 优先用 `node` 直接启动框架 JS 入口，或复用手动启动的服务 |
| 无 Bash | 使用原生命令完成同一检查流程；本包不依赖 WSL |

安装与客户端调用示例见仓库 [E2E 使用指南](../../../docs/e2e-skills.md)。单独复制此技能时，该指南不是运行依赖。
