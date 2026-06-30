#!/usr/bin/env python3
"""Migrate vendor tool dirs from tools/ → integrations/<vendor>/tools/.

Pure mechanical: git mv each dir, rewrite import paths, update registry.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Mapping: vendor_name → [list of tool directory names that exist in tools/]
# Each directory under tools/ is moved as a single unit.
# ---------------------------------------------------------------------------
VENDOR_MAP: dict[str, list[str]] = {
    "aws": [
        "aws_operation_tool",
        "cloudtrail_events_tool",
        "cloudwatch_batch_metrics_tool",
        "cloudwatch_logs_tool",
        "ec2_instances_by_tag_tool",
        "eks_tools",
        "elb_target_health_tool",
        "lambda_config_tool",
        "lambda_errors_tool",
        "lambda_inspect_tool",
        "lambda_invocation_logs_tool",
        "rds_describe_instance_tool",
        "rds_events_tool",
        "s3_get_object_tool",
        "s3_inspect_tool",
        "s3_list_tool",
        "s3_marker_tool",
    ],
    "azure": [
        "azure_monitor_logs_tool",
    ],
    "azure_sql": [
        "azure_sql_current_queries_tool",
        "azure_sql_resource_stats_tool",
        "azure_sql_server_status_tool",
        "azure_sql_slow_queries_tool",
        "azure_sql_wait_stats_tool",
    ],
    "redis": [
        "redis_client_list_tool",
        "redis_key_scan_tool",
        "redis_latency_doctor_tool",
        "redis_list_depth_tool",
        "redis_replication_tool",
        "redis_server_info_tool",
        "redis_slowlog_tool",
    ],
    "postgresql": [
        "postgresql_current_queries_tool",
        "postgresql_locks_tool",
        "postgresql_replication_status_tool",
        "postgresql_server_status_tool",
        "postgresql_slow_queries_tool",
        "postgresql_table_stats_tool",
    ],
    "mysql": [
        "mysql_current_processes_tool",
        "mysql_replication_status_tool",
        "mysql_server_status_tool",
        "mysql_slow_queries_tool",
        "mysql_table_stats_tool",
    ],
    "mariadb": [
        "mariadb_innodb_status_tool",
        "mariadb_process_list_tool",
        "mariadb_replication_tool",
        "mariadb_slow_queries_tool",
        "mariadb_status_tool",
    ],
    "mongodb": [
        "mongodb_collection_stats_tool",
        "mongodb_current_ops_tool",
        "mongodb_profiler_tool",
        "mongodb_replica_status_tool",
        "mongodb_server_status_tool",
    ],
    "mongodb_atlas": [
        "mongodb_atlas_alerts_tool",
        "mongodb_atlas_clusters_tool",
        "mongodb_atlas_events_tool",
        "mongodb_atlas_metrics_tool",
        "mongodb_atlas_performance_advisor_tool",
    ],
    "sentry": [
        "sentry_search_issues_tool",
        "sentry_issue_details_tool",
        "sentry_issue_events_tool",
        "sentry_mcp_tool",
        "fix_sentry_issue",
    ],
    "jira": [
        "jira_tools",
    ],
    "pagerduty": [
        "pagerduty_tools",
    ],
    "hermes": [
        "hermes_logs_tool",
        "hermes_session_evidence_tool",
    ],
    "signoz": [
        "signoz_tools",
    ],
    "tempo": [
        "tempo_tools",
    ],
    "temporal": [
        "temporal_tools",
    ],
    "tracer_cloud": [
        "tracer_airflow_dag_tool",
        "tracer_airflow_metrics_tool",
        "tracer_batch_statistics_tool",
        "tracer_error_logs_tool",
        "tracer_failed_jobs_tool",
        "tracer_failed_run_tool",
        "tracer_failed_tools_tool",
        "tracer_host_metrics_tool",
        "tracer_run_tool",
        "tracer_tasks_tool",
    ],
    "alertmanager": [
        "alertmanager_tools",
    ],
    "argocd": [
        "argocd_tools",
    ],
    "betterstack": [
        "betterstack_logs_tool",
    ],
    "bitbucket": [
        "bitbucket_commits_tool",
        "bitbucket_file_contents_tool",
        "bitbucket_search_code_tool",
    ],
    "clickhouse": [
        "clickhouse_query_activity_tool",
        "clickhouse_system_health_tool",
    ],
    "coralogix": [
        "coralogix_tools",
    ],
    "dagster": [
        "dagster_tools",
    ],
    "elasticsearch": [
        "elasticsearch_tools",
    ],
    "git": [
        "git_deploy_timeline_tool",
    ],
    "gitlab": [
        "gitlab_commits_tool",
        "gitlab_file_tool",
        "gitlab_mrs_tool",
        "gitlab_pipelines_tool",
    ],
    "google_docs": [
        "google_docs_tools",
    ],
    "groundcover": [
        "groundcover_tools",
    ],
    "helm": [
        "helm_tools",
    ],
    "honeycomb": [
        "honeycomb_tools",
    ],
    "incident_io": [
        "incident_io_tools",
    ],
    "jenkins": [
        "jenkins_tools",
    ],
    "kafka": [
        "kafka_consumer_group_tool",
        "kafka_topic_health_tool",
    ],
    "openclaw": [
        "openclaw_mcp_tool",
    ],
    "openobserve": [
        "openobserve_logs_tool",
    ],
    "opensearch": [
        "opensearch_analytics_tool",
    ],
    "opsgenie": [
        "opsgenie_tools",
    ],
    "posthog": [
        "posthog_mcp_tool",
    ],
    "prefect": [
        "prefect_tools",
    ],
    "rabbitmq": [
        "rabbitmq_broker_overview_tool",
        "rabbitmq_connection_stats_tool",
        "rabbitmq_consumer_health_tool",
        "rabbitmq_node_health_tool",
        "rabbitmq_queue_backlog_tool",
    ],
    "snowflake": [
        "snowflake_query_history_tool",
    ],
    "splunk": [
        "splunk_tools",
    ],
    "supabase": [
        "supabase_health_tool",
        "supabase_storage_tool",
    ],
    "telegram": [
        "telegram_send_message_tool",
    ],
    "twilio": [
        "twilio_notify_tool",
    ],
    "vercel": [
        "vercel_tools",
    ],
    "victoria_logs": [
        "victoria_logs_tools",
    ],
}


# ---------------------------------------------------------------------------
# Step 0: Verify all source directories exist
# ---------------------------------------------------------------------------
def verify_sources() -> None:
    missing: list[str] = []
    for vendor, tools in VENDOR_MAP.items():
        for tool in tools:
            src = REPO_ROOT / "tools" / tool
            if not src.is_dir():
                missing.append(f"tools/{tool}/  (vendor={vendor})")
    if missing:
        print("ERROR: Missing source directories:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        sys.exit(1)
    total_dirs = sum(len(t) for t in VENDOR_MAP.values())
    print(f"[verify] All {total_dirs} source directories exist OK")


# ---------------------------------------------------------------------------
# Step 1: Create integration __init__.py files where needed
# ---------------------------------------------------------------------------
def ensure_init(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content)
        print(f"  created {path.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Step 2: git mv each tool dir and rewrite imports
# ---------------------------------------------------------------------------
IMPORT_PATTERNS = [
    re.compile(rf"^from\s+tools\.({re.escape(tool)})\b", re.MULTILINE)
    for tool_list in VENDOR_MAP.values()
    for tool in tool_list
]

IMPORT_PATTERNS_STARTSWITH = [
    (tool, re.compile(rf"^from\s+tools\.{re.escape(tool)}\b", re.MULTILINE))
    for tool_list in VENDOR_MAP.values()
    for tool in tool_list
]

IMPORT_PATTERNS_IMPORT = [
    (tool, re.compile(rf"^import\s+tools\.{re.escape(tool)}\b", re.MULTILINE))
    for tool_list in VENDOR_MAP.values()
    for tool in tool_list
]


def rewrite_imports_in_file(filepath: Path, vendor: str, tool: str) -> bool:
    """Rewrite imports in a single file. Returns True if modified."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return False

    old_f = f"from tools.{tool}"
    new_f = f"from integrations.{vendor}.tools.{tool}"
    old_i = f"import tools.{tool}"
    new_i = f"import integrations.{vendor}.tools.{tool}"

    if old_f not in content and old_i not in content:
        return False

    modified = content.replace(old_f, new_f).replace(old_i, new_i)
    if modified != content:
        filepath.write_text(modified, encoding="utf-8")
        return True
    return False


