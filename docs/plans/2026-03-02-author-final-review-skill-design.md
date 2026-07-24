# Author Final Review Skill Design

> User confirmed constraints:
> 1. Review only commits authored by self.
> 2. Review final state only (base..head), not intermediate commit snapshots.
> 3. Do not report bugs from early commits if fixed in final state.
> 4. Do comprehensive bug listing, no arbitrary issue-count cap.

## Problem

Existing review skills are strong for code quality, but they do not explicitly enforce:

- author-only scope filtering across multiple repos
- final-state-only evidence gating
- comprehensive (non-truncated) issue output as default

## Solution

Create new skill: `author-final-review`

- Input author identity + base/head refs + multi-repo list
- Build author scope from commits (`git log --author`)
- Build touched file set from author commits
- Review only final-state diff (`git diff base..head -- <author_file_set>`)
- Enforce evidence in final code state for each issue
- Output all confirmed issues (no top-N truncation)

## Components

1. `skills/author-final-review/SKILL.md`
- Workflow and quality gates
- Output schema and constraints

2. `skills/author-final-review/scripts/collect_author_scope.py`
- Collect commits/files/final numstat/collaborators for author scope
- Supports multiple repos
- Emits structured JSON for downstream review

## Trade-offs

1. Pros
- Avoids false positives from fixed intermediate defects
- Keeps review ownership clear (author-only)
- Scales to cross-repo changes

2. Cons
- Requires accurate base/head selection
- Author filtering is best-effort if names/emails are inconsistent

## Validation

- Python syntax compile passes
- Scope collector dry-run passes
- Skill quick validation passes

## Next Step

Use this skill to run full review against real project repos with explicit:
- `author=email`
- `base=target release branch`
- `head=final integration ref`
