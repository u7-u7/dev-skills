#!/bin/bash

# Git Worktree Management Script
# Manages Git worktrees with intelligent defaults, IDE integration, and content migration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get main repository path
get_main_repo_path() {
  local git_common_dir=$(git rev-parse --git-common-dir 2>/dev/null)
  local current_toplevel=$(git rev-parse --show-toplevel 2>/dev/null)

  if [[ "$git_common_dir" != "$current_toplevel/.git" ]]; then
    # In worktree, derive main repo from git-common-dir
    dirname "$git_common_dir"
  else
    # In main repo
    echo "$current_toplevel"
  fi
}

# Copy environment files from .gitignore
copy_environment_files() {
    local main_repo="$1"
    local target_worktree="$2"
    local gitignore_file="$main_repo/.gitignore"
    
    if [[ ! -f "$gitignore_file" ]]; then
        return 0
    fi
    
    local copied_count=0
    
    # Detect .env file
    if [[ -f "$main_repo/.env" ]] && grep -q "^\.env$" "$gitignore_file" 2>/dev/null; then
        cp "$main_repo/.env" "$target_worktree/.env"
        echo -e "${GREEN}✅ 已复制 .env${NC}"
        ((copied_count++))
    fi
    
    # Detect .env.* pattern files (exclude .env.example)
    for env_file in "$main_repo"/.env.*; do
        if [[ -f "$env_file" ]] && [[ "$(basename "$env_file")" != ".env.example" ]]; then
            local filename=$(basename "$env_file")
            if grep -q "^\.env\.\*$" "$gitignore_file" 2>/dev/null; then
                cp "$env_file" "$target_worktree/$filename"
                echo -e "${GREEN}✅ 已复制 $filename${NC}"
                ((copied_count++))
            fi
        fi
    done
    
    if [[ $copied_count -gt 0 ]]; then
        echo -e "${BLUE}📋 已从 .gitignore 复制 $copied_count 个环境文件${NC}"
    fi
}

# Detect and open IDE
open_in_ide() {
    local path="$1"
    
    # Detect IDE
    if command -v code &> /dev/null; then
        echo -e "${BLUE}🚀 正在用 VS Code 打开 $path...${NC}"
        code "$path"
    elif command -v cursor &> /dev/null; then
        echo -e "${BLUE}🚀 正在用 Cursor 打开 $path...${NC}"
        cursor "$path"
    elif command -v webstorm &> /dev/null; then
        echo -e "${BLUE}🚀 正在用 WebStorm 打开 $path...${NC}"
        webstorm "$path"
    elif command -v subl &> /dev/null; then
        echo -e "${BLUE}🚀 正在用 Sublime Text 打开 $path...${NC}"
        subl "$path"
    elif command -v vim &> /dev/null; then
        echo -e "${BLUE}🚀 正在用 Vim 打开 $path...${NC}"
        vim "$path"
    else
        echo -e "${YELLOW}⚠️  未检测到支持的 IDE${NC}"
    fi
}

# Add worktree
add_worktree() {
    local path="$1"
    local branch="$2"
    local open_ide="$3"
    
    # Validate Git repository
    if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        echo -e "${RED}❌ 错误: 不在 Git 仓库中${NC}"
        exit 1
    fi
    
    MAIN_REPO_PATH=$(get_main_repo_path)
    PROJECT_NAME=$(basename "$MAIN_REPO_PATH")
    WORKTREE_BASE="$MAIN_REPO_PATH/../.wt/$PROJECT_NAME"
    ABSOLUTE_WORKTREE_PATH="$WORKTREE_BASE/$path"
    
    # Create base directory if not exists
    mkdir -p "$WORKTREE_BASE"
    
    # Check if path already exists
    if [[ -d "$ABSOLUTE_WORKTREE_PATH" ]]; then
        echo -e "${RED}❌ 错误: 路径已存在: $ABSOLUTE_WORKTREE_PATH${NC}"
        exit 1
    fi
    
    # Determine branch name
    if [[ -z "$branch" ]]; then
        branch="$path"
    fi
    
    # Check if branch exists
    if git show-ref --verify --quiet refs/heads/"$branch"; then
        echo -e "${RED}❌ 错误: 分支 '$branch' 已存在${NC}"
        exit 1
    fi
    
    # Get base branch (main or master)
    local base_branch="main"
    if ! git show-ref --verify --quiet refs/heads/main; then
        base_branch="master"
    fi
    
    # Create worktree
    echo -e "${BLUE}📦 正在创建 worktree...${NC}"
    git worktree add -b "$branch" "$ABSOLUTE_WORKTREE_PATH" "$base_branch"
    
    # Copy environment files
    copy_environment_files "$MAIN_REPO_PATH" "$ABSOLUTE_WORKTREE_PATH"
    
    echo -e "${GREEN}✅ Worktree created at $ABSOLUTE_WORKTREE_PATH${NC}"
    
    # Open in IDE
    if [[ "$open_ide" == "true" ]]; then
        open_in_ide "$ABSOLUTE_WORKTREE_PATH"
    else
        read -p "🖥️  是否在 IDE 中打开 $ABSOLUTE_WORKTREE_PATH？[y/n]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open_in_ide "$ABSOLUTE_WORKTREE_PATH"
        fi
    fi
}

# List worktrees
list_worktrees() {
    echo -e "${BLUE}📋 Worktree 列表:${NC}"
    git worktree list
}