def move_and_rewrite(vendor: str, tool: str) -> None:
    src = REPO_ROOT / "tools" / tool
    dst = REPO_ROOT / "integrations" / vendor / "tools" / tool

    if dst.exists():
        print(f"  SKIP (target exists): integrations/{vendor}/tools/{tool}/")
        return

    # git mv
    dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "mv", str(src), str(dst.parent)], capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        print(f"  FAIL git mv: {result.stderr.strip()}")
        return

    # Rewrite imports across the repo
    count = 0
    for pyfile in REPO_ROOT.rglob("*.py"):
        # Skip files inside the moved dir itself (already at destination)
        if pyfile.resolve().parent == dst.resolve() or dst.resolve() in pyfile.resolve().parents:
            continue
        # Skip __pycache__
        if "__pycache__" in pyfile.parts:
            continue
        if rewrite_imports_in_file(pyfile, vendor, tool):
            count += 1

    print(f"  moved tools/{tool}/ → integrations/{vendor}/tools/{tool}/  ({count} files updated)")


def rewrite_all_imports_for_tool(vendor: str, tool: str) -> int:
    """Pass 2: rewrite imports for a tool that was already moved.
    Needed when multiple tools share the same prefix and the first move
    already changed some paths."""
    count = 0
    for pyfile in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in pyfile.parts:
            continue
        if rewrite_imports_in_file(pyfile, vendor, tool):
            count += 1
    if count:
        print(f"  [{vendor}] re-check imports for {tool}: {count} files updated")
    return count


