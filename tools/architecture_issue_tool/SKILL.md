# Architecture Issue Tool

Use `find_architecture_violations` when auditing codebase layering, shims, or module placement.

## When to invoke

- Before opening a large refactor PR
- When investigating recurring import-boundary CI failures
- When looking for compatibility forwarding modules to delete

## GitHub issue creation

The scanner is read-only. To file GitHub issues from proposed tasks, make a **separate explicit call** to:

1. `propose_github_issue_mutation_from_slack` (build proposal)
2. `execute_github_issue_mutation` (create issue after approval)

Do not auto-create issues from scan output.
