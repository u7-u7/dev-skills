#!/usr/bin/env bash
# 生成配置和 smoke；已有文件逐个保留，不安装依赖。
set -euo pipefail

if [[ "${1:-}" == "--help" || $# -lt 2 ]]; then
  echo "用法: scaffold-e2e.sh <项目目录> <appUrl> [executable [args...]]"
  echo "省略 executable 时复用已经启动的服务。"
  [[ "${1:-}" == "--help" ]] && exit 0
  exit 2
fi

[[ -d "$1" ]] || { echo "[scaffold] 项目目录不存在: $1" >&2; exit 1; }
cd -- "$1"
shift
command -v node >/dev/null 2>&1 || { echo "[scaffold] 未找到 Node.js" >&2; exit 1; }

# JSON 序列化保留参数边界和引号，避免路径空格或输入内容变成脚本。
node - "$@" <<'NODE'
const fs = require('node:fs');
const [url, executable, ...args] = process.argv.slice(2);
try {
  const parsed = new URL(url);
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('需要 HTTP(S) 地址');
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error('应用基地址不能包含凭据、查询参数或 fragment');
  }
  const loopback = parsed.hostname === 'localhost' || parsed.hostname.endsWith('.localhost')
    || parsed.hostname === '[::1]' || /^127(\.\d{1,3}){3}$/.test(parsed.hostname);
  if (parsed.protocol === 'http:' && !loopback) throw new Error('非 loopback 地址需要 HTTPS');
  // 此脚手架复用固定端口；动态端口需要另行配置 {port} 和启动命令。
  if (parsed.port === '0') throw new Error('脚手架需要固定端口，不支持 port 0');
} catch (error) {
  console.error(`[scaffold] appUrl 无效: ${error.message}`);
  process.exit(2);
}

const app = { url };
if (executable) app.command = { executable, args, reuseExisting: true };
const config = `import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';

const app = ${JSON.stringify(app, null, 2)};
app.url = process.env.APP_URL ?? app.url;

export default {
  targets: [{ name: 'chromium', engine: web({ viewport: { width: 1440, height: 900 } }), app }],
  timeout: 120_000,
  workers: 1,
  retries: 0,
} satisfies E2EConfig;
`;
const smoke = `import { test } from '@e2e-dev/web';
import { expect } from 'e2e';

// 仅验证基础加载；请按实际页面补充关键元素和业务行为断言。
test.describe('smoke', () => {
  test('app shell loads', async ({ app, browser }) => {
    await app.open('/');
    await expect(browser.locator('body')).toBeVisible();
  });
});
`;

function writeNew(file, content) {
  try {
    fs.writeFileSync(file, content, { flag: 'wx' });
    console.log(`[scaffold] 生成 ${file}`);
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    console.log(`[scaffold] ${file} 已存在，保留原文件`);
  }
}

writeNew('e2e.config.ts', config);
fs.mkdirSync('tests', { recursive: true });
writeNew('tests/smoke.e2e.ts', smoke);
console.log('[scaffold] 下一步：完善 smoke 断言，再运行 run-e2e.sh');
NODE
