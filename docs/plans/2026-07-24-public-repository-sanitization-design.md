# Public Repository Sanitization Design

## Goal

Publish a repository snapshot that contains only reusable, organization-neutral skills and supporting files.

## Scope

- Remove skills whose primary purpose is accessing organization-specific systems.
- Remove compatibility copies and workflow entrypoints that depend on those skills.
- Remove credential setup scripts, generated artifacts, and documentation tied to private systems.
- Sanitize reusable skills by removing optional private-system adapters and examples.
- Update manifests, profiles, installation scripts, and indexes so every remaining reference resolves.

## History Strategy

The public remote will be replaced with a new root commit containing the sanitized snapshot. The private remote will not be modified. This prevents deleted files and credentials from remaining accessible through the public Git history.

## Validation

- Search the complete snapshot for organization names, private domains, internal skill names, and credential patterns.
- Verify every listed skill directory and manifest entry exists.
- Run repository audit, shell syntax, JSON parsing, and Markdown link checks where available.
- Compare the public remote branch hash with the local sanitized root commit.