# ---------------------------------------------------------------------------
# Step 3: Update _INTEGRATION_TOOL_PACKAGES in tools/registry.py
# ---------------------------------------------------------------------------
def update_registry() -> None:
    registry_path = REPO_ROOT / "tools" / "registry.py"
    content = registry_path.read_text(encoding="utf-8")

    # Build insertion
    vendor_lines = []
    for vendor in sorted(VENDOR_MAP.keys()):
        vendor_lines.append(f'    "integrations.{vendor}.tools",')
    insert = "\n".join(vendor_lines) + "\n"

    # Find the existing _INTEGRATION_TOOL_PACKAGES block and replace it
    # Current content has:
    #   _INTEGRATION_TOOL_PACKAGES: tuple[str, ...] = (
    #       "integrations.datadog.tools",
    #       "integrations.grafana.tools",
    #   )
    # Replace the block between the opening and closing parens
    start_marker = "_INTEGRATION_TOOL_PACKAGES: tuple[str, ...] = ("
    end_marker = ")"

    start_idx = content.index(start_marker)
    end_idx = content.index(end_marker, start_idx + len(start_marker)) + 1

    old_block = content[start_idx:end_idx]
    new_block = f"_INTEGRATION_TOOL_PACKAGES: tuple[str, ...] = (\n{insert})"

    content = content.replace(old_block, new_block)
    registry_path.write_text(content, encoding="utf-8")
    print(f"[registry] Updated _INTEGRATION_TOOL_PACKAGES ({len(VENDOR_MAP)} vendors)")


