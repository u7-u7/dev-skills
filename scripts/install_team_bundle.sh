#!/bin/bash
# Team bundle installer (profile-based)
# Installs selected skills to multiple IDE targets via symlink.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✅ [INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠️  [WARN]${NC} $1" >&2; }
log_error() { echo -e "${RED}❌ [ERROR]${NC} $1" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$ROOT_DIR/skills"
SKILL_SUFFIX="$(basename "$ROOT_DIR")"

PROFILE="diy"
DRY_RUN=0
UNINSTALL=0
FORCE=0
ONLY="skills"
CONFLICT_POLICY="ask"
SKILL_CONFLICT_POLICY="overwrite"
INTERACTIVE_MODE="auto"
PERSIST_EXTRA="ask"
TARGETS_CSV="cursor,claude,codex"

usage() {
  cat <<EOF
用法:
  bash scripts/install_team_bundle.sh [--profile diy] [--only skills] [--targets cursor,claude,codex] [--conflict ask|overwrite|skip] [--skill-conflict overwrite|skip|rename|ask] [--persist-extra ask|always|never] [--interactive|--no-interactive] [--force] [--dry-run] [--uninstall]

参数:
  --profile <name>  profile 名称（位于 config/profiles，默认: diy）
  --only <scope>    安装范围: skills（默认: skills）
  --targets <list>  客户端目标：cursor,claude,codex（默认: 全部）
  --conflict <mode> 目标重名时策略: ask|overwrite|skip（默认: ask）
  --skill-conflict <mode> skill 重名策略: overwrite|skip|rename|ask（默认: overwrite）
  --persist-extra <mode> 追加未收录 skills 是否写回 profile: ask|always|never（默认: ask）
  --interactive     强制启用交互选择安装项（仅 TTY）
  --no-interactive  禁用交互，按 profile 全量安装
  --force           强制覆盖已存在目标（目录/文件/软链）
  --dry-run         仅打印动作，不落地
  --uninstall       卸载该 profile 已安装的软链接
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --only)
      ONLY="${2:-}"
      shift 2
      ;;
    --targets)
      TARGETS_CSV="${2:-}"
      shift 2
      ;;
    --conflict)
      CONFLICT_POLICY="${2:-}"
      shift 2
      ;;
    --skill-conflict)
      SKILL_CONFLICT_POLICY="${2:-}"
      shift 2
      ;;
    --persist-extra)
      PERSIST_EXTRA="${2:-}"
      shift 2
      ;;
    --interactive)
      INTERACTIVE_MODE="on"
      shift
      ;;
    --no-interactive)
      INTERACTIVE_MODE="off"
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log_error "未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

SKILLS_PROFILE="$ROOT_DIR/config/profiles/${PROFILE}.skills"

case "$ONLY" in
  skills) ;;
  *)
    log_error "--only 参数非法: ${ONLY}（当前仅支持: skills）"
    exit 1
    ;;
esac

case "$CONFLICT_POLICY" in
  ask|overwrite|skip) ;;
  *)
    log_error "--conflict 参数非法: ${CONFLICT_POLICY}（可选: ask|overwrite|skip）"
    exit 1
    ;;
esac

case "$SKILL_CONFLICT_POLICY" in
  overwrite|skip|rename|ask) ;;
  *)
    log_error "--skill-conflict 参数非法: ${SKILL_CONFLICT_POLICY}（可选: overwrite|skip|rename|ask）"
    exit 1
    ;;
esac

case "$INTERACTIVE_MODE" in
  auto|on|off) ;;
  *)
    log_error "--interactive 模式非法: ${INTERACTIVE_MODE}（可选: auto|on|off）"
    exit 1
    ;;
esac

case "$PERSIST_EXTRA" in
  ask|always|never) ;;
  *)
    log_error "--persist-extra 参数非法: ${PERSIST_EXTRA}（可选: ask|always|never）"
    exit 1
    ;;
esac

contains_csv_item() {
  local csv="$1"
  local item="$2"
  local token
  IFS=',' read -r -a __items <<<"$csv"
  for token in "${__items[@]-}"; do
    token="${token//[[:space:]]/}"
    [[ "$token" == "$item" ]] && return 0
  done
  return 1
}

validate_targets_csv() {
  local token
  local count=0
  IFS=',' read -r -a __targets <<<"$TARGETS_CSV"
  for token in "${__targets[@]-}"; do
    token="${token//[[:space:]]/}"
    [[ -z "$token" ]] && continue
    case "$token" in
      cursor|claude|codex)
        count=$((count + 1))
        ;;
      *)
        log_error "--targets 含非法项: ${token}（可选: cursor,claude,codex）"
        exit 1
        ;;
    esac
  done
  if [[ $count -eq 0 ]]; then
    log_error "--targets 至少指定一个客户端"
    exit 1
  fi
}

target_id_for_ide() {
  case "$1" in
    "Cursor") echo "cursor" ;;
    "Claude Code") echo "claude" ;;
    "Codex") echo "codex" ;;
    *) return 1 ;;
  esac
}

validate_targets_csv

NEED_SKILLS=1
if [[ ! -f "$SKILLS_PROFILE" ]]; then
  log_error "缺少 skills profile: $SKILLS_PROFILE"
  exit 1
