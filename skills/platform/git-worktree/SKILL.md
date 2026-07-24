---
name: git-worktree
description: Manages Git worktrees with intelligent defaults, IDE integration, and content migration. Uses structured ../.wt/project-name/ paths. Use when the user wants to create, manage, or migrate Git worktrees, or asks about working with multiple branches simultaneously.
tags: devops, git, general
author: youqi.sjh
created: 2026-03-05T13:09:51Z
updated: 2026-03-10T10:00:00Z
---

# Git Worktree Management

Manage Git worktrees with intelligent defaults, IDE integration, and content migration using structured `../.wt/项目名/` paths.

## Quick Start

Execute commands directly and provide concise results.

**Implementation**: The skill includes a shell script at `scripts/git-worktree.sh` that implements all functionality. When executing commands, use this script or guide the user to use it.

### Basic Operations

```bash
# Create new branch from main/master
git-worktree add <path>

# Create new branch with specified name
git-worktree add <path> -b <branch>

# Create and open in IDE
git-worktree add <path> -o

# List all worktrees
git-worktree list

# Remove worktree
git-worktree remove <path>

# Clean invalid worktree records
git-worktree prune
```

### Content Migration

```bash
# Migrate uncommitted changes
git-worktree migrate <target> --from <source>

# Migrate stash content
git-worktree migrate <target> --stash
```

## Core Features

### 1. Environment Detection

- Validates Git repository via `git rev-parse --is-inside-work-tree`
- Detects if in main repo or existing worktree
- Calculates paths intelligently

### 2. Smart Path Management

Uses structured `../.wt/项目名/<path>` directory structure:

```bash
# Path calculation logic
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

MAIN_REPO_PATH=$(get_main_repo_path)
PROJECT_NAME=$(basename "$MAIN_REPO_PATH")
WORKTREE_BASE="$MAIN_REPO_PATH/../.wt/$PROJECT_NAME"
ABSOLUTE_WORKTREE_PATH="$WORKTREE_BASE/<path>"
```

**Key fix**: Always use absolute paths when creating new worktrees from existing worktrees to prevent nested paths like `../.wt/project/.wt/project/path`.

### 3. Intelligent Defaults

- **Branch creation**: Uses path name as branch name if `-b` not specified
- **Base branch**: Creates new branch from main/master
- **Path resolution**: Uses branch name as path if path not specified
- **IDE integration**: Auto-detects and prompts to open in IDE

### 4. Environment File Handling

Automatically copies environment files from `.gitignore`:

```bash
copy_environment_files() {
    local main_repo="$MAIN_REPO_PATH"
    local target_worktree="$ABSOLUTE_WORKTREE_PATH"
    local gitignore_file="$main_repo/.gitignore"
    
    if [[ ! -f "$gitignore_file" ]]; then
        return 0
    fi
    
    # Detect .env files
    if [[ -f "$main_repo/.env" ]] && grep -q "^\.env$" "$gitignore_file"; then
        cp "$main_repo/.env" "$target_worktree/.env"
    fi
    
    # Detect .env.* pattern files (exclude .env.example)
    for env_file in "$main_repo"/.env.*; do
        if [[ -f "$env_file" ]] && [[ "$(basename "$env_file")" != ".env.example" ]]; then
            local filename=$(basename "$env_file")
            if grep -q "^\.env\.\*$" "$gitignore_file"; then
                cp "$env_file" "$target_worktree/$filename"
            fi
        fi
    done
}
```

### 5. IDE Integration

Auto-detects and supports:
- VS Code
- Cursor
- WebStorm
- Sublime Text
- Vim

Use `-o` flag to skip prompt and open directly.

### 6. Content Migration

**Migration workflow**:
1. Verify source has uncommitted content
2. Ensure target worktree is clean
3. Display changes to be migrated
4. Use git commands to migrate safely
5. Confirm results and suggest next steps

## Options

| Option | Description |
|--------|-------------|
| `add [<path>]` | Add new worktree at `../.wt/项目名/<path>` |
| `migrate <target>` | Migrate content to specified worktree |
| `list` | List all worktrees and their status |
| `remove <path>` | Remove specified worktree |
| `prune` | Clean invalid worktree references |
| `-b <branch>` | Create new branch and checkout to worktree |
| `-o, --open` | Open in IDE after creation (skip prompt) |
| `--from <source>` | Specify migration source path |
| `--stash` | Migrate current stash content |
| `--track` | Set new branch to track remote branch |
| `--guess-remote` | Auto-guess remote branch for tracking |
| `--detach` | Create detached HEAD worktree |
| `--checkout` | Checkout immediately after creation (default) |
| `--lock` | Lock worktree after creation |

## Examples

```bash
# Basic usage
git-worktree add feature-ui                       # Create branch 'feature-ui' from main/master
git-worktree add feature-ui -b my-feature         # Create branch 'my-feature', path 'feature-ui'
git-worktree add feature-ui -o                    # Create and open in IDE

# Content migration
git-worktree add feature-ui -b feature/new-ui     # Create new feature worktree
git-worktree migrate feature-ui --from main       # Migrate uncommitted changes
git-worktree migrate hotfix --stash               # Migrate stash content

# Management
git-worktree list                                 # View all worktrees
git-worktree remove feature-ui                    # Remove worktree
git-worktree prune                                # Clean invalid references
```

## Directory Structure

```
parent-directory/
├── your-project/            # Main project
│   ├── .git/
│   └── src/
└── .wt/                    # Worktree management
    └── your-project/        # Project worktrees
        ├── feature-ui/      # Feature branch
        ├── hotfix/          # Hotfix branch
        └── debug/           # Debug worktree
```

## Security Features

- **Path conflict protection**: Checks if directory exists before creation
- **Branch checkout verification**: Ensures branch not used elsewhere
- **Absolute path enforcement**: Prevents nested `.wt` directories in worktrees
- **Auto cleanup on removal**: Cleans both directory and git references
- **Clear status reporting**: Shows worktree location and branch status

## Implementation

The skill includes a complete shell script implementation at `scripts/git-worktree.sh`. When users request git-worktree operations:

1. **Execute the script directly** if the user has it in their PATH
2. **Guide execution** by providing the script path and command
3. **Explain the operation** before executing to confirm intent

Example execution:
```bash
# If script is in PATH
git-worktree add feature-ui -o

# If using script directly
bash ~/.cursor/skills/git-worktree/scripts/git-worktree.sh add feature-ui -o
```

## Notes

- **Performance**: Worktrees share `.git` directory, saving disk space
- **Migration**: Only uncommitted changes; use `git cherry-pick` for committed content
- **IDE requirement**: Command-line tools must be in PATH
- **Cross-platform**: Supports Windows, macOS, Linux (script uses bash)
- **Environment files**: Auto-copies `.gitignore` listed env files to new worktree
- **File exclusion**: Template files like `.env.example` remain only in main repo
- **Script location**: Implementation script at `scripts/git-worktree.sh` in skill directory
