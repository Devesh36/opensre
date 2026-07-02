# Architecture Issue Tool

Use `find_architecture_violations` when auditing codebase layering, shims, or module placement.

## When to invoke

- Before opening a large refactor PR
- When investigating recurring import-boundary CI failures
- When looking for compatibility forwarding modules to delete

## Reporting scan results

The tool returns a deterministic `report` string alongside structured `violations` and `summary`.

When presenting results to the user:

1. Include **all** counts from `summary.by_type` (dependency_direction, compatibility_shim, misplaced_module, oversized_file).
2. Prefer echoing the full `report` text verbatim when the user asked for a scan or audit.
3. Never omit a non-zero violation type from the summary (especially compatibility shims).

For guaranteed identical output across CLI and REPL without summarization, the user may run:

- `opensre architecture-scan` (CLI)
- `/architecture-scan` (REPL slash command)

Do not route natural-language requests to those commands unless the user explicitly asks to run them.

## GitHub issue creation

The scanner is read-only. To file GitHub issues from proposed tasks, make a **separate explicit call** to:

1. `propose_github_issue_mutation_from_slack` (build proposal)
2. `execute_github_issue_mutation` (create issue after approval)

Do not auto-create issues from scan output.
