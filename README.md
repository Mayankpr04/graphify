# callmap

A tiny static-analysis tool that maps which functions call which across every
file in a Python codebase. Think rqt_graph-style function call visualization
for Python source code.

## Install
Clone this repository
```
git clone https://github.com/Mayankpr04/graphify.git
```
Then navigate to the directory and install

```
cd ~/graphify
python -m pip install -e .
```

## Run

From inside any Python codebase:

```
graph --open
```

You can also run:

```
callmap . -o graph.html --open
python -m callmap . -o graph.html
```

`graph` scans the current directory by default, so you can use it from inside
whatever Python codebase you are working on. The generated HTML is draggable,
zoomable, and colored by source file.

Add `--show-unresolved` to see calls that could not be matched to a scanned
definition, such as builtins, third-party libraries, or calls on instance
attributes whose type is not known statically.

## What It Does

- Walks every `.py` file with the `ast` module.
- Records every function and method definition.
- Records every call made from inside each function.
- Resolves straightforward imports across files.
- Renders an interactive `pyvis`/`vis-network` graph.

Examples it can resolve include:

- `utilities.load_config()`
- `from utilities import Cache; Cache()`
- `self.method()` inside a class, when a matching method is found in the same module

## Try The Demo

```powershell
python -m callmap demo_project -o demo.html --open
```

`demo_project/` has `main.py`, `utilities.py`, and `helpers.py`, matching the
small example used while building the tool.

## Limitations

- Instance method calls like `cache.set(...)` are not resolved unless the
  variable's type can be inferred trivially.
- Constructor calls like `Cache()` are not currently linked to `__init__`.
- Dynamic dispatch, such as `getattr(obj, name)()` or decorators that swap a
  function, cannot be seen by AST alone.
- Multiple functions with the same unqualified name in different classes can
  occasionally collide when resolved via `self.method()`.

These are solvable with deeper static analysis or type inference, but the
current version already handles the common case: module-level functions,
methods, and straightforward imports.