# Remove worktree
remove_worktree() {
    local path="$1"
    
    MAIN_REPO_PATH=$(get_main_repo_path)
    PROJECT_NAME=$(basename "$MAIN_REPO_PATH")
    WORKTREE_BASE="$MAIN_REPO_PATH/../.wt/$PROJECT_NAME"
    ABSOLUTE_WORKTREE_PATH="$WORKTREE_BASE/$path"
    
    if [[ ! -d "$ABSOLUTE_WORKTREE_PATH" ]]; then
        echo -e "${RED}❌ 错误: Worktree 不存在: $ABSOLUTE_WORKTREE_PATH${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}🗑️  正在删除 worktree: $ABSOLUTE_WORKTREE_PATH${NC}"
    git worktree remove "$ABSOLUTE_WORKTREE_PATH"
    echo -e "${GREEN}✅ Worktree 已删除${NC}"
}

# Prune worktrees
prune_worktrees() {
    echo -e "${YELLOW}🧹 正在清理无效的 worktree 引用...${NC}"
    git worktree prune
    echo -e "${GREEN}✅ 清理完成${NC}"
}

# Migrate content
migrate_content() {
    local target="$1"
    local source="$2"
    local use_stash="$3"
    
    MAIN_REPO_PATH=$(get_main_repo_path)
    PROJECT_NAME=$(basename "$MAIN_REPO_PATH")
    WORKTREE_BASE="$MAIN_REPO_PATH/../.wt/$PROJECT_NAME"
    TARGET_PATH="$WORKTREE_BASE/$target"
    
    if [[ ! -d "$TARGET_PATH" ]]; then
        echo -e "${RED}❌ 错误: 目标 worktree 不存在: $TARGET_PATH${NC}"
        exit 1
    fi
    
    # Check if target is clean
    cd "$TARGET_PATH"
    if ! git diff-index --quiet HEAD --; then
        echo -e "${RED}❌ 错误: 目标 worktree 有未提交的更改${NC}"
        exit 1
    fi
    
    if [[ "$use_stash" == "true" ]]; then
        # Migrate stash
        if ! git stash list | grep -q .; then
            echo -e "${RED}❌ 错误: 没有 stash 内容${NC}"
            exit 1
        fi
        echo -e "${BLUE}📦 正在迁移 stash 内容...${NC}"
        git stash pop
        echo -e "${GREEN}✅ Stash 内容已迁移${NC}"
    else
        # Migrate from source
        if [[ -z "$source" ]]; then
            echo -e "${RED}❌ 错误: 必须指定源路径或使用 --stash${NC}"
            exit 1
        fi
        
        SOURCE_PATH="$WORKTREE_BASE/$source"
        if [[ ! -d "$SOURCE_PATH" ]]; then
            SOURCE_PATH="$source"
        fi
        
        if [[ ! -d "$SOURCE_PATH" ]]; then
            echo -e "${RED}❌ 错误: 源路径不存在: $SOURCE_PATH${NC}"
            exit 1
        fi
        
        cd "$SOURCE_PATH"
        if git diff-index --quiet HEAD --; then
            echo -e "${YELLOW}⚠️  源路径没有未提交的更改${NC}"
            exit 0
        fi
        
        echo -e "${BLUE}📦 正在迁移未提交的更改...${NC}"
        git diff --name-only
        git stash
        cd "$TARGET_PATH"
        git stash pop
        echo -e "${GREEN}✅ 内容已迁移${NC}"
    fi
}

# Main command handler
main() {
    local command="$1"
    shift
    
    case "$command" in
        add)
            local path=""
            local branch=""
            local open_ide=false
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    -b|--branch)
                        branch="$2"
                        shift 2
                        ;;
                    -o|--open)
                        open_ide=true
                        shift
                        ;;
                    *)
                        if [[ -z "$path" ]]; then
                            path="$1"
                        fi
                        shift
                        ;;
                esac
            done
            
            if [[ -z "$path" ]]; then
                echo -e "${RED}❌ 错误: 必须指定路径${NC}"
                exit 1
            fi
            
            add_worktree "$path" "$branch" "$open_ide"
            ;;
        list)
            list_worktrees
            ;;
        remove)
            if [[ -z "$1" ]]; then
                echo -e "${RED}❌ 错误: 必须指定路径${NC}"
                exit 1
            fi
            remove_worktree "$1"
            ;;
        prune)
            prune_worktrees
            ;;
        migrate)
            local target="$1"
            shift
            local source=""
            local use_stash=false
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --from)
                        source="$2"
                        shift 2
                        ;;
                    --stash)
                        use_stash=true
                        shift
                        ;;
                    *)
                        shift
                        ;;
                esac
            done
            
            if [[ -z "$target" ]]; then
                echo -e "${RED}❌ 错误: 必须指定目标路径${NC}"
                exit 1
            fi
            
            migrate_content "$target" "$source" "$use_stash"
            ;;
        *)
            echo "用法: git-worktree <command> [options]"
            echo ""
            echo "命令:"
            echo "  add <path>             创建新的 worktree"
            echo "  list                   列出所有 worktree"
            echo "  remove <path>          删除指定的 worktree"
            echo "  prune                  清理无效的 worktree 引用"
            echo "  migrate <target>       迁移内容到指定的 worktree"
            echo ""
            echo "选项:"
            echo "  -b, --branch <branch>  指定分支名称"
            echo "  -o, --open             创建后直接在 IDE 中打开"
            echo "  --from <source>        指定迁移源路径"
            echo "  --stash                迁移 stash 内容"
            exit 1
            ;;
    esac
}

main "$@"
