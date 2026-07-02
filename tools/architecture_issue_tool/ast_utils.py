"""Shared AST helpers for architecture scanners."""

from __future__ import annotations

import ast


def parse_module(source: str) -> ast.Module | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def class_base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def inherits_from(node: ast.ClassDef, base_names: set[str]) -> bool:
    return bool(class_base_names(node) & base_names)
