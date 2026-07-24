# DIY Skill Reorganization Design

## Goal

Keep a small, self-contained collection of personally maintained skills with neutral examples and no private-system dependencies.

## Structure

- `skills/development`: requirements, implementation, and application discovery.
- `skills/review`: author review, quality review, test design, and team review.
- `skills/visualization`: diagram creation.
- `skills/platform`: discovery, worktree management, and local usage statistics.

## Cleanup Rules

- Remove imported skill collections and compatibility copies.
- Remove private integrations, generated artifacts, caches, credentials, and absolute local paths.
- Replace organization-specific examples with neutral sample applications and packages.
- Keep profiles, scripts, dependency declarations, and README indexes aligned with physical paths.

## Validation

- Confirm exactly 11 `SKILL.md` files remain.
- Confirm every profile and dependency entry resolves.
- Scan tracked and ignored workspace content for private identifiers and credential signatures.
- Run shell syntax, JSON parsing, repository audit, and installation dry-run checks.
- Leave all changes unstaged and uncommitted for review.

## README and SOP

- Document the profile-driven symlink model and every supported client target.
- Lead with a safe `audit -> dry-run -> install -> verify` workflow.
- Keep normal link uninstallation separate from destructive source removal.
- Use portable Mermaid `classDef` styling to distinguish safe actions, decisions, and destructive operations.
- Include direct script parameters, common commands, verification steps, and troubleshooting guidance.
