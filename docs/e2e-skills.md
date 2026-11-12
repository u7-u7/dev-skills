# 🧪 E2E 双人组使用指南

> 🧰 把环境准备好，🕹️ 把用户流程跑起来，🔎 把失败证据留下来。

这两个技能围绕 [e2e-inc/e2e](https://github.com/e2e-inc/e2e) 为 Web 项目提供自动化测试流程，供 **Codex 与 Claude Code** 使用。它们是技能说明和辅助脚本，不是测试框架本身，也不包含 Node、浏览器或模型凭据。

## 🧩 谁负责什么？

| Skill | 适合的请求 | 交付 |
|---|---|---|
| `e2e-local-setup` | “测试环境缺什么？”“Chromium 找不到了” | 版本与依赖检查、浏览器准备、环境排障 |
| `e2e-project-testing` | “给这个 Web 项目补 smoke”“跑一下登录回归” | 配置、测试用例、执行结果与失败证据 |

沿用项目已有测试框架与包管理器，不因安装技能而替换 Playwright/Cypress。纯 API 和原生移动端使用对应工具；这两个技能只处理 Web 浏览器流程。

## 🚀 安装到客户端

### 路线 A：npm / npx 安装（推荐）📦

准备 Node ≥22.20、npm、Git 和可用的 Codex 或 Claude Code。若接下来要使用本文的 E2E 版本配对，Node 还需满足 `^22.22.3 || >=24.8.0`。在**要测试的项目根目录**运行以下单行命令，适用于 macOS/Linux 终端与 Windows PowerShell：

```bash
npx --yes skills@1.8.1 add u7-u7/dev-skills --skill e2e-local-setup e2e-project-testing --agent codex claude-code --yes
```

`npx` 从 npm 获取 [Skills CLI](https://github.com/vercel-labs/skills)，CLI 再从本 GitHub 仓库安装指定的两个技能；这里没有额外发布一个同名 npm 技能包。前一个 `--yes` 用于 npm 下载工具，后一个用于安装器确认。

| 需求 | 调整方式 |
|---|---|
| 只用于当前项目 | 使用上面的默认命令 |
| 所有项目都可用 | 在安装命令末尾加 `--global` |
| 只安装到 Codex | 将 agent 列表改为 `--agent codex` |
| 只安装到 Claude Code | 将 agent 列表改为 `--agent claude-code` |
| 链接不可用时复制文件 | 在命令末尾加 `--copy` |

项目级安装把完整技能放到 `.agents/skills/<skill-name>/`，并建立 Claude Code 的链接；默认还会生成或更新 `skills-lock.json`。安装后可检查：

```bash
npx --yes skills@1.8.1 list --agent codex claude-code
```

预期看到两个技能，同时属于 Codex 和 Claude Code。用户级安装对应在检查命令末尾加 `--global`。重新打开客户端后，再使用下文提示词。

喜欢先安装命令行工具，也可以执行：

```bash
npm install --global skills@1.8.1
skills add u7-u7/dev-skills --skill e2e-local-setup e2e-project-testing --agent codex claude-code --yes
```

更新或卸载本组技能（项目级示例）：

```bash
npx --yes skills@1.8.1 update e2e-local-setup e2e-project-testing --project --yes
npx --yes skills@1.8.1 remove e2e-local-setup e2e-project-testing --yes
```

用户级更新将 `--project` 改为 `--global`，用户级卸载增加 `--global`。完整卸载不限定 `--agent`，以同时清理这两个技能的共享目录和客户端链接。更新或卸载前保留自己在技能目录内的定制内容。不要与仓库安装器混合管理同名技能。

### 路线 B：沿用仓库安装器

在仓库根目录运行：

```bash
bash scripts/install_team_bundle.sh --profile e2e --targets codex,claude --no-interactive --dry-run
# 核对计划后安装；有同名目录时先保留并检查归属
bash scripts/install_team_bundle.sh --profile e2e --targets codex,claude --no-interactive --conflict skip
```

Windows PowerShell：

```powershell
.\install.ps1 preview -Profile e2e
.\install.ps1 install -Profile e2e
```

安装器使用仓库既有的 Codex 兼容目录和 Claude Code 用户目录，详情见[根 README](../README.md)。这里只安装两个 E2E 技能，不自动安装框架或运行测试。

### 路线 C：按客户端当前官方目录手动安装

同一份技能源码可被两种客户端读取，无需维护两份说明。官方文档列出的路径：

| 客户端 | 项目级 | 用户级 |
|---|---|---|
| Codex | `.agents/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` |
| Claude Code | `.claude/skills/<skill-name>/` | `~/.claude/skills/<skill-name>/` |

macOS/Linux 在本仓库根目录创建用户级软链接，已存在的目标保留并提示：

```bash
mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
for skill in e2e-local-setup e2e-project-testing; do
  for target in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
    if [[ -e "$target/$skill" || -L "$target/$skill" ]]; then
      echo "保留已有目标: $target/$skill"
    else
      ln -s "$PWD/skills/review/$skill" "$target/$skill"
    fi
  done
done
```

也可以把两个完整文件夹复制到目标目录。Windows 使用路线 A，或路线 B 的 Junction 安装，也可手动复制完整目录。不要仅复制 `SKILL.md`，脚本也需要随技能一起安装。**三条路线择一**，避免多个安装目录重复暴露同名技能；指向本仓库源码的软链接需要保留本仓库。

安装后重新打开客户端或按客户端方式刷新技能。参考：[Codex 官方技能文档](https://developers.openai.com/codex/skills/)、[Claude Code 官方技能文档](https://code.claude.com/docs/en/skills)。本指南里的 Claude 指本地 Claude Code，不代表上传到 claude.ai 就能访问本机项目。

## 🪄 如何召唤？

Codex：

```text
$e2e-local-setup 检查当前项目的 Node、框架和 Chromium 环境，沿用锁文件。
$e2e-project-testing 给当前 Web 项目补一组不依赖模型的登录页 smoke，运行并报告结果。
```

Claude Code：

```text
/e2e-local-setup 检查当前项目的 Web E2E 运行环境。
/e2e-project-testing 验证首页与登录路由，保留失败证据并说明阻塞项。
```

也可以直接说“给当前 Web 项目补 E2E 测试”，由客户端按技能描述自动匹配。

## 🛠️ 手动跑一遍

以下是 npm 项目的基线示例：**e2e 0.23.0 + @e2e-dev/web 0.15.5**。两个包不共用版本号，要求 Node **`^22.22.3 || >=24.8.0`**；已有其他版本时先核对包的 engines、类型和官方变更记录。

在被测项目安装依赖和对应 Chromium：

```bash
npm install --save-dev --save-exact e2e@0.23.0 @e2e-dev/web@0.15.5
npx --no-install @e2e-dev/web install chromium
```

pnpm/yarn/bun 使用对应本地执行命令，不混用锁文件。浏览器安装使用已安装的 Web 引擎，避免下载另一版 Playwright 导致 revision 不匹配。

在本仓库根目录生成 Vite 配置：

以下命令适用于已克隆本仓库的情况。通过 npm 安装的项目，可在被测项目中使用 `.agents/skills/e2e-project-testing/scripts/` 下的同名脚本，或让客户端按技能说明调用实际安装路径。

```bash
bash skills/review/e2e-project-testing/scripts/scaffold-e2e.sh \
  "<project-dir>" "http://localhost:5173" \
  node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
```

Next.js 换成以下启动参数：

```bash
bash skills/review/e2e-project-testing/scripts/scaffold-e2e.sh \
  "<project-dir>" "http://localhost:3000" \
  node node_modules/next/dist/bin/next dev --port 3000
```

若服务已经启动，省略 `node` 和后续参数即可生成只有 URL 的配置。已有配置与 smoke 文件逐个保留。配置中的 `APP_URL` 只覆盖访问地址，不会改变启动端口。自动启动命令的 `reuseExisting` 在 CI 中会被忽略；外部已运行的服务可以使用不带 command 的 URL 配置。

URL 使用固定端口的 HTTP(S) 基地址，不包含凭据、query 或 fragment；非 loopback 地址使用 HTTPS。动态端口需另行按框架文档配置，不属于脚手架默认路径。

完善生成的 smoke：基础 body 可见性只说明浏览器成功加载页面，真实回归还需要关键元素、路由或业务状态断言。然后运行：

```bash
bash skills/review/e2e-project-testing/scripts/run-e2e.sh "<project-dir>"
bash skills/review/e2e-project-testing/scripts/run-e2e.sh "<project-dir>" tests/smoke.e2e.ts --headed
```

运行器只使用项目本地 CLI，转发参数并返回真实退出码，不自动联网下载。其他配置文件格式或 Yarn PnP 请直接使用项目自己的本地 CLI。无 Bash 时由客户端按技能流程直接写配置和执行命令。

## 🎒 可选：便携运行环境

已有系统 Node 时无需设置。需要便携环境时，可以由用户准备如下目录：

```text
e2e-runtime/
├── node/          # node 可执行文件，或 bin/node
├── npm-global/    # 可选的全局命令
└── browsers/      # 已安装的匹配浏览器
```

```bash
export E2E_HOME="$HOME/tools/e2e-runtime"
source skills/review/e2e-local-setup/scripts/e2e-env.sh
```

Windows Git Bash 可设置 `E2E_HOME` 为自己的 Windows 路径，脚本会通过 `cygpath` 转换；浏览器路径沿用用户的 `PLAYWRIGHT_BROWSERS_PATH`，未设置时才选择便携目录里的 `browsers/`。安装和运行浏览器必须使用相同缓存路径。

`source` 只影响当前 shell；跨终端调用时重新激活。运行器在设置 `E2E_HOME` 时自动加载同级环境技能，非同级布局用 `E2E_ENV_FILE` 指向实际脚本。没有便携配置时直接沿用现有 PATH。

## 🩺 常见坑，提前绕开

| 现象 | 处理 |
|---|---|
| Node 版本报错 | 依包的 engines 检查，而非只看主版本号 |
| `spawn npm` / `.cmd` 错误 | 用 `node` 启动框架 JS bin，或先手动起服务 |
| `screen.locator is not a function` | 基线版本改用 `browser.locator` 或支持的语义定位器 |
| `APP_UNREACHABLE` | 检查服务、端口和启动日志 |
| 后端 500 | 结合约定判断环境阻塞还是应用缺陷，不能一律忽略 |
| 要看失败前发生了什么 | 查看实际 output 下的 trace、截图和报告；默认位于 `.e2e` |

📸 运行器不删除整个 `.e2e`。框架仍会管理并清理自己的 `results`；重跑前按需把失败报告归档到独立目录，保留回放缓存。AI `agent.act` / `agent.assert` 需要框架模型配置，普通 locator smoke 不需要模型 Key。密钥来自环境或框架认可的凭据来源，不提交到仓库；客户端账号不自动等于测试框架的模型授权。

## 🔗 兼容依据

- [e2e 0.23.0 配置类型](https://github.com/e2e-inc/e2e/blob/e2e@0.23.0/packages/e2e/src/types.ts)
- [官方 Web 初始化示例](https://github.com/e2e-inc/e2e/blob/e2e@0.23.0/packages/e2e/src/cli/init/engines.ts)
- [Web 引擎浏览器安装命令](https://github.com/e2e-inc/e2e/blob/e2e@0.23.0/packages/web/src/cli.ts)
- [运行器的结果与缓存处理](https://github.com/e2e-inc/e2e/blob/e2e@0.23.0/packages/e2e/src/run/runner.ts)

已在 macOS 检查脚本参数转发、已有文件保护、失败退出码、缓存保留和便携环境，并用基线框架完成 `e2e list`、`e2e doctor` 与隔离页面的 Chromium smoke（1 个用例通过）。Windows/Linux 实机尚未验证；具体业务回归仍以目标项目实际执行为准 🎯

另已在独立临时项目中通过 `skills@1.8.1` 从 GitHub 实际安装两个技能，并用 `skills list --json` 确认二者均被 Codex 和 Claude Code 识别、状态为 `tracked`；安装不修改本机已有用户级技能。安装器参数依据 [Skills CLI 官方参考](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)，核验日期：2026-11-12。