fi

declare -a IDE_CONFIGS=(
  "Cursor|$HOME/.cursor/skills"
  "Claude Code|$HOME/.claude/skills"
  "Codex|$HOME/.codex/skills.union,$HOME/.codex/skills"
)

is_cmd_available() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1
}

is_ide_detected() {
  local name="$1"
  case "$name" in
    "Cursor")
      [[ -d "$HOME/.cursor" ]] && return 0
      [[ -d "/Applications/Cursor.app" || -d "$HOME/Applications/Cursor.app" ]] && return 0
      is_cmd_available "cursor" && return 0
      return 1
      ;;
    "Claude Code")
      [[ -d "$HOME/.claude" ]] && return 0
      is_cmd_available "claude" && return 0
      is_cmd_available "claude-code" && return 0
      return 1
      ;;
    "Codex")
      [[ -d "$HOME/.codex" ]] && return 0
      is_cmd_available "codex" && return 0
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

ide_detect_hint() {
  local name="$1"
  case "$name" in
    "Cursor")
      echo "~/.cursor 或 Cursor.app 或 cursor 命令"
      ;;
    "Claude Code")
      echo "~/.claude 或 claude/claude-code 命令"
      ;;
    "Codex")
      echo "~/.codex 或 codex 命令"
      ;;
    *)
      echo "本地目录或 CLI"
      ;;
  esac
}

run_cmd() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[演练] $*"
  else
    eval "$@"
  fi
}

