---
name: e2e-project-testing
description: 使用 e2e-inc/e2e 为本地 Web 项目生成配置、编写浏览器 smoke 和回归测试、运行用例并分析失败证据。适用于验证页面、用户流程和前端回归；不用于原生移动端或纯 API 测试，也不替换已有的其他 E2E 框架。
---

# 🧪 Web 项目 E2E 测试

在 Codex 或 Claude Code 中，对用户指定的 Web 应用完成“识别项目 → 最小 smoke → 运行 → 定位 → 汇报”。使用实际版本与页面证据编写测试，不默认依赖模型。

## 路径与执行环境

`<skill-dir>` 是当前 `SKILL.md` 所在目录。根据客户端实际加载路径定位脚本；Claude Code 可使用 `${CLAUDE_SKILL_DIR}`，Codex 使用解析到的实际路径。不要写死用户名、盘符或安装目录。脚本需要 Bash 和 Node，Windows 使用 Git Bash；没有 Bash 时按同一流程直接操作文件与本地 CLI。

环境不齐时使用 `e2e-local-setup`；该技能未安装时，根据本项目的 Node engines、锁文件和浏览器要求补齐即可。两个技能分工互补，执行本技能不要求另一个技能目录必须存在。

## 1. 识别项目与测试边界

先读项目规则、`package.json`、锁文件、现有测试和启动配置。已有 Playwright/Cypress 等测试时，沿用项目框架；用户明确选择 e2e-inc/e2e 后才引入它。有现成 E2E 配置时优先修改和复用，不重新脚手架。

确认 URL、启动方式、后端可用性和测试账号来源。只覆盖有浏览器界面的 Web 层；纯 API 或原生移动端任务交给对应工具，不把它们判为应用不支持测试。用户仅授权测试时，不自行改产品逻辑或削弱断言。

## 2. 初始化缺失的配置

先按项目包管理器安装依赖。本包的配置基线是 `e2e@0.23.0` + `@e2e-dev/web@0.15.5`（Node `^22.22.3 || >=24.8.0`），已有其他版本时先核对类型和官方文档。

```bash
# 复用已经运行的应用，不创建启动命令
bash "<skill-dir>/scripts/scaffold-e2e.sh" "<project-dir>" "http://localhost:5173"

# 或由框架启动 Vite，每个参数单独传递
bash "<skill-dir>/scripts/scaffold-e2e.sh" "<project-dir>" "http://localhost:5173" \
  node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
```

脚本逐个保留已有 `e2e.config.ts` 和 `tests/smoke.e2e.ts`，不会安装依赖。`APP_URL` 可在运行时覆盖地址；它不会自动改启动命令的端口。生成的 body 可见性断言只是起点，要替换或扩展为真实页面行为验证。

地址使用固定端口的 HTTP(S) 基地址，不含凭据、查询参数或 fragment；非 loopback 主机要求 HTTPS。动态端口不属于此脚手架的默认配置，需要按框架文档单独设置。

Windows 中遇到 `spawn npm ENOENT` 或 `.cmd` 的 `EINVAL`，优先用 `node` 加框架 JS bin（从包的 `bin` 字段确认）。Next.js 示例参数是 `node_modules/next/dist/bin/next`、`dev`、`--port`、`3000`。不要把整条命令塞进一个参数。不能可靠启动时先手动起服务，生成仅含 URL 的配置。`reuseExisting: true` 在 CI 会被框架忽略，CI 应提供有效启动命令或使用外部已就绪 URL。

## 3. 编写最小但有意义的测试

- 测试放 `tests/*.e2e.ts`；`test` 来自 `@e2e-dev/web`，`expect` 来自 `e2e`。
- `app.open(path)` 导航；优先用角色、标签或项目 test id 定位，写选择器前核对页面或组件。0.23 中 `browser.locator(...)` 可用，`screen.locator(...)` 不可用。
- 从不依赖后端和模型的页面加载、路由守卫或表单 smoke 开始，再按用户目标验证关键行为、错误分支和外部依赖。不要堆叠仅验证 DOM 存在的用例来冒充业务回归。
- `agent.act` / `agent.assert` 是可选 AI 步骤；需要独立模型配置与授权。参考[官方文档](https://e2e.com/docs)使用 provider/model 对象和环境变量，不把 API Key 写入配置、日志或仓库，也不假设 Codex/Claude 的登录能直接供框架使用。

## 4. 执行、取证与修复

```bash
bash "<skill-dir>/scripts/run-e2e.sh" "<project-dir>"
bash "<skill-dir>/scripts/run-e2e.sh" "<project-dir>" tests/smoke.e2e.ts --headed
```

运行器使用项目的 `node_modules/.bin/e2e`，转发 `e2e run` 参数并保留退出码；不自动下载 CLI。便携环境可通过 `E2E_HOME` 启用配套环境脚本，非同级安装时用 `E2E_ENV_FILE` 指定路径。使用 Yarn PnP 或其他配置文件名时，直接通过项目包管理器执行本地 CLI。

不要在每次运行前删除整个 `.e2e`：它包含 agent 回放缓存和调试产物。框架会管理 `results`，需要保留上一轮证据时先归档相关产物，再重跑。自定义 output 路径时以实际配置为准。读取失败用例的 `trace.md`、截图与报告，必要时查看网络或启动日志。

区分配置/环境故障、测试写法错误和应用缺陷。后端缺失时记录受影响用例为阻塞或失败；只有明确限定为前端 smoke 时，才将对应 API 错误列为已知环境限制。不要一律忽略 500，也不要靠改弱断言或无限重试换取通过。修复后做针对性验证，同一阻碍反复出现且无新证据时报告原因。

## 5. 交付结果

报告实际运行命令、通过/失败/跳过/阻塞数量、验证的业务范围、证据与改动文件。仅 scaffold、未安装浏览器或未执行测试时如实说明，不宣称整套回归通过。仓库安装和调用示例见 [E2E 使用指南](../../../docs/e2e-skills.md)，该指南不是单独安装时的运行依赖。
