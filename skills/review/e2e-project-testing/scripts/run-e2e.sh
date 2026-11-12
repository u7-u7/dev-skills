#!/usr/bin/env bash
# 使用项目本地 CLI，保留框架缓存与产物；退出码原样交给调用方。
set -euo pipefail

if [[ "${1:-}" == "--help" || $# -lt 1 ]]; then
  echo "用法: run-e2e.sh <项目目录> [测试文件或 e2e run 参数...]"
  echo "可选环境变量: E2E_HOME、E2E_ENV_FILE（环境激活脚本路径）"
  [[ "${1:-}" == "--help" ]] && exit 0
  exit 2
fi

SCRIPT_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${E2E_ENV_FILE:-$SCRIPT_DIR/../../e2e-local-setup/scripts/e2e-env.sh}"
if [[ -n "${E2E_ENV_FILE:-}" || -n "${E2E_HOME:-}" ]]; then
  [[ -f "$ENV_FILE" ]] || { echo "[run-e2e] 找不到环境脚本，请设置 E2E_ENV_FILE" >&2; exit 1; }
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

[[ -d "$1" ]] || { echo "[run-e2e] 项目目录不存在: $1" >&2; exit 1; }
cd -- "$1"
shift
[[ -f e2e.config.ts ]] || { echo "[run-e2e] 缺少 e2e.config.ts；已有其他格式配置时请直接用项目 CLI" >&2; exit 1; }
[[ -f node_modules/.bin/e2e ]] || { echo "[run-e2e] 缺少项目本地 e2e CLI，请按锁文件安装依赖" >&2; exit 1; }

# 不删除 .e2e：其中可能包含回放缓存与上一轮失败证据。
# 框架仍会管理自己的 results；需要保留完整报告时在运行前归档。
exec ./node_modules/.bin/e2e run "$@"