normalize_path_with_home() {
  local p="$1"
  if [[ "$p" == "~" ]]; then
    p="$HOME"
  elif [[ "$p" == ~/* ]]; then
    p="$HOME/${p#~/}"
  elif [[ "$p" != /* ]]; then
    p="$PWD/$p"
  fi
  echo "$p"
}

is_install_interactive_enabled() {
  if [[ "$INTERACTIVE_MODE" == "on" ]]; then
    return 0
  fi
  if [[ "$INTERACTIVE_MODE" == "auto" && -t 0 ]]; then
    return 0
  fi
  return 1
}

read_profile_lines() {
  local file="$1"
  grep -v '^[[:space:]]*#' "$file" | sed '/^[[:space:]]*$/d'
}

declare -a PROFILE_SKILL_ITEMS=()
declare -a SELECTED_SKILL_ITEMS=()
declare -a DISCOVERED_EXTRA_SKILL_ITEMS=()
declare -a SELECTED_EXTRA_SKILL_ITEMS=()
declare -a PERSISTED_EXTRA_SKILL_ITEMS=()
declare -a AUTO_ADDED_DEP_SKILLS=()
declare -a PARSED_ITEMS=()

load_profile_items() {
  PROFILE_SKILL_ITEMS=()

  if [[ $NEED_SKILLS -eq 1 ]]; then
    while IFS= read -r rel; do
      PROFILE_SKILL_ITEMS+=("$rel")
    done < <(read_profile_lines "$SKILLS_PROFILE")
  fi
}

discover_profile_missing_skills() {
  DISCOVERED_EXTRA_SKILL_ITEMS=()
  if [[ $NEED_SKILLS -ne 1 ]]; then
    return 0
  fi

  local all_skills=()
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    all_skills+=("$rel")
  done < <(
    find -L "$SKILLS_DIR" -mindepth 3 -maxdepth 3 -type f -name "SKILL.md" \
      | sed "s#^$SKILLS_DIR/##; s#/SKILL.md##" \
      | sort
  )

  local profile_csv=","
  local rel
  for rel in "${PROFILE_SKILL_ITEMS[@]-}"; do
    [[ -z "$rel" ]] && continue
    profile_csv="${profile_csv}${rel},"
  done

  for rel in "${all_skills[@]-}"; do
    [[ -z "$rel" ]] && continue
    if [[ "$profile_csv" != *",$rel,"* ]]; then
      DISCOVERED_EXTRA_SKILL_ITEMS+=("$rel")
    fi
  done
}

find_skill_rel_by_name() {
  local name="$1"
  if [[ -z "$name" ]]; then
    echo ""
    return
  fi

  if [[ "$name" == */* ]]; then
    if [[ -d "$SKILLS_DIR/$name" ]]; then
      echo "$name"
      return
    fi
  fi

  local matches=()
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    matches+=("$rel")
  done < <(
    find -L "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -type d -name "$name" \
      | sed "s#^$SKILLS_DIR/##"
  )

  if [[ ${#matches[@]} -eq 0 ]]; then
    echo ""
    return
  fi

  if [[ ${#matches[@]} -gt 1 ]]; then
    log_warn "依赖名 [$name] 匹配到多个 skill，默认使用: ${matches[0]}" >&2
  fi
  echo "${matches[0]}"
}

get_skill_dep_names() {
  local rel="$1"
  local skill_file="$SKILLS_DIR/$rel/SKILL.md"
  [[ -f "$skill_file" ]] || return 0

  awk '
    BEGIN { fm=0; deps=0 }
    NR==1 && $0=="---" { fm=1; next }
    fm && $0=="---" { exit }
    !fm { exit }
    {
      if (deps==1) {
        if ($0 ~ /^[[:space:]]*-[[:space:]]+/) {
          line=$0
          sub(/^[[:space:]]*-[[:space:]]+/, "", line)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
          if (line!="") print line
          next
        }
        if ($0 ~ /^[[:alnum:]_][[:alnum:]_-]*[[:space:]]*:/) {
          deps=0
        }
      }

      if ($0 ~ /^depends_on:[[:space:]]*$/) {
        deps=1
        next
      }

      if ($0 ~ /^depends_on:[[:space:]]*\[[^]]*\][[:space:]]*$/) {
        line=$0
        sub(/^depends_on:[[:space:]]*\[/, "", line)
        sub(/\][[:space:]]*$/, "", line)
        gsub(/[[:space:]]/, "", line)
        n=split(line, arr, ",")
        for (i=1; i<=n; i++) if (arr[i]!="") print arr[i]
      }
    }
  ' "$skill_file"
}

expand_selected_skill_dependencies() {
  AUTO_ADDED_DEP_SKILLS=()
  if [[ $NEED_SKILLS -ne 1 ]]; then
    return 0
  fi

  local queue=("${SELECTED_SKILL_ITEMS[@]-}")
  local selected_csv=","
  local item
  for item in "${queue[@]-}"; do
    [[ -z "$item" ]] && continue
    if [[ "$selected_csv" != *",$item,"* ]]; then
      selected_csv="${selected_csv}${item},"
    fi
  done

  local idx=0
  while (( idx < ${#queue[@]} )); do
    local rel="${queue[$idx]}"
    idx=$((idx + 1))
    [[ -z "$rel" ]] && continue

    while IFS= read -r dep_name; do
      [[ -z "$dep_name" ]] && continue
      local dep_rel
      dep_rel="$(find_skill_rel_by_name "$dep_name")"
      if [[ -z "$dep_rel" ]]; then
        log_warn "skill [$rel] 依赖 [$dep_name] 未找到，已跳过自动补齐"
        continue
      fi
      if [[ "$selected_csv" != *",$dep_rel,"* ]]; then
        queue+=("$dep_rel")
        AUTO_ADDED_DEP_SKILLS+=("$dep_rel")
        selected_csv="${selected_csv}${dep_rel},"
      fi
    done < <(get_skill_dep_names "$rel")
  done

  SELECTED_SKILL_ITEMS=("${queue[@]-}")
}

print_indexed_items() {
  local title="$1"
  shift
  local items=("$@")
  echo "📦 $title"
  if [[ ${#items[@]} -eq 0 ]]; then
    echo "  (无可选项)"
    return
  fi
  local i=1
  for item in "${items[@]}"; do
    echo "  [$i] $item"
    local desc
    desc="$(get_skill_description "$item")"
    if [[ -n "$desc" ]]; then
      echo "      ↳ $(get_skill_intro_emoji "$item") $desc"
    fi
    i=$((i + 1))
  done
}

get_skill_intro_emoji() {
  local rel="$1"
  local group="${rel%%/*}"
  case "$group" in
    development) echo "🛠️" ;;
    review) echo "🧪" ;;
    visualization) echo "📝" ;;
    platform) echo "⚙️" ;;
    *) echo "✨" ;;
  esac
}

get_skill_items_for_ide() {
  local ide_name="$1"
  printf "%s\n" "${SELECTED_SKILL_ITEMS[@]-}"
}

get_skill_description() {
  local rel="$1"
  local skill_file="$SKILLS_DIR/$rel/SKILL.md"
  local desc=""
  local override=""

  override="$(get_skill_summary_override "$rel")"
  if [[ -n "$override" ]]; then
    echo "$override"
    return
  fi

  if [[ ! -f "$skill_file" ]]; then
    echo "未找到 SKILL.md"
    return
  fi

  desc="$(awk '
    BEGIN { in_fm=0; in_desc_block=0 }
    NR==1 && $0=="---" { in_fm=1; next }
    in_fm && $0=="---" { exit }
    !in_fm { exit }
    {
      if (in_desc_block == 0) {
        if ($0 ~ /^description:[[:space:]]*\|[[:space:]]*$/) {
          in_desc_block=1
          next
        }
        if ($0 ~ /^description:[[:space:]]*/) {
          line=$0
          sub(/^description:[[:space:]]*/, "", line)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
          gsub(/^"|"$/, "", line)
          if (line != "") {
            print line
            exit
          }
        }
      } else {
        if ($0 ~ /^[[:space:]]{2,}.+/) {
          line=$0
          sub(/^[[:space:]]+/, "", line)
          if (line != "") {
            print line
            exit
          }
        } else if ($0 ~ /^[[:space:]]*$/) {
          next
        } else {
          exit
        }
      }
    }
  ' "$skill_file")"

  if [[ -z "$desc" ]]; then
    desc="$(awk 'NR>1 && $0 !~ /^---$/ && $0 !~ /^#/ && $0 !~ /^[[:space:]]*$/ { print; exit }' "$skill_file")"
  fi

  desc="${desc//$'\r'/}"
  echo "$(summarize_description_text "$desc")"
}

get_skill_summary_override() {
  local rel="$1"
  local skill_name
  skill_name="$(basename "$rel")"
  case "$skill_name" in
    author-final-review)
      echo "只审你本人最终代码改动，输出完整 bug 清单（不看中间已修复问题）"
      ;;
    brainstorming)
      echo "开发前先做需求澄清和方案设计，确认后再进入实现"
      ;;
    *)
      echo ""
      ;;
  esac
}

summarize_description_text() {
  local text="$1"
  text="$(echo "$text" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^[[:space:]]+//; s/[[:space:]]+$//')"
  if [[ -z "$text" ]]; then
    echo ""
    return
  fi

  local summary="$text"
  local marker
  for marker in "。触发" "。功能" "。使用场景" "。当用户" "。可由" ". When " ". If " ". Supports " ". It "; do
    summary="${summary%%$marker*}"
  done

  if [[ -z "$summary" ]]; then
    summary="$text"
  fi

  summary="$(echo "$summary" | sed -E \
    -e 's/^Use when /用于：/I' \
    -e 's/^You MUST use this before /用于：/I' \
    -e 's/^When user /当用户/I' \
    -e 's/^It /该技能/I' \
    -e 's/[[:space:]]+$//')"

  if [[ ${#summary} -gt 56 ]]; then
    summary="${summary:0:56}..."
  fi
  echo "$summary"
}

parse_selection_input() {
  local raw="$1"
  shift
  local items=("$@")
  PARSED_ITEMS=()

  local normalized
  normalized="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  if [[ -z "$normalized" || "$normalized" == "all" || "$normalized" == "a" ]]; then
    PARSED_ITEMS=("${items[@]}")
    return 0
  fi
  if [[ "$normalized" == "none" || "$normalized" == "n" ]]; then
    return 0
  fi

  local selected_csv=","
  IFS=',' read -r -a tokens <<< "$normalized"
  for token in "${tokens[@]}"; do
    [[ -z "$token" ]] && continue

    if [[ "$token" =~ ^[0-9]+$ ]]; then
      local idx=$((token - 1))
      if (( idx < 0 || idx >= ${#items[@]} )); then
        return 1
      fi
      local picked="${items[$idx]}"
      if [[ "$selected_csv" != *",$picked,"* ]]; then
        PARSED_ITEMS+=("$picked")
        selected_csv="${selected_csv}${picked},"
      fi
      continue
    fi

    if [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
      local start="${BASH_REMATCH[1]}"
      local end="${BASH_REMATCH[2]}"
      if (( start > end )); then
        local tmp="$start"
        start="$end"
        end="$tmp"
      fi
      local n
      for ((n=start; n<=end; n++)); do
        local idx=$((n - 1))
        if (( idx < 0 || idx >= ${#items[@]} )); then
          return 1
        fi
        local picked="${items[$idx]}"
        if [[ "$selected_csv" != *",$picked,"* ]]; then
          PARSED_ITEMS+=("$picked")
          selected_csv="${selected_csv}${picked},"
        fi
      done
      continue
    fi

    return 1
  done
  return 0
}

prompt_pick_items() {
  local items=("$@")
  local prompt_text="请输入要安装的编号（如 1,3,5 或 2-6；all 全选；none 不选）[all]: "

  while true; do
    print_indexed_items "skills 可选项" "${items[@]}"
    echo -n "$prompt_text"
    read -r raw
    local raw_norm
    raw_norm="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
    if [[ "$raw_norm" == "none" || "$raw_norm" == "n" ]]; then
      SELECTED_SKILL_ITEMS=()
      break
    fi
    if parse_selection_input "$raw" "${items[@]}"; then
      SELECTED_SKILL_ITEMS=("${PARSED_ITEMS[@]-}")
      break
    fi
    log_warn "输入格式无效，请重新输入。"
  done
}

append_unique_skills_to_selected() {
  local selected_csv=","
  local rel
  for rel in "${SELECTED_SKILL_ITEMS[@]-}"; do
    [[ -z "$rel" ]] && continue
    selected_csv="${selected_csv}${rel},"
  done
  for rel in "$@"; do
    [[ -z "$rel" ]] && continue
    if [[ "$selected_csv" != *",$rel,"* ]]; then
      SELECTED_SKILL_ITEMS+=("$rel")
      SELECTED_EXTRA_SKILL_ITEMS+=("$rel")
      selected_csv="${selected_csv}${rel},"
    fi
  done
}

prompt_include_missing_skills() {
  local interactive_enabled="$1"
  SELECTED_EXTRA_SKILL_ITEMS=()

  if [[ ${#DISCOVERED_EXTRA_SKILL_ITEMS[@]} -eq 0 ]]; then
    return 0
  fi

  if [[ "$interactive_enabled" -ne 1 || ! -t 0 ]]; then
    log_warn "发现 ${#DISCOVERED_EXTRA_SKILL_ITEMS[@]} 个未写入 profile 的 skill；当前非交互模式未追加（可使用 --interactive 选择）"
    return 0
  fi

  echo "======================================"
  echo " 🆕 发现未收录到 profile 的 skills（${#DISCOVERED_EXTRA_SKILL_ITEMS[@]} 个）"
  echo " 可选择将它们一并同步："
  echo " [1] 不追加（默认）"
  echo " [2] 全部追加"
  echo " [3] 按编号追加"
  echo -n "请选择 [1]: "
  local mode
  read -r mode
  mode="$(echo "$mode" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"

  case "$mode" in
    ""|1|n|no|none|skip)
      ;;
    2|all|a)
      append_unique_skills_to_selected "${DISCOVERED_EXTRA_SKILL_ITEMS[@]}"
      ;;
    3|custom|c)
      while true; do
        print_indexed_items "未收录 skills 可选项" "${DISCOVERED_EXTRA_SKILL_ITEMS[@]}"
        echo -n "请输入要追加的编号（如 1,3,5 或 2-6；all 全选；none 不追加）[none]: "
        local raw
        read -r raw
        local raw_norm
        raw_norm="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
        if [[ -z "$raw_norm" || "$raw_norm" == "none" || "$raw_norm" == "n" ]]; then
          break
        fi
        if parse_selection_input "$raw" "${DISCOVERED_EXTRA_SKILL_ITEMS[@]}"; then
          append_unique_skills_to_selected "${PARSED_ITEMS[@]-}"
          break
        fi
        log_warn "输入格式无效，请重新输入。"
      done
      ;;
    *)
      log_warn "未识别的选择，默认不追加未收录 skills。"
      ;;
  esac
}

persist_selected_extra_skills_to_profile() {
  PERSISTED_EXTRA_SKILL_ITEMS=()
  if [[ ${#SELECTED_EXTRA_SKILL_ITEMS[@]} -eq 0 ]]; then
    return 0
  fi

  local existing_csv=","
  local rel
  while IFS= read -r rel; do
    [[ -z "$rel" ]] && continue
    existing_csv="${existing_csv}${rel},"
  done < <(read_profile_lines "$SKILLS_PROFILE")

  local to_persist=()
  for rel in "${SELECTED_EXTRA_SKILL_ITEMS[@]-}"; do
    [[ -z "$rel" ]] && continue
    if [[ "$existing_csv" != *",$rel,"* ]]; then
      to_persist+=("$rel")
      existing_csv="${existing_csv}${rel},"
    fi
  done

  if [[ ${#to_persist[@]} -eq 0 ]]; then
    return 0
  fi

  local do_persist=0
  case "$PERSIST_EXTRA" in
    always)
      do_persist=1
      ;;
    never)
      do_persist=0
      ;;
    ask)
      if [[ ! -t 0 ]]; then
        log_warn "非交互模式，未写回 profile（可用 --persist-extra always 自动写回）"
        do_persist=0
      else
        echo -n "💾 检测到本次追加 ${#to_persist[@]} 个未收录 skill，是否写回 profile（${SKILLS_PROFILE}）？ [Y/n]: "
        local ans
        read -r ans
        ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
        case "$ans" in
          ""|y|yes)
            do_persist=1
            ;;
          *)
            do_persist=0
            ;;
        esac
      fi
      ;;
  esac

  if [[ $do_persist -eq 0 ]]; then
    return 0
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log_info "🧪 演练：将写回 profile ${#to_persist[@]} 个 skill -> $(printf '%s ' "${to_persist[@]}")"
    PERSISTED_EXTRA_SKILL_ITEMS=("${to_persist[@]-}")
    return 0
  fi

  for rel in "${to_persist[@]-}"; do
    echo "$rel" >> "$SKILLS_PROFILE"
    PROFILE_SKILL_ITEMS+=("$rel")
  done
  PERSISTED_EXTRA_SKILL_ITEMS=("${to_persist[@]-}")
  log_info "已写回 profile ${#to_persist[@]} 个 skill。"
}

run_install_selector() {
  SELECTED_SKILL_ITEMS=("${PROFILE_SKILL_ITEMS[@]-}")
  SELECTED_EXTRA_SKILL_ITEMS=()

  local interactive_enabled=0
  if is_install_interactive_enabled; then
    interactive_enabled=1
  fi

  if [[ $interactive_enabled -eq 0 ]]; then
    prompt_include_missing_skills 0
    return
  fi
  if [[ ! -t 0 ]]; then
    log_warn "当前非交互终端，无法选择安装项，已按 profile 全量处理。"
    prompt_include_missing_skills 0
    return
  fi

  echo "======================================"
  echo " 🧭 安装项选择"
  echo " [1] 全部安装（使用 profile 全量）"
  echo " [2] 自定义安装（按编号多选）"
  echo -n "请选择 [1]: "
  local mode
  read -r mode
  mode="$(echo "$mode" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"

  case "$mode" in
    ""|1|all|a)
      ;;
    2|custom|c)
      if [[ $NEED_SKILLS -eq 1 ]]; then
        prompt_pick_items "${PROFILE_SKILL_ITEMS[@]}"
      fi
      ;;
    *)
      log_warn "未识别的选择，已按全量安装处理。"
      ;;
  esac

  prompt_include_missing_skills "$interactive_enabled"

  if [[ $UNINSTALL -eq 0 && ${#SELECTED_SKILL_ITEMS[@]} -eq 0 ]]; then
    log_error "未选择任何安装项，已终止。"
    exit 1
  fi
}

should_overwrite_target() {
  local dst="$1"
  local kind="$2"

  if [[ $FORCE -eq 1 || "$CONFLICT_POLICY" == "overwrite" ]]; then
    return 0
  fi
  if [[ "$CONFLICT_POLICY" == "skip" ]]; then
    return 1
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log_warn "🧪 冲突(演练模式): ${dst}（类型: ${kind}），保持现状（可用 --conflict overwrite 覆盖）"
    return 1
  fi

  if [[ ! -t 0 ]]; then
    log_warn "🤖 冲突(非交互): ${dst}（类型: ${kind}），保持现状（可用 --conflict overwrite 或 --force）"
    return 1
  fi

  while true; do
    echo -n "⚔️  [冲突] ${dst}（类型: ${kind}）已存在。请选择: [o]覆盖/[s]跳过/[oa]全部覆盖/[sa]全部跳过: "
    read -r ans
    ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]')"
    case "$ans" in
      o|overwrite)
        return 0
        ;;
      s|skip)
        return 1
        ;;
      oa|overwrite-all)
        CONFLICT_POLICY="overwrite"
        return 0
        ;;
      sa|skip-all)
        CONFLICT_POLICY="skip"
        return 1
        ;;
      *)
        echo "👉 请输入: o/s/oa/sa"
        ;;
    esac
  done
}

remove_existing_target() {
  local dst="$1"
  if [[ -L "$dst" || -f "$dst" ]]; then
    run_cmd "rm -f \"$dst\""
  elif [[ -d "$dst" ]]; then
    run_cmd "rm -rf \"$dst\""
  else
    run_cmd "rm -rf \"$dst\""
  fi
}

safe_link_file() {
  local src="$1"
  local dst="$2"

  if [[ ! -f "$src" ]]; then
    log_warn "源文件不存在，已跳过: $src"
    return 0
  fi

  if [[ -L "$dst" ]]; then
    local curr
    curr="$(readlink "$dst" || true)"
    if [[ "$curr" == "$src" ]]; then
      return
    fi
    if should_overwrite_target "$dst" "symlink"; then
      remove_existing_target "$dst"
    else
      return 0
    fi
  elif [[ -e "$dst" ]]; then
    local kind="file"
    [[ -d "$dst" ]] && kind="directory"
    if should_overwrite_target "$dst" "$kind"; then
      remove_existing_target "$dst"
    else
      return 0
    fi
  fi

  run_cmd "ln -s \"$src\" \"$dst\""
}

safe_link_dir() {
  local src="$1"
  local dst="$2"
  local ide_name="${3:-}"

  if [[ ! -d "$src" || ! -f "$src/SKILL.md" ]]; then
    log_warn "无效的 skill 目录（缺少 SKILL.md），已跳过: $src"
    return 0
  fi

  if [[ -L "$dst" ]]; then
    local curr
    curr="$(readlink "$dst" || true)"
    if [[ "$curr" == "$src" ]]; then
      return
    fi
    if should_overwrite_target "$dst" "symlink"; then
      remove_existing_target "$dst"
    else
      return 0
    fi
  elif [[ -e "$dst" ]]; then
    local kind="file"
    [[ -d "$dst" ]] && kind="directory"
    if should_overwrite_target "$dst" "$kind"; then
      remove_existing_target "$dst"
    else
      return 0
    fi
  fi

  run_cmd "ln -s \"$src\" \"$dst\""
}

choose_skill_conflict_action() {
  local dst="$1"

  if [[ $FORCE -eq 1 ]]; then
    echo "overwrite"
    return
  fi

  case "$SKILL_CONFLICT_POLICY" in
    overwrite|skip|rename)
      echo "$SKILL_CONFLICT_POLICY"
      return
      ;;
  esac

  # ask 模式
  if [[ $DRY_RUN -eq 1 || ! -t 0 ]]; then
    log_warn "🤖 skill 冲突(非交互/演练): ${dst}，默认覆盖（可用 --skill-conflict skip|rename）"
    echo "overwrite"
    return
  fi

  while true; do
    echo -n "⚔️  [skill冲突] $dst 已存在。请选择: [o]覆盖/[s]跳过/[r]重命名/[oa]全覆盖/[sa]全跳过/[ra]全重命名: "
    read -r ans
    ans="$(echo "$ans" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
    case "$ans" in
      o|overwrite)
        echo "overwrite"
        return
        ;;
      s|skip)
        echo "skip"
        return
        ;;
      r|rename)
        echo "rename"
        return
        ;;
      oa|overwrite-all)
        SKILL_CONFLICT_POLICY="overwrite"
        echo "overwrite"
        return
        ;;
      sa|skip-all)
        SKILL_CONFLICT_POLICY="skip"
        echo "skip"
        return
        ;;
      ra|rename-all)
        SKILL_CONFLICT_POLICY="rename"
        echo "rename"
        return
        ;;
      *)
        echo "👉 请输入: o/s/r/oa/sa/ra"
        ;;
    esac
  done
}

