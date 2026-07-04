"""Scan orchestration, refactor task building, and report formatting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from integrations.github.client import resolve_github_token
from integrations.github.repo_scope import (
    detect_git_remote_repo_scope,
    parse_github_repository_reference,
    split_repo_full_name,
)
from integrations.github.tools.workflow.models import GitHubIssueMutationProposal
from tools.architecture_issue_tool.scanners import (
    ArchitectureViolation,
    RefactorPriority,
    RefactorTask,
    resolve_repo_root,
    scan_compatibility_shims,
    scan_dependency_violations,
    scan_misplaced_modules,
    scan_oversized_files,
)

_GITHUB_ISSUE_GUIDANCE_GENERIC = (
    "Run `opensre architecture-scan propose` or `/architecture-scan propose` to build "
    "create-issue proposals. Run `... file-issues` to create issues after review. "
    "GitHub repo defaults from git remote upstream (Tracer-Cloud/opensre for this checkout). "
    "The scanner does not create GitHub issues automatically."
)


CANONICAL_OPENSRE_GITHUB_REPO = ("Tracer-Cloud", "opensre")


def _detect_git_remote_repo_scope_for_remote(
    remote_name: str,
    cwd: str | Path | None = None,
) -> tuple[str, str] | None:
    """Return owner/repo from ``git remote get-url <remote_name>`` when available."""
    import os
    import subprocess

    work_dir = Path(cwd or os.getcwd())
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote_name],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    from integrations.github.repo_scope import _parse_git_remote_url

    return _parse_git_remote_url(result.stdout)


def resolve_architecture_scan_github_repo_scope(
    cwd: str | Path | None = None,
) -> tuple[str, str] | None:
    """Resolve the GitHub repo for architecture-scan issue filing.

    Prefers ``upstream`` (canonical fork parent), then ``GITHUB_REPOSITORY``, then maps
    local ``opensre`` checkouts to ``Tracer-Cloud/opensre`` instead of a personal fork
    ``origin``, and finally falls back to ``origin``.
    """
    import os

    upstream = _detect_git_remote_repo_scope_for_remote("upstream", cwd=cwd)
    if upstream:
        return upstream

    env_repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if env_repo:
        owner, repo = split_repo_full_name(env_repo)
        if owner and repo:
            return owner, repo

    origin = detect_git_remote_repo_scope(cwd)
    if origin is not None and origin[1].lower() == "opensre":
        return CANONICAL_OPENSRE_GITHUB_REPO
    return origin


def format_github_repo_url(owner: str, repo: str) -> str:
    """Render a canonical GitHub repository URL for CLI/REPL examples."""
    return f"https://github.com/{owner}/{repo}"


def parse_github_repo_argument(value: str) -> tuple[str, str]:
    """Parse ``https://github.com/OWNER/REPO`` or ``OWNER/REPO`` into owner/repo."""
    parsed = parse_github_repository_reference(value)
    if not parsed:
        owner, repo = split_repo_full_name(value)
        if owner and repo:
            parsed = (owner, repo)
    if not parsed or not parsed[0] or not parsed[1]:
        msg = (
            f"Invalid GitHub repository {value!r}. Use https://github.com/OWNER/REPO or OWNER/REPO."
        )
        raise ValueError(msg)
    return parsed


def build_github_issue_guidance(
    *,
    owner: str | None = None,
    repo: str | None = None,
) -> str:
    """Render next-step GitHub issue commands, filling owner/repo when known."""
    if owner and repo:
        repo_url = format_github_repo_url(owner, repo)
        return (
            f"Next steps for {owner}/{repo}:\n"
            f"  opensre architecture-scan propose {repo_url}\n"
            f"  /architecture-scan propose {repo_url}\n"
            f"  opensre architecture-scan file-issues {repo_url}\n"
            f"  /architecture-scan file-issues {repo_url}\n"
            "Omitting `--issue-numbers` files issues for every refactor task. "
            "The scanner does not create GitHub issues automatically."
        )
    return _GITHUB_ISSUE_GUIDANCE_GENERIC


_GITHUB_TOKEN_SETUP_HINT = (
    "GitHub token is required to create issues. Run `opensre integrations setup github`, "
    "or set GITHUB_TOKEN or GH_TOKEN in your environment."
)

