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

For guaranteed identical output across CLI and REPL without summarization:

- `opensre architecture-scan` or `/architecture-scan` (report only)
- `opensre architecture-scan propose` or `/architecture-scan propose` (defaults to Tracer-Cloud/opensre in this repo)
- `opensre architecture-scan file-issues` or `/architecture-scan file-issues`

Do not route natural-language requests to those commands unless the user explicitly asks to run them.

## GitHub issue creation

Prefer explicit slash/CLI subcommands over chat-tool chaining:

1. `/architecture-scan propose` — scan + proposals (read-only); or pick **Propose issues** from the menu
2. `/architecture-scan file-issues` — scan + create issues; or pick **Create issues** from the menu

After either command, the REPL offers **Run … --issue-numbers** so you can target specific proposal numbers without retyping the full command.

Agent tools `propose_github_issues_from_architecture_tasks` and `execute_github_issue_mutation`
remain available for programmatic use, but the REPL gather loop only runs investigation-surface
tools — use slash subcommands for reliable GitHub filing from the terminal.

Do not auto-create issues from scan output.