resolve_renamed_skill_dst() {
  local src="$1"
  local target_dir="$2"
  local skill_name="$3"
  local base="${target_dir}/${skill_name}__${SKILL_SUFFIX}"

  if [[ ! -e "$base" && ! -L "$base" ]]; then
    echo "$base"
    return
  fi
  if [[ -L "$base" ]]; then
    local curr
    curr="$(readlink "$base" || true)"
    if [[ "$curr" == "$src" ]]; then
      echo "$base"
      return
    fi
  fi

  local n=2
  while true; do
    local candidate="${base}-${n}"
    if [[ ! -e "$candidate" && ! -L "$candidate" ]]; then
      echo "$candidate"
      return
    fi
    if [[ -L "$candidate" ]]; then
      local curr2
      curr2="$(readlink "$candidate" || true)"
      if [[ "$curr2" == "$src" ]]; then
        echo "$candidate"
        return
      fi
    fi
    n=$((n + 1))
  done
}

resolve_skill_install_dst() {
  local src="$1"
  local target_dir="$2"
  local skill_name="$3"
  local primary="$target_dir/$skill_name"

  if [[ ! -e "$primary" && ! -L "$primary" ]]; then
    echo "$primary"
    return
  fi

  if [[ -L "$primary" ]]; then
    local curr
    curr="$(readlink "$primary" || true)"
    if [[ "$curr" == "$src" ]]; then
      echo "$primary"
      return
    fi
  fi

  local action
  action="$(choose_skill_conflict_action "$primary")"
  case "$action" in
    overwrite)
      echo "$primary"
      ;;
    skip)
      echo "__SKIP__"
      ;;
    rename)
      echo "$(resolve_renamed_skill_dst "$src" "$target_dir" "$skill_name")"
      ;;
    *)
      echo "$primary"
      ;;
  esac
}

