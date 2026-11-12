#!/usr/bin/env bash
# 在当前 shell 激活可选的便携环境；不下载依赖、不修改全局配置。
# 用法: source <skill目录>/scripts/e2e-env.sh

_e2e_activate() {
  local runtime_dir="${E2E_HOME:-}" candidate
  if [[ -n "$runtime_dir" ]]; then
    if command -v cygpath >/dev/null 2>&1; then
      runtime_dir="$(cygpath -u "$runtime_dir")" || return 1
    fi
    [[ -d "$runtime_dir" ]] || { echo "[e2e-env] E2E_HOME 目录不存在" >&2; return 1; }
    # 倒序加入 PATH，让便携 Node 优先于 npm 全局命令和系统 Node。
    for candidate in npm-global/bin npm-global node/bin node; do
      [[ ! -d "$runtime_dir/$candidate" ]] || export PATH="$runtime_dir/$candidate:$PATH"
    done
    if [[ -z "${PLAYWRIGHT_BROWSERS_PATH:-}" && -d "$runtime_dir/browsers" ]]; then
      if command -v cygpath >/dev/null 2>&1; then
        export PLAYWRIGHT_BROWSERS_PATH="$(cygpath -w "$runtime_dir/browsers")"
      else
        export PLAYWRIGHT_BROWSERS_PATH="$runtime_dir/browsers"
      fi
    fi
  fi

  command -v node >/dev/null 2>&1 || { echo "[e2e-env] 未找到 Node.js，请先安装项目所需版本" >&2; return 1; }
  echo "[e2e-env] node -> $(node --version)"
  echo "[e2e-env] browsers -> ${PLAYWRIGHT_BROWSERS_PATH:-使用 Playwright 默认缓存}"
  echo "[e2e-env] CLI 版本与兼容性请在被测项目中检查"
}

if _e2e_activate; then
  unset -f _e2e_activate
else
  unset -f _e2e_activate
  return 1 2>/dev/null || exit 1
fi
