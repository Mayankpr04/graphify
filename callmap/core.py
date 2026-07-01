"""
callmap.core
============
Static analysis engine that scans a Python codebase, extracts every
function/method definition and every call made from inside it, resolves
those calls across files (handling `import x`, `import x as y`,
`from x import y`, and `self.method()` / `cls.method()`), and builds a
directed graph you can render like an rqt_graph node graph.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import networkx as nx


@dataclass
class FunctionDef:
    qualified_name: str          # e.g. "utilities.helper" or "utilities.Thing.method"
    file: str
    lineno: int
    is_method: bool = False
    calls: List[str] = field(default_factory=list)   # raw, unresolved call expressions


class _ModuleScanner(ast.NodeVisitor):
    """Walks a single file's AST, recording imports, defs, and calls."""

    def __init__(self, module_name: str, filepath: str):
        self.module_name = module_name
        self.filepath = filepath
        self.imports: Dict[str, str] = {}                 # local_name -> dotted module path
        self.from_imports: Dict[str, tuple] = {}           # local_name -> (module, original_name)
        self.functions: Dict[str, FunctionDef] = {}
        self._class_stack: List[str] = []
        self._func_stack: List[FunctionDef] = []

    # -- imports -----------------------------------------------------
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self.imports[local] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            self.from_imports[local] = (module, alias.name)
        self.generic_visit(node)

    # -- defs ----------------------------------------------------------
    def _qualname(self, name: str) -> str:
        prefix = ".".join(self._class_stack)
        return f"{self.module_name}.{prefix}.{name}" if prefix else f"{self.module_name}.{name}"

    def visit_ClassDef(self, node: ast.ClassDef):
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node):
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_func(node)

    def _visit_func(self, node):
        qname = self._qualname(node.name)
        fdef = FunctionDef(
            qualified_name=qname,
            file=self.filepath,
            lineno=node.lineno,
            is_method=bool(self._class_stack),
        )
        self.functions[qname] = fdef
        self._func_stack.append(fdef)
        self.generic_visit(node)
        self._func_stack.pop()

    # -- calls -----------------------------------------------------------
    def visit_Call(self, node: ast.Call):
        if self._func_stack:
            name = self._flatten(node.func)
            if name:
                self._func_stack[-1].calls.append(name)
        self.generic_visit(node)

    @staticmethod
    def _flatten(node) -> Optional[str]:
        """Turn `a.b.c` attribute chains (or bare names) into a dotted string."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = _ModuleScanner._flatten(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return None


class CallGraphBuilder:
    """
    Scans every .py file under `root_dir`, then builds a networkx.DiGraph
    where nodes are fully-qualified function/method names and edges point
    from caller to callee.
    """

    def __init__(self, root_dir: str, exclude_dirs: Optional[Set[str]] = None):
        self.root_dir = Path(root_dir).resolve()
        self.exclude_dirs = exclude_dirs or {
            ".venv", "venv", "__pycache__", ".git", "node_modules", "build", "dist",
        }
        self.modules: Dict[str, _ModuleScanner] = {}
        self.graph = nx.DiGraph()

    # -- scanning ------------------------------------------------------
    def _module_name_for(self, path: Path) -> str:
        rel = path.relative_to(self.root_dir).with_suffix("")
        parts = rel.parts
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts) if parts else path.stem

    def _iter_py_files(self):
        for path in sorted(self.root_dir.rglob("*.py")):
            if any(part in self.exclude_dirs for part in path.parts):
                continue
            yield path

    def scan(self):
        for path in self._iter_py_files():
            module_name = self._module_name_for(path)
            try:
                source = path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(path))
            except SyntaxError as e:
                print(f"[callmap] skipping {path} ({e})", file=sys.stderr)
                continue
            scanner = _ModuleScanner(module_name, str(path.relative_to(self.root_dir)))
            scanner.visit(tree)
            self.modules[module_name] = scanner
        return self

    def _all_qualified_names(self) -> Set[str]:
        names = set()
        for scanner in self.modules.values():
            names.update(scanner.functions.keys())
        return names

    # -- resolution ------------------------------------------------------
    def _resolve(self, caller_module: str, all_names: Set[str], raw_call: str) -> Optional[str]:
        scanner = self.modules[caller_module]
        parts = raw_call.split(".")
        head = parts[0]

        # 1. defined in the same module, unqualified: helper()
        candidate = f"{caller_module}.{raw_call}"
        if candidate in all_names:
            return candidate

        # 2. self.method() / cls.method() -> find a method in this module ending in .method
        if head in ("self", "cls") and len(parts) > 1:
            suffix = "." + ".".join(parts[1:])
            matches = [n for n in all_names if n.startswith(caller_module + ".") and n.endswith(suffix)]
            if matches:
                return matches[0]

        # 3. `import utilities` / `import utilities as u`  ->  u.foo() or utilities.foo()
        if head in scanner.imports:
            target_module = scanner.imports[head]
            rest = ".".join(parts[1:])
            candidate = f"{target_module}.{rest}" if rest else target_module
            if candidate in all_names:
                return candidate

        # 4. `from utilities import foo` (optionally `as bar`) -> bar() / foo()
        if head in scanner.from_imports:
            src_module, orig_name = scanner.from_imports[head]
            rest = parts[1:]
            candidate = f"{src_module}.{orig_name}"
            if rest:
                candidate += "." + ".".join(rest)
            if candidate in all_names:
                return candidate

        return None

    # -- graph construction --------------------------------------------
    def build(self) -> nx.DiGraph:
        self.scan()
        all_names = self._all_qualified_names()

        for module_name, scanner in self.modules.items():
            for qname, fdef in scanner.functions.items():
                self.graph.add_node(
                    qname,
                    file=fdef.file,
                    module=module_name,
                    lineno=fdef.lineno,
                    is_method=fdef.is_method,
                )

        for module_name, scanner in self.modules.items():
            for qname, fdef in scanner.functions.items():
                for raw_call in fdef.calls:
                    resolved = self._resolve(module_name, all_names, raw_call)
                    if resolved and resolved != qname:
                        self.graph.add_edge(qname, resolved)

        return self.graph

    # -- convenience -------------------------------------------------------
    def unresolved_calls(self) -> Dict[str, List[str]]:
        """Calls that couldn't be matched to any scanned definition (e.g. stdlib, 3rd-party)."""
        all_names = self._all_qualified_names()
        out: Dict[str, List[str]] = {}
        for module_name, scanner in self.modules.items():
            for qname, fdef in scanner.functions.items():
                misses = [c for c in fdef.calls if not self._resolve(module_name, all_names, c)]
                if misses:
                    out[qname] = misses
        return out
