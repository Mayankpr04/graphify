"""
callmap.cli
===========
Usage:
    callmap [path_to_codebase] [-o output.html]
    graph [path_to_codebase] [-o output.html]
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="callmap",
        description="Visualize which functions call which, across every file in a Python codebase.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory of the codebase to scan (default: current directory)",
    )
    parser.add_argument("-o", "--output", default="callmap.html", help="Output HTML file (default: callmap.html)")
    parser.add_argument("--open", action="store_true", help="Open the generated graph in your default browser")
    parser.add_argument(
        "--show-unresolved",
        action="store_true",
        help="Print calls that could not be matched to a scanned definition",
    )
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"[callmap] error: scan path does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"[callmap] error: scan path must be a directory: {root}", file=sys.stderr)
        return 2

    try:
        from .core import CallGraphBuilder
        from .render import render_html
    except ModuleNotFoundError as exc:
        print(f"[callmap] missing dependency: {exc.name}", file=sys.stderr)
        print("[callmap] install with: python -m pip install -e .", file=sys.stderr)
        return 1

    builder = CallGraphBuilder(str(root))
    graph = builder.build()

    print(
        f"[callmap] scanned {len(builder.modules)} module(s), "
        f"{graph.number_of_nodes()} function(s), {graph.number_of_edges()} call edge(s)."
    )
    if not builder.modules:
        print(f"[callmap] no Python files were found under {root}")
        print("[callmap] tip: run this from the root of a Python project, or pass that folder explicitly.")

    if args.show_unresolved:
        for qname, misses in builder.unresolved_calls().items():
            print(f"  {qname} -> {sorted(set(misses))}")

    out = Path(render_html(graph, args.output)).resolve()
    print(f"[callmap] wrote {out}")
    if args.open:
        webbrowser.open(out.as_uri())
    else:
        open_cmd = "start" if os.name == "nt" else "open"
        print("[callmap] open it in a browser, or rerun with --open.")
        print(f"[callmap] Windows shortcut: {open_cmd} {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