GITHUB_TOKEN_SETUP_HINT = _GITHUB_TOKEN_SETUP_HINT


def github_token_configured(github_token: str | None = None) -> bool:
    """Return True when a GitHub token is available for REST mutations."""
    return bool(resolve_github_token(github_token))


def _scan_error_payload(error: str) -> dict[str, Any]:
    return {"scan": {"error": error}, "error": error, "proposals": [], "count": 0}


def _scan_context_from_result(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": scan.get("summary"),
        "github_issue_creation": scan.get("github_issue_creation"),
    }


VIOLATION_TYPE_ORDER = (
    "dependency_direction",
    "compatibility_shim",
    "misplaced_module",
    "oversized_file",
)

_SECTION_LABELS: dict[str, str] = {
    "dependency_direction": "Dependency direction",
    "compatibility_shim": "Compatibility shims",
    "misplaced_module": "Misplaced modules",
    "oversized_file": "Oversized files",
}


def _priority_for(violation: ArchitectureViolation) -> RefactorPriority:
    if violation.type == "dependency_direction":
        return "high"
    if violation.type == "compatibility_shim":
        return "medium"
    if violation.type == "oversized_file":
        line_count = int(violation.details.get("line_count", 0))
        return "medium" if line_count > 800 else "low"
    return "medium"


def _title_for(violation: ArchitectureViolation) -> str:
    if violation.type == "dependency_direction":
        return f"Fix dependency direction violation in {violation.file_path}"
    if violation.type == "compatibility_shim":
        return f"Remove compatibility forwarding module {violation.file_path}"
    if violation.type == "oversized_file":
        return f"Split oversized module {violation.file_path}"
    return f"Relocate misplaced module {violation.file_path}"


def _description_for(violation: ArchitectureViolation) -> str:
    if violation.type == "dependency_direction":
        return (
            f"{violation.description} Resolve by moving shared logic to a lower layer "
            "or introducing a port/adapter. See AGENTS.md layering rules."
        )
    if violation.type == "compatibility_shim":
        module = violation.details.get("module", violation.file_path)
        return (
            f"The module '{module}' is a compatibility-only forwarding module. "
            "Migrate remaining import sites to the canonical path and delete this file."
        )
    if violation.type == "oversized_file":
        return (
            f"{violation.description} Extract validation, transport, and formatting "
            "into focused sibling modules."
        )
    return (
        f"{violation.description} Keep agent-callable tools under 'tools/' and "
        "integration clients/config under 'integrations/'."
    )


def build_refactor_tasks(violations: list[ArchitectureViolation]) -> list[RefactorTask]:
    return [
        RefactorTask(
            title=_title_for(violation),
            description=_description_for(violation),
            target_file=violation.file_path,
            violation_type=violation.type,
            priority=_priority_for(violation),
        )
        for violation in violations
    ]


def build_summary(violations: list[ArchitectureViolation]) -> dict[str, object]:
    by_type: dict[str, int] = {}
    for violation in violations:
        by_type[violation.type] = by_type.get(violation.type, 0) + 1
    return {"total": len(violations), "by_type": by_type}


def format_architecture_scan_report(scan_result: dict[str, Any]) -> str:
    """Render a deterministic text report shared by CLI, REPL, and tool output."""
    error = scan_result.get("error")
    if isinstance(error, str) and error:
        return f"Architecture violation scan failed: {error}"

    summary = scan_result.get("summary", {})
    by_type = summary.get("by_type", {})
    total = summary.get("total", 0)
    violations = scan_result.get("violations", [])

    lines = [
        "Architecture violation scan",
        f"Total: {total}",
        "",
        "Summary by type:",
    ]
    for violation_type in VIOLATION_TYPE_ORDER:
        count = by_type.get(violation_type, 0)
        lines.append(f"  {violation_type}: {count}")

    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in VIOLATION_TYPE_ORDER}
    for violation in violations:
        if not isinstance(violation, dict):
            continue
        item_type = violation.get("type")
        if isinstance(item_type, str) and item_type in grouped:
            grouped[item_type].append(violation)

    for violation_type in VIOLATION_TYPE_ORDER:
        items = grouped[violation_type]
        if not items:
            continue
        label = _SECTION_LABELS[violation_type]
        lines.extend(("", f"=== {label} ({len(items)}) ==="))
        for violation in items:
            file_path = str(violation.get("file_path", ""))
            description = str(violation.get("description", "")).strip()
            details = violation.get("details", {})
            if violation_type == "oversized_file" and isinstance(details, dict):
                line_count = details.get("line_count", "?")
                lines.append(f"  {file_path} ({line_count} lines)")
            else:
                lines.append(f"  {file_path}")
                if description:
                    lines.append(f"    {description}")

    guidance = scan_result.get("github_issue_creation")
    if isinstance(guidance, str) and guidance:
        lines.extend(("", "GitHub issues:", guidance))

    return "\n".join(lines)


