#!/bin/bash
# Remove synced skills from IDE link targets and/or repository source.

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
PROFILES_DIR="$ROOT_DIR/config/profiles"

SPECS_CSV=""
GROUP_FILTER=""
TARGETS_CSV="cursor,claude,codex"

REMOVE_LINKS=1
REMOVE_REPO=1
UPDATE_PROFILES=1
INTERACTIVE_MODE="auto" # auto|on|off
FORCE=0
DRY_RUN=0

ALL_RELS=()
ALL_NAMES=()
ALL_DESCS=()
SELECTED_RELS=()

REMOVED_LINKS=0
REMOVED_REPO_DIRS=0
UPDATED_PROFILES=0
SKIPPED_ITEMS=0

usage() {
  cat <<EOF
用法:
  bash scripts/remove_skills.sh [选项]

说明:
  删除误同步的 skills。默认同时执行：
  1) 删除 AI IDE 目录中的技能软链接
  2) 删除仓库 skills 源目录
  3) 清理 config/profiles/*.skills 中的引用

选项:
  --skills <a,b,c>        指定 skill 列表（支持 name 或 group/name）
  --group <name>          按分类过滤（如 development/review/visualization/platform）
  --targets <list>        软链接删除目标：cursor,claude,codex（逗号分隔，默认全选）
  --unlink-only           仅删除 IDE 软链接，不删仓库
  --repo-only             仅删除仓库技能，不删 IDE 软链接
  --no-profile-update     删除仓库后，不更新 profile 引用
  --force                 强制删除（当目标不是软链接时也删除）
  --interactive           强制交互
  --no-interactive        禁用交互
  --dry-run               仅演练，不落地
  -h, --help              显示帮助

示例:
  bash scripts/remove_skills.sh --group review --interactive
  bash scripts/remove_skills.sh --skills code-review,full-review --unlink-only
  bash scripts/remove_skills.sh --skills visualization/diagram-creation --repo-only
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skills)
      SPECS_CSV="${2:-}"
      shift 2
      ;;
    --group)
      GROUP_FILTER="${2:-}"
      shift 2
      ;;
    --targets)
      TARGETS_CSV="${2:-}"
      shift 2
      ;;
    --unlink-only)
      REMOVE_LINKS=1
      REMOVE_REPO=0
      shift
      ;;
    --repo-only)
      REMOVE_LINKS=0
      REMOVE_REPO=1
      shift
      ;;
    --no-profile-update)
      UPDATE_PROFILES=0
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --interactive)
      INTERACTIVE_MODE="on"
      shift
      ;;
    --no-interactive)
      INTERACTIVE_MODE="off"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ ! -d "$SKILLS_DIR" ]]; then
  log_error "未找到 skills 目录: $SKILLS_DIR"
  exit 1
fi

is_interactive() {
  case "$INTERACTIVE_MODE" in
    on) return 0 ;;
    off) return 1 ;;
    auto)
      [[ -t 0 && -t 1 ]] && return 0
      return 1
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

contains_csv_item() {
  local csv="$1"
  local item="$2"
  local token
  IFS=',' read -r -a __arr <<<"$csv"
  for token in "${__arr[@]-}"; do
    token="${token//[[:space:]]/}"
    [[ -z "$token" ]] && continue
    if [[ "$token" == "$item" ]]; then
      return 0
    fi
  done
  return 1
}

summarize_description_text() {
  local text="$1"
  text="$(echo "$text" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^[[:space:]]+//; s/[[:space:]]+$//')"
  [[ -z "$text" ]] && { echo ""; return; }
  local summary="$text"
  local marker
  for marker in "。触发" "。功能" "。使用场景" "。当用户" "。可由" ". When " ". If " ". Supports " ". It "; do
    summary="${summary%%$marker*}"
  done
  [[ -z "$summary" ]] && summary="$text"
  if [[ ${#summary} -gt 54 ]]; then
    summary="${summary:0:54}..."
  fi
  echo "$summary"
}

get_skill_description() {
  local rel="$1"
  local skill_file="$SKILLS_DIR/${rel}/SKILL.md"
  local desc=""
  [[ -f "$skill_file" ]] || { echo "未找到 SKILL.md"; return; }

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
          if (line != "") { print line; exit }
        }
      } else {
        if ($0 ~ /^[[:space:]]{2,}.+/) {
          line=$0
          sub(/^[[:space:]]+/, "", line)
          if (line != "") { print line; exit }
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

discover_all_skills() {
  ALL_RELS=()
  ALL_NAMES=()
  ALL_DESCS=()

  local skill_file rel name group desc
  while IFS= read -r skill_file; do
    rel="${skill_file#$SKILLS_DIR/}"
    rel="${rel%/SKILL.md}"
    [[ -z "$rel" ]] && continue
    group="${rel%%/*}"
    name="${rel##*/}"
    [[ -z "$group" || -z "$name" || "$group" == "$name" ]] && continue
    if [[ -n "$GROUP_FILTER" && "$group" != "$GROUP_FILTER" ]]; then
      continue
    fi
    desc="$(get_skill_description "$rel")"
    ALL_RELS+=("$rel")
    ALL_NAMES+=("$name")
    ALL_DESCS+=("$desc")
  done < <(find "$SKILLS_DIR" -mindepth 3 -maxdepth 3 -type f -name "SKILL.md" | sort)
}

