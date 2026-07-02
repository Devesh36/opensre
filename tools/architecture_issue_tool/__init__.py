"""Architecture violation scanner for maintainers."""

from tools.architecture_issue_tool.tool import find_architecture_violations

TOOL_MODULES = ("tool",)

__all__ = ["TOOL_MODULES", "find_architecture_violations"]