def _architecture_proposal_digest(data: dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _issue_body_for_architecture_task(task: dict[str, Any], marker: str) -> str:
    violation_type = str(task.get("violation_type", "unknown"))
    target_file = str(task.get("target_file", ""))
    priority = str(task.get("priority", "medium"))
    description = str(task.get("description", "")).strip()
    return "\n".join(
        [
            "## Architecture refactor task",
            "",
            f"**Violation type:** {violation_type}",
            f"**Target file:** `{target_file}`",
            f"**Priority:** {priority}",
            "",
            "### Description",
            "",
            description or "(No description provided.)",
            "",
            f"<!-- {marker} -->",
        ]
    )


def build_github_issue_proposal_for_task(
    *,
    owner: str,
    repo: str,
    task: dict[str, Any],
    task_index: int,
) -> dict[str, Any]:
    """Build a create-issue proposal compatible with execute_github_issue_mutation."""
    seed = {
        "owner": owner,
        "repo": repo,
        "task_index": task_index,
        "title": str(task.get("title", "")),
        "target_file": str(task.get("target_file", "")),
        "violation_type": str(task.get("violation_type", "")),
    }
    proposal_id = f"gharch-{_architecture_proposal_digest(seed)}"
    marker = f"opensre-architecture-proposal:{proposal_id}"
    labels = task.get("suggested_labels")
    payload: dict[str, Any] = {
        "title": str(task.get("title", "Architecture refactor task")),
        "body": _issue_body_for_architecture_task(task, marker),
    }
    if isinstance(labels, list) and all(isinstance(label, str) for label in labels):
        payload["labels"] = labels

    proposal = GitHubIssueMutationProposal(
        proposal_id=proposal_id,
        operation="create",
        owner=owner,
        repo=repo,
        target={},
        payload=payload,
        slack_url="",
        idempotency_marker=marker,
    )
    return proposal.to_dict()


def propose_github_issues_from_tasks(
    *,
    owner: str,
    repo: str,
    proposed_refactor_tasks: list[dict[str, Any]],
    issue_numbers: list[int] | None = None,
) -> dict[str, Any]:
    """Build read-only GitHub issue proposals for architecture refactor tasks."""
    if not proposed_refactor_tasks:
        return {
            "error": "proposed_refactor_tasks is empty; run find_architecture_violations first",
            "proposals": [],
            "count": 0,
        }

    selected_indices = (
        list(range(len(proposed_refactor_tasks)))
        if issue_numbers is None
        else sorted({index for index in issue_numbers if isinstance(index, int)})
    )
    proposals: list[dict[str, Any]] = []
    skipped_indices: list[int] = []
    for index in selected_indices:
        if index < 0 or index >= len(proposed_refactor_tasks):
            skipped_indices.append(index)
            continue
        task = proposed_refactor_tasks[index]
        if not isinstance(task, dict):
            skipped_indices.append(index)
            continue
        proposals.append(
            build_github_issue_proposal_for_task(
                owner=owner,
                repo=repo,
                task=task,
                task_index=index,
            )
        )

    return {
        "proposals": proposals,
        "count": len(proposals),
        "skipped_indices": skipped_indices,
        "execute_with": (
            "Call execute_github_issue_mutation(owner, repo, proposal) for each approved "
            "proposal, or run `opensre architecture-scan file-issues` / "
            "`/architecture-scan file-issues`."
        ),
    }


def parse_issue_numbers(spec: str | None) -> list[int] | None:
    """Parse a comma-separated list of 0-based issue numbers from the scan."""
    if spec is None or not spec.strip():
        return None
    indices: list[int] = []
    for part in spec.split(","):
        stripped = part.strip()
        if not stripped:
            continue
        try:
            indices.append(int(stripped))
        except ValueError as exc:
            raise ValueError(f"Invalid issue number {stripped!r}: must be an integer.") from exc
    return indices


def run_architecture_scan_and_propose_github_issues(
    *,
    owner: str,
    repo: str,
    repo_root: str | None = None,
    max_file_lines: int = 500,
    include_baselines: bool = False,
    issue_numbers: list[int] | None = None,
) -> dict[str, Any]:
    """Scan the repository and build GitHub create-issue proposals."""
    scan = run_architecture_scan(
        repo_root=repo_root,
        max_file_lines=max_file_lines,
        include_baselines=include_baselines,
    )
    if isinstance(scan.get("error"), str) and scan["error"]:
        return {**_scan_error_payload(scan["error"])}

    tasks = scan.get("proposed_refactor_tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    if not tasks:
        return {
            "scan": _scan_context_from_result(scan),
            "proposals": [],
            "count": 0,
            "skipped_indices": [],
        }

    proposal_payload = propose_github_issues_from_tasks(
        owner=owner,
        repo=repo,
        proposed_refactor_tasks=tasks,
        issue_numbers=issue_numbers,
    )
    return {
        "scan": _scan_context_from_result(scan),
        **proposal_payload,
    }


def run_architecture_scan_and_file_github_issues(
    *,
    owner: str,
    repo: str,
    repo_root: str | None = None,
    max_file_lines: int = 500,
    include_baselines: bool = False,
    issue_numbers: list[int] | None = None,
) -> dict[str, Any]:
    """Scan, propose GitHub issues, and execute create-issue mutations."""
    from integrations.github.tools.work_status import execute_github_issue_mutation

    payload = run_architecture_scan_and_propose_github_issues(
        owner=owner,
        repo=repo,
        repo_root=repo_root,
        max_file_lines=max_file_lines,
        include_baselines=include_baselines,
        issue_numbers=issue_numbers,
    )
    if isinstance(payload.get("error"), str) and payload["error"]:
        return {**payload, "issue_results": []}

    proposals = payload.get("proposals", [])
    if not isinstance(proposals, list):
        proposals = []
    if proposals and not github_token_configured():
        return {
            **payload,
            "issue_results": [],
            "error": _GITHUB_TOKEN_SETUP_HINT,
        }

    issue_results: list[dict[str, Any]] = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        issue_results.append(
            execute_github_issue_mutation(owner=owner, repo=repo, proposal=proposal)
        )

    return {**payload, "issue_results": issue_results}


def run_architecture_scan(
    *,
    repo_root: str | None = None,
    max_file_lines: int = 500,
    include_baselines: bool = False,
) -> dict[str, Any]:
    root = resolve_repo_root(repo_root)
    if not root.is_dir():
        return {"error": f"Repository root does not exist: {root}"}

    violations: list[ArchitectureViolation] = []
    violations.extend(scan_dependency_violations(root, include_baselines=include_baselines))
    violations.extend(scan_oversized_files(root, max_file_lines=max_file_lines))
    violations.extend(scan_compatibility_shims(root))
    violations.extend(scan_misplaced_modules(root))

    tasks = build_refactor_tasks(violations)
    repo_scope = resolve_architecture_scan_github_repo_scope(root)
    owner, repo_name = repo_scope if repo_scope else (None, None)
    payload = {
        "violations": [v.to_dict() for v in violations],
        "proposed_refactor_tasks": [t.to_dict() for t in tasks],
        "summary": build_summary(violations),
        "github_issue_creation": build_github_issue_guidance(owner=owner, repo=repo_name),
    }
    if owner and repo_name:
        payload["github_repo_scope"] = {"owner": owner, "repo": repo_name}
    payload["report"] = format_architecture_scan_report(payload)
    return payload


PROPOSAL_TITLE_PREVIEW_LIMIT = 10


def format_scan_workflow_header(scan: dict[str, Any]) -> str:
    """One-line scan summary for propose/file-issues follow-up commands."""
    summary = scan.get("summary", {})
    if not isinstance(summary, dict):
        return "Architecture violation scan"
    total = summary.get("total", 0)
    by_type = summary.get("by_type", {})
    if not isinstance(by_type, dict):
        return f"Architecture violation scan: {total} total"
    parts = [
        f"{violation_type}: {by_type.get(violation_type, 0)}"
        for violation_type in VIOLATION_TYPE_ORDER
        if int(by_type.get(violation_type, 0)) > 0
    ]
    detail = ", ".join(parts) if parts else "no violations"
    return f"Architecture violation scan: {total} total ({detail})"


def _proposal_title(proposal: dict[str, Any]) -> str:
    payload = proposal.get("payload", {})
    if isinstance(payload, dict):
        title = payload.get("title")
        if isinstance(title, str) and title:
            return title
    return "(untitled)"


def format_proposal_titles(
    proposals: list[dict[str, Any]],
    *,
    count: int,
    preview_limit: int = PROPOSAL_TITLE_PREVIEW_LIMIT,
) -> list[str]:
    """Render proposal titles with a capped preview list."""
    lines = [f"GitHub issue proposals: {count}"]
    for index, proposal in enumerate(proposals):
        if index >= preview_limit:
            remaining = count - preview_limit
            if remaining > 0:
                lines.append(f"  - ... and {remaining} more")
            break
        if isinstance(proposal, dict):
            lines.append(f"  - {_proposal_title(proposal)}")
    return lines


def format_github_issue_error(error: str) -> str:
    """Add actionable hints for common GitHub issue API failures."""
    lowered = error.lower()
    if "issues has been disabled" in lowered or ("410" in error and "disabled" in lowered):
        return (
            f"{error}\n"
            "  Hint: enable Issues under repository Settings → General → Features, "
            "or target a repository where Issues are enabled."
        )
    return error


def summarize_issue_results(issue_results: list[dict[str, Any]]) -> list[str]:
    """Collapse per-issue results into concise CLI lines."""
    created: list[str] = []
    existing: list[str] = []
    failures: dict[str, int] = {}
    for item in issue_results:
        if not isinstance(item, dict):
            continue
        if item.get("executed"):
            issue = item.get("issue", {})
            number = issue.get("number", "?") if isinstance(issue, dict) else "?"
            url = issue.get("html_url", "") if isinstance(issue, dict) else ""
            created.append(f"  - created #{number} {url}".rstrip())
            continue
        if item.get("side_effect") == "existing_github_issue":
            issue = item.get("issue", {})
            number = issue.get("number", "?") if isinstance(issue, dict) else "?"
            url = issue.get("html_url", "") if isinstance(issue, dict) else ""
            existing.append(f"  - already exists #{number} {url}".rstrip())
            continue
        error = format_github_issue_error(str(item.get("error", "unknown error")))
        failures[error] = failures.get(error, 0) + 1

    lines = [*created, *existing]
    for error, failure_count in failures.items():
        if failure_count == 1:
            lines.append(f"  - failed: {error}")
        else:
            lines.append(f"  - failed ({failure_count}): {error}")
    return lines


def format_propose_report_text(
    result: dict[str, Any],
    *,
    include_scan_header: bool = True,
    list_titles: bool = True,
) -> str:
    """Render propose/file-issues scan output as plain text."""
    lines: list[str] = []
    scan = result.get("scan", {})
    if include_scan_header and isinstance(scan, dict):
        lines.append(format_scan_workflow_header(scan))
        lines.append("")

    error = result.get("error")
    if isinstance(error, str) and error:
        lines.append(error)
        return "\n".join(lines)

    count = int(result.get("count", 0))
    proposals = result.get("proposals", [])
    if not isinstance(proposals, list):
        proposals = []
    if list_titles:
        lines.extend(format_proposal_titles(proposals, count=count))
    else:
        lines.append(f"GitHub issue proposals: {count}")
    return "\n".join(lines)


def format_file_issues_report_text(result: dict[str, Any]) -> str:
    """Render file-issues output as plain text."""
    issue_results = result.get("issue_results", [])
    if not isinstance(issue_results, list):
        issue_results = []
    skip_titles = bool(result.get("error")) and not issue_results
    body = format_propose_report_text(
        result,
        include_scan_header=True,
        list_titles=not skip_titles,
    )
    lines = [body] if body else []
    if isinstance(result.get("error"), str) and result["error"] and not issue_results:
        return "\n".join(lines)

    lines.extend(["", "GitHub issue results:"])
    if not issue_results:
        lines.append("  - no issues filed")
        return "\n".join(lines)
    lines.extend(summarize_issue_results(issue_results))
    return "\n".join(lines)
