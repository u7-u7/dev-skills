# Windows Installer Design

## Goal

Add a native Windows installation path without changing the existing Bash installer for macOS and Linux.

## Supported workflow

The first Windows release supports the common profile workflow:

- install all skills from a profile;
- preview changes with dry-run;
- uninstall links owned by this repository;
- replace conflicting targets only when force is explicitly enabled;
- detect Cursor, Claude Code, and Codex from their user configuration directories or commands.

Advanced interactive selection and per-skill conflict policies remain Bash-only for now.

## Implementation

Add `scripts/install_team_bundle.ps1`, compatible with Windows PowerShell 5.1 and PowerShell 7. The script reads `config/profiles/<name>.skills`, validates each selected skill and its `SKILL.md`, resolves declared `depends_on` entries, then links each skill into detected client directories.

Directory links use Windows junctions. Junctions work for local directories without requiring Developer Mode or an elevated shell. The installer records ownership implicitly through the junction target: uninstall removes a junction only when it resolves to the expected repository skill directory.

Provide root-level PowerShell entry points through a small command dispatcher so Windows users do not need GNU Make. The existing Make targets and Bash installer remain unchanged.

## Safety and errors

- Dry-run never creates directories, links, or files.
- Existing physical files and directories are skipped unless `-Force` is supplied.
- Uninstall never removes a target that is not a reparse point owned by this repository.
- Missing clients are skipped with a diagnostic message.
- Invalid profiles, missing skill directories, and missing `SKILL.md` files fail before link mutation begins.

## Verification

Tests run the PowerShell installer against temporary repository and user-home fixtures. They cover profile loading, dependency expansion, dry-run behavior, junction creation, idempotent reinstall, conflict handling, force replacement, and safe uninstall. Platform-independent repository checks continue to run on macOS/Linux.
