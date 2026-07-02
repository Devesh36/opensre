"""Architecture violation scanners."""

from tools.architecture_issue_tool.scanners.dependencies import scan_dependency_violations
from tools.architecture_issue_tool.scanners.misplaced import scan_misplaced_modules
from tools.architecture_issue_tool.scanners.oversized import scan_oversized_files
from tools.architecture_issue_tool.scanners.shims import scan_compatibility_shims

__all__ = [
    "scan_compatibility_shims",
    "scan_dependency_violations",
    "scan_misplaced_modules",
    "scan_oversized_files",
]