resolve_spec_to_rel() {
  local spec="$1"
  spec="${spec//[[:space:]]/}"
  [[ -z "$spec" ]] && return 0

  if [[ "$spec" == */* ]]; then
    if [[ -f "$SKILLS_DIR/$spec/SKILL.md" ]]; then
      echo "$spec"
    else
      log_warn "未找到 skill: $spec"
      SKIPPED_ITEMS=$((SKIPPED_ITEMS + 1))
    fi
    return 0
  fi

  local matches=()
  local i
  for i in "${!ALL_NAMES[@]}"; do
    if [[ "${ALL_NAMES[$i]}" == "$spec" ]]; then
      matches+=("${ALL_RELS[$i]}")
    fi
  done

  if [[ ${#matches[@]} -eq 0 ]]; then
    log_warn "未找到 skill 名称: $spec"
    SKIPPED_ITEMS=$((SKIPPED_ITEMS + 1))
    return 0
  fi
  if [[ ${#matches[@]} -gt 1 ]]; then
    log_warn "skill 名称不唯一: $spec，请使用 group/name（命中: ${matches[*]}）"
    SKIPPED_ITEMS=$((SKIPPED_ITEMS + 1))
    return 0
  fi
  echo "${matches[0]}"
}

select_skills() {
  SELECTED_RELS=()

  if [[ -n "$SPECS_CSV" ]]; then
    local spec rel
    IFS=',' read -r -a __specs <<<"$SPECS_CSV"
    for spec in "${__specs[@]-}"; do
      rel="$(resolve_spec_to_rel "$spec" || true)"
      [[ -n "$rel" ]] && SELECTED_RELS+=("$rel")
    done
    return 0
  fi

  # 非交互下：group 模式默认全选该组
  if ! is_interactive; then
    if [[ -n "$GROUP_FILTER" ]]; then
      SELECTED_RELS=("${ALL_RELS[@]}")
      return 0
    fi
    log_error "未指定 --skills，且当前非交互模式。请加 --skills 或 --group。"
    exit 1
  fi

  echo "======================================"
  echo " 🧹 Skills 删除器"
  echo " [1] 按编号选择要删除的 skill"
  if [[ -n "$GROUP_FILTER" ]]; then
    echo " [2] 删除当前分类全部（$GROUP_FILTER）"
  else
    echo " [2] 删除全部已发现 skill（不推荐）"
  fi
  echo -n "请选择 [1]: "
  local mode
  read -r mode
  mode="${mode:-1}"

  if [[ "$mode" == "2" ]]; then
    SELECTED_RELS=("${ALL_RELS[@]}")
    return 0
  fi

  echo "======================================"
  echo " 📦 可删除 skill 列表（${#ALL_RELS[@]}）"
  local i
  for i in "${!ALL_RELS[@]}"; do
    printf " [%d] %s\n" "$((i + 1))" "${ALL_RELS[$i]}"
    if [[ -n "${ALL_DESCS[$i]}" ]]; then
      echo "     ↳ ${ALL_DESCS[$i]}"
    fi
  done
  echo -n "请输入要删除的编号（如 1,3,5 或 2-6；all 全选）[none]: "
  local picks
  read -r picks
  picks="${picks:-none}"

  if [[ "$picks" == "none" || -z "$picks" ]]; then
    SELECTED_RELS=()
    return 0
  fi
  if [[ "$picks" == "all" ]]; then
    SELECTED_RELS=("${ALL_RELS[@]}")
    return 0
  fi

  local token start end j idx
  IFS=',' read -r -a __parts <<<"$picks"
  for token in "${__parts[@]-}"; do
    token="${token//[[:space:]]/}"
    [[ -z "$token" ]] && continue
    if [[ "$token" == *-* ]]; then
      start="${token%-*}"
      end="${token#*-}"
      if [[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ && "$start" -le "$end" ]]; then
        for ((j=start; j<=end; j++)); do
          idx=$((j - 1))
          if [[ $idx -ge 0 && $idx -lt ${#ALL_RELS[@]} ]]; then
            SELECTED_RELS+=("${ALL_RELS[$idx]}")
          fi
        done
      else
        log_warn "忽略非法区间: $token"
      fi
    elif [[ "$token" =~ ^[0-9]+$ ]]; then
      idx=$((token - 1))
      if [[ $idx -ge 0 && $idx -lt ${#ALL_RELS[@]} ]]; then
        SELECTED_RELS+=("${ALL_RELS[$idx]}")
      else
        log_warn "忽略越界编号: $token"
      fi
    else
      log_warn "忽略非法输入: $token"
    fi
  done
}

dedupe_selected() {
  local seen="|"
  local dedup=()
  local rel
  for rel in "${SELECTED_RELS[@]-}"; do
    [[ -z "$rel" ]] && continue
    if [[ "$seen" == *"|$rel|"* ]]; then
      continue
    fi
    seen="${seen}${rel}|"
    dedup+=("$rel")
  done
  SELECTED_RELS=("${dedup[@]-}")
}

remove_target_item() {
  local label="$1"
  local dest="$2"
  local src="$3"

  if [[ ! -e "$dest" && ! -L "$dest" ]]; then
    return 0
  fi

  if [[ -L "$dest" ]]; then
    local dest_real src_real
    dest_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$dest" 2>/dev/null || true)"
    src_real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$src" 2>/dev/null || true)"
    if [[ -n "$dest_real" && -n "$src_real" && "$dest_real" == "$src_real" ]]; then
      run_cmd "rm -f \"$dest\""
      log_info "[$label] 已删除软链接: $dest"
      REMOVED_LINKS=$((REMOVED_LINKS + 1))
      return 0
    fi
    if [[ $FORCE -eq 1 ]]; then
      run_cmd "rm -rf \"$dest\""
      log_warn "[$label] 强制删除非本仓库软链接: $dest"
      REMOVED_LINKS=$((REMOVED_LINKS + 1))
    else
      log_warn "[$label] 软链接不指向仓库 skill，已跳过: $dest"
      SKIPPED_ITEMS=$((SKIPPED_ITEMS + 1))
    fi
    return 0
  fi

  if [[ $FORCE -eq 1 ]]; then
    run_cmd "rm -rf \"$dest\""
    log_warn "[$label] 强制删除非软链接目录/文件: $dest"
    REMOVED_LINKS=$((REMOVED_LINKS + 1))
  else
    log_warn "[$label] 目标不是软链接，已跳过: $dest（可用 --force）"
    SKIPPED_ITEMS=$((SKIPPED_ITEMS + 1))
  fi
}

remove_ide_links_for_skill() {
  local rel="$1"
  local name="${rel##*/}"
  local src="$SKILLS_DIR/${rel}"
  local cursor_dir="$HOME/.cursor/skills"
  local claude_dir="$HOME/.claude/skills"
  local codex_union_dir="$HOME/.codex/skills.union"
  local codex_dir="$HOME/.codex/skills"

  if contains_csv_item "$TARGETS_CSV" "cursor"; then
    remove_target_item "Cursor" "$cursor_dir/$name" "$src"
  fi
  if contains_csv_item "$TARGETS_CSV" "claude"; then
    remove_target_item "Claude Code" "$claude_dir/$name" "$src"
  fi
  if contains_csv_item "$TARGETS_CSV" "codex"; then
    remove_target_item "Codex" "$codex_union_dir/$name" "$src"
    remove_target_item "Codex" "$codex_dir/$name" "$src"
  fi
}

remove_repo_skill() {
  local rel="$1"
  local src="$SKILLS_DIR/${rel}"
  if [[ ! -d "$src" ]]; then
    log_warn "仓库目录不存在，跳过: $src"
    SKIPPED_ITEMS=$((SKIPPED_ITEMS + 1))
    return 0
  fi
  run_cmd "rm -rf \"$src\""
  log_info "已删除仓库 skill: ${rel}"
  REMOVED_REPO_DIRS=$((REMOVED_REPO_DIRS + 1))
}

remove_from_profiles() {
  local rel="$1"
  [[ -d "$PROFILES_DIR" ]] || return 0
  local profile tmp changed
  for profile in "$PROFILES_DIR"/*.skills; do
    [[ -f "$profile" ]] || continue
    tmp="$(mktemp "${TMPDIR:-/tmp}/profile-skill.XXXXXX")"
    changed=0
    awk -v target="${rel}" '
      {
        raw=$0
        line=$0
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
        if (line==target) { next }
        print raw
      }
    ' "$profile" > "$tmp"
    if ! cmp -s "$profile" "$tmp"; then
      run_cmd "mv \"$tmp\" \"$profile\""
      log_info "已更新 profile: $(basename "$profile")（移除 ${rel}）"
      UPDATED_PROFILES=$((UPDATED_PROFILES + 1))
    else
      rm -f "$tmp"
    fi
  done
}

validate_targets_csv() {
  local token
  IFS=',' read -r -a __targets <<<"$TARGETS_CSV"
  for token in "${__targets[@]-}"; do
    token="${token//[[:space:]]/}"
    [[ -z "$token" ]] && continue
    case "$token" in
      cursor|claude|codex) ;;
      *)
        log_error "--targets 含非法项: $token（可选: cursor,claude,codex）"
        exit 1
        ;;
    esac
  done
}

validate_targets_csv
discover_all_skills

if [[ ${#ALL_RELS[@]} -eq 0 ]]; then
  log_error "未发现可删除 skill（group=${GROUP_FILTER:-all}）"
  exit 1
fi

select_skills
dedupe_selected

if [[ ${#SELECTED_RELS[@]} -eq 0 ]]; then
  log_warn "未选择任何 skill，退出。"
  exit 0
fi

echo "======================================"
echo " 🧾 删除计划"
echo " skills(${#SELECTED_RELS[@]}): ${SELECTED_RELS[*]}"
if [[ $REMOVE_LINKS -eq 1 ]]; then
  echo "  - 删除软链接目标: $TARGETS_CSV"
else
  echo "  - 删除软链接目标: 跳过"
fi
if [[ $REMOVE_REPO -eq 1 ]]; then
  echo "  - 删除仓库目录: 启用"
  if [[ $UPDATE_PROFILES -eq 1 ]]; then
    echo "  - 更新 profile 引用: 启用"
  else
    echo "  - 更新 profile 引用: 跳过"
  fi
else
  echo "  - 删除仓库目录: 跳过"
fi
echo "  - 冲突强删: $([[ $FORCE -eq 1 ]] && echo yes || echo no)"
echo "  - 演练模式: $([[ $DRY_RUN -eq 1 ]] && echo yes || echo no)"

if is_interactive; then
  echo -n "确认执行删除？[y/N]: "
  confirm=""
  read -r confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    log_warn "用户取消，未执行删除。"
    exit 0
  fi
fi

for rel in "${SELECTED_RELS[@]}"; do
  if [[ $REMOVE_LINKS -eq 1 ]]; then
    remove_ide_links_for_skill "$rel"
  fi
  if [[ $REMOVE_REPO -eq 1 ]]; then
    remove_repo_skill "$rel"
    if [[ $UPDATE_PROFILES -eq 1 ]]; then
      remove_from_profiles "$rel"
    fi
  fi
done

echo "======================================"
log_info "🎉 删除完成"
log_info "软链接删除数量: $REMOVED_LINKS"
log_info "仓库 skill 删除数量: $REMOVED_REPO_DIRS"
log_info "profile 更新次数: $UPDATED_PROFILES"
if [[ $SKIPPED_ITEMS -gt 0 ]]; then
  log_warn "跳过项数量: $SKIPPED_ITEMS"
fi