# ---------------------------------------------------------------------------
# Step 4: Clean up stale empty dirs
# ---------------------------------------------------------------------------
def clean_stale() -> None:
    stale = [
        "tools/GrafanaLogsTool",
        "tools/GrafanaMetricsTool",
        "tools/GrafanaTracesTool",
    ]
    for d in stale:
        path = REPO_ROOT / d
        if path.is_dir():
            subprocess.run(["git", "rm", "-rf", str(path)], cwd=REPO_ROOT, capture_output=True)
            print(f"  removed {d}/ (stale empty dir)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    os.chdir(REPO_ROOT)

    print("=" * 60)
    print("T-3: Migrate vendor tools to integrations/<vendor>/tools/")
    print("=" * 60)

    # Step 0
    print("\n[0] Verifying sources...")
    verify_sources()

    # Step 1: Create integration package inits
    print("\n[1] Creating integration __init__.py files...")
    # Create __init__.py for new integrations that don't exist yet
    new_integrations = {"tracer_cloud", "git", "posthog", "gitlab"}
    for vendor in new_integrations:
        pkg_init = REPO_ROOT / "integrations" / vendor / "__init__.py"
        tools_init = REPO_ROOT / "integrations" / vendor / "tools" / "__init__.py"
        ensure_init(pkg_init, f'"""{vendor.title()} integration package."""\n')
        ensure_init(tools_init, f'"""{vendor.title()} tools."""\n')
        print(f"  created integrations/{vendor}/ (new integration)")

    # Also create __init__.py for any existing integration that doesn't have it
    for vendor in VENDOR_MAP:
        tools_init = REPO_ROOT / "integrations" / vendor / "tools" / "__init__.py"
        ensure_init(tools_init, f'"""{vendor.title()} tools."""\n')

    # Step 2: Move and rewrite
    print("\n[2] Moving tool dirs and rewriting imports...")
    # First, collect all import sites for all tools before any moves
    # (since git mv will change paths)

    # Pass 1: record tool-to-vendor mapping for import rewriting
    tool_to_vendor = {}
    for vendor, tools in VENDOR_MAP.items():
        for tool in tools:
            tool_to_vendor[tool] = vendor

    # We need to handle the fact that after git mv, the tool is no longer
    # at tools/<tool>/ but at integrations/<vendor>/tools/<tool>/.
    # For import rewriting, we need the CORRECT old path.
    #
    # Strategy: Do all git mv first, then rewrite all imports.

    # 2a: git mv all dirs
    for vendor, tools in VENDOR_MAP.items():
        for tool in tools:
            src = REPO_ROOT / "tools" / tool
            dst = REPO_ROOT / "integrations" / vendor / "tools" / tool
            if dst.exists():
                print(f"  SKIP integrations/{vendor}/tools/{tool}/ (target exists)")
                continue
            if not src.is_dir():
                print(f"  SKIP tools/{tool}/ (source not found)")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "mv", str(src), str(dst.parent)], capture_output=True, cwd=REPO_ROOT
            )
            print(f"  moved tools/{tool}/ → integrations/{vendor}/tools/{tool}/")

    # 2b: Rewrite all imports (across entire repo, including moved dirs)
    print("\n  Rewriting import paths across repo...")
    total_updated = 0
    for pyfile in sorted(REPO_ROOT.rglob("*.py")):
        if "__pycache__" in pyfile.parts:
            continue
        content_before = pyfile.read_text(encoding="utf-8") if pyfile.is_file() else ""
        if not content_before:
            continue
        content_after = content_before
        for tool, vendor in tool_to_vendor.items():
            old_f = f"from tools.{tool}"
            new_f = f"from integrations.{vendor}.tools.{tool}"
            old_i = f"import tools.{tool}"
            new_i = f"import integrations.{vendor}.tools.{tool}"
            content_after = content_after.replace(old_f, new_f)
            content_after = content_after.replace(old_i, new_i)
        if content_after != content_before:
            pyfile.write_text(content_after, encoding="utf-8")
            total_updated += 1

    print(f"  {total_updated} files had import rewrites")

    # Step 3: Update registry
    print("\n[3] Updating registry...")
    update_registry()

    # Step 4: Clean stale
    print("\n[4] Cleaning stale empty dirs...")
    clean_stale()

    print("\n" + "=" * 60)
    print("DONE. Run verification:")
    print(
        '  grep -rn "^from tools\\." --include="*.py" . | grep -vE "(utils|base|registry|registered_tool|tool_decorator|_telemetry|skill_guidance|investigation_registry|fleet_monitoring|watch_dog|sre_guidance_tool|pi_coding_tool|work_status_report_tool|community_followup_tool|github|interactive_shell|investigation)"'
    )
    print("  make typecheck")
    print("  make test-cov")
    print("=" * 60)


if __name__ == "__main__":
    main()