remove_if_owned_symlink() {
  local src="$1"
  local dst="$2"
  if [[ -L "$dst" ]]; then
    local curr
    curr="$(readlink "$dst" || true)"
    if [[ "$curr" == "$src" ]]; then
      run_cmd "rm \"$dst\""
    fi
  fi
}

remove_owned_skill_aliases() {
  local src="$1"
  local target_dir="$2"
  local skill_name="$3"
  local pattern="${skill_name}__${SKILL_SUFFIX}*"
  local p
  while IFS= read -r p; do
    [[ -z "$p" ]] && continue
    remove_if_owned_symlink "$src" "$p"
  done < <(find "$target_dir" -maxdepth 1 -type l -name "$pattern" 2>/dev/null)
}

remove_target() {
  local p="$1"
  if [[ -L "$p" ]]; then
    run_cmd "rm \"$p\""
  elif [[ $FORCE -eq 1 && -e "$p" ]]; then
    run_cmd "rm -rf \"$p\""
  fi
}

log_skill_install_result() {
  local ide_name="$1"
  local rel="$2"
  local status="$3"
  local skill_name
  skill_name="$(basename "$rel")"
  local summary
  summary="$(get_skill_description "$rel")"
  [[ -z "$summary" ]] && summary="无说明"
  local emoji
  emoji="$(get_skill_intro_emoji "$rel")"

  if [[ "$status" == "planned" ]]; then
    log_info "[$ide_name] ${skill_name} 技能（负责：${emoji} ${summary}）将安装"
    return
  fi

  if [[ "$status" == "ok" ]]; then
    log_info "[$ide_name] ${skill_name} 技能（负责：${emoji} ${summary}）安装成功"
    return
  fi

  log_warn "[$ide_name] ${skill_name} 技能安装未生效（可能被冲突策略跳过）"
}

