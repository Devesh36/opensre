"""Bridge to CI import-graph helpers under ``.github/ci/``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, cast

_CI_DIR = Path(__file__).resolve().parents[2] / ".github" / "ci"
if str(_CI_DIR) not in sys.path:
    sys.path.insert(0, str(_CI_DIR))

_check_direct_imports = importlib.import_module("check_direct_imports")
_check_import_cycles = importlib.import_module("check_import_cycles")

_REQUIRED_DIRECT_SYMBOLS = ("_BASELINE_IGNORES", "DirectViolation", "find_direct_violations")
_REQUIRED_CYCLE_SYMBOLS = ("_build_graph",)

for symbol in _REQUIRED_DIRECT_SYMBOLS:
    if not hasattr(_check_direct_imports, symbol):
        msg = f"check_direct_imports is missing required symbol {symbol!r}"
        raise ImportError(msg)

for symbol in _REQUIRED_CYCLE_SYMBOLS:
    if not hasattr(_check_import_cycles, symbol):
        msg = f"check_import_cycles is missing required symbol {symbol!r}"
        raise ImportError(msg)

_BASELINE_IGNORES = cast(Any, _check_direct_imports._BASELINE_IGNORES)
DirectViolation = cast(Any, _check_direct_imports.DirectViolation)
find_direct_violations = cast(Any, _check_direct_imports.find_direct_violations)
_build_graph = cast(Any, _check_import_cycles._build_graph)

__all__ = [
    "_BASELINE_IGNORES",
    "DirectViolation",
    "_build_graph",
    "find_direct_violations",
]