install_for_ide() {
  local name="$1"
  local skills_targets_csv="$2"

  IFS=',' read -r -a skills_targets <<< "$skills_targets_csv"
  for st in "${skills_targets[@]}"; do
    mkdir -p "$st"
  done
  log_info "🛠️  正在为 $name 安装"

  if [[ $NEED_SKILLS -eq 1 ]]; then
    local ide_skill_items=()
    while IFS= read -r rel; do
      [[ -z "$rel" ]] && continue
      ide_skill_items+=("$rel")
    done < <(get_skill_items_for_ide "$name")

    for rel in "${ide_skill_items[@]-}"; do
      [[ -z "$rel" ]] && continue
      local src="$SKILLS_DIR/$rel"
      local skill_name
      skill_name="$(basename "$rel")"
      local installed=0
      if [[ $DRY_RUN -eq 1 ]]; then
        log_skill_install_result "$name" "$rel" "planned"
      fi
      for st in "${skills_targets[@]}"; do
        local dst
        dst="$(resolve_skill_install_dst "$src" "$st" "$skill_name")"
        if [[ "$dst" == "__SKIP__" ]]; then
          log_warn "[${name}] ${skill_name} 技能重名，按策略跳过（目标: ${st}/${skill_name}）"
          continue
        fi
        if [[ "$dst" != "$st/$skill_name" ]]; then
          log_warn "[$name] ${skill_name} 技能重名，已重命名安装到: $dst"
        fi
        safe_link_dir "$src" "$dst" "$name"
        if [[ $DRY_RUN -eq 0 && -L "$dst" ]]; then
          local curr
          curr="$(readlink "$dst" || true)"
          if [[ "$curr" == "$src" ]]; then
            installed=1
          fi
        fi
      done
      if [[ $DRY_RUN -eq 0 ]]; then
        if [[ $installed -eq 1 ]]; then
          log_skill_install_result "$name" "$rel" "ok"
        else
          log_skill_install_result "$name" "$rel" "skip"
        fi
      fi
    done
  fi
}

uninstall_for_ide() {
  local name="$1"
  local skills_targets_csv="$2"
  IFS=',' read -r -a skills_targets <<< "$skills_targets_csv"

  log_info "🧹 正在为 $name 卸载"

  if [[ $NEED_SKILLS -eq 1 ]]; then
    local ide_skill_items=()
    while IFS= read -r rel; do
      [[ -z "$rel" ]] && continue
      ide_skill_items+=("$rel")
    done < <(get_skill_items_for_ide "$name")

    for rel in "${ide_skill_items[@]-}"; do
      [[ -z "$rel" ]] && continue
      local src="$SKILLS_DIR/$rel"
      local skill_name
      skill_name="$(basename "$rel")"
      for st in "${skills_targets[@]}"; do
        remove_if_owned_symlink "$src" "$st/$skill_name"
        remove_owned_skill_aliases "$src" "$st" "$skill_name"
      done
    done
  fi
}

load_profile_items
discover_profile_missing_skills
run_install_selector
persist_selected_extra_skills_to_profile
expand_selected_skill_dependencies

echo "======================================"
echo " 🚀 团队安装器"
echo " profile: $PROFILE"
echo " 范围: $ONLY"
echo " 客户端: $TARGETS_CSV"
[[ $FORCE -eq 1 ]] && echo " 强制覆盖: 是"
echo " 冲突策略: $CONFLICT_POLICY"
echo " skills 重名策略: ${SKILL_CONFLICT_POLICY}（默认 overwrite，可选 skip/rename/ask）"
echo " 交互模式: $INTERACTIVE_MODE"
if [[ $NEED_SKILLS -eq 1 ]]; then
  _dep_count=${#AUTO_ADDED_DEP_SKILLS[@]}
  _summary="已选 ${#SELECTED_SKILL_ITEMS[@]}（profile ${#PROFILE_SKILL_ITEMS[@]} + 追加 ${#SELECTED_EXTRA_SKILL_ITEMS[@]}"
  if [[ $_dep_count -gt 0 ]]; then
    _summary="${_summary} + ${YELLOW}依赖 ${_dep_count}${NC}"
  else
    _summary="${_summary} + 依赖 0"
  fi
  _summary="${_summary}）"
  echo " skills: ${_summary}"
  if [[ ${#SELECTED_SKILL_ITEMS[@]} -gt 0 ]]; then
    echo "   -> $(printf '%s ' "${SELECTED_SKILL_ITEMS[@]}")"
  fi
  if [[ ${#SELECTED_EXTRA_SKILL_ITEMS[@]} -gt 0 ]]; then
    echo " 手动追加未收录 skills: $(printf '%s ' "${SELECTED_EXTRA_SKILL_ITEMS[@]}")"
  fi
  if [[ ${#PERSISTED_EXTRA_SKILL_ITEMS[@]} -gt 0 ]]; then
    echo " 已写回 profile: $(printf '%s ' "${PERSISTED_EXTRA_SKILL_ITEMS[@]}")"
  fi
  if [[ $_dep_count -gt 0 ]]; then
    echo -e "${YELLOW} 🔗 自动补齐依赖 ${_dep_count} 个:${NC} ${YELLOW}$(printf '%s ' "${AUTO_ADDED_DEP_SKILLS[@]}")${NC}"
  fi
fi
[[ $DRY_RUN -eq 1 ]] && echo " 模式: 演练(dry-run)"
[[ $UNINSTALL -eq 1 ]] && echo " 模式: 卸载"
echo "======================================"

for config in "${IDE_CONFIGS[@]}"; do
  IFS='|' read -r name skills_targets_csv <<< "$config"
  target_id="$(target_id_for_ide "$name")"
  if ! contains_csv_item "$TARGETS_CSV" "$target_id"; then
    log_info "跳过 ${name}（不在 --targets 范围内）"
    continue
  fi
  if ! is_ide_detected "$name"; then
    log_warn "跳过 ${name}（未检测到客户端/CLI：$(ide_detect_hint "$name")）"
    continue
  fi
  skills_any_parent=0
  IFS=',' read -r -a skill_targets_for_check <<< "$skills_targets_csv"
  for st in "${skill_targets_for_check[@]}"; do
    parent_skill="$(dirname "$st")"
    if [[ -d "$parent_skill" ]]; then
      skills_any_parent=1
      break
    fi
  done
  if [[ $skills_any_parent -eq 0 ]]; then
    log_warn "跳过 ${name}（目标父目录不存在）"
    continue
  fi

  if [[ $UNINSTALL -eq 1 ]]; then
    uninstall_for_ide "$name" "$skills_targets_csv"
  else
    install_for_ide "$name" "$skills_targets_csv"
  fi
done

log_info "🎉 完成。"
