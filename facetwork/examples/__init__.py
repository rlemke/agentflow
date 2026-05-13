"""Discovery of Facetwork example packages.

Two sources are merged:

1. **Installed packages** declaring the ``facetwork.examples`` entry point.
   Each entry point loads to an :class:`ExamplePackage` instance.
2. **In-repo examples** under ``examples/<name>/`` with a ``handlers/`` package
   exposing ``register_all_registry_handlers(runner)`` and (optionally) an
   ``ffl/`` directory.

When the same name appears in both, the installed package wins.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import logging
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "facetwork.examples"

# Seed path stamped onto FlowDefinitions created by ``seed_example_flows``.
# One path per example so re-seeding a single example is cleanly scoped.
SEED_PATH_PREFIX = "example:"


@dataclass
class ExamplePackage:
    """A discoverable Facetwork example.

    Both installed packages and in-repo example directories surface as this
    type so callers can treat them uniformly.
    """

    name: str
    ffl_dir: Path | None
    register_handlers: Callable[[Any], None]
    runner_env: dict[str, str] = field(default_factory=dict)
    source: str = "entry_point"  # "entry_point" | "local"
    handlers_path: Path | None = None  # set for "local" examples; needed for sys.path
    extra_ffl_dirs: list[Path] = field(default_factory=list)
    # Extra directories to walk for *.ffl, in addition to ffl_dir and the
    # default root scan. Used by entry-point packages that ship FFL fixtures
    # outside their installed src/ tree (e.g. tests/real/ffl/ at the repo
    # root). Each dir is rglob'd; the standard tests/ exclusion still applies.


def _load_entry_point(ep: importlib.metadata.EntryPoint) -> ExamplePackage | None:
    try:
        obj = ep.load()
    except Exception as e:
        logger.warning("Failed to load example entry point %s: %s", ep.name, e)
        return None
    if not isinstance(obj, ExamplePackage):
        logger.warning(
            "Entry point %s did not resolve to ExamplePackage (got %s); skipping",
            ep.name,
            type(obj).__name__,
        )
        return None
    return obj


def discover_entry_point_examples() -> list[ExamplePackage]:
    """Return examples registered via the ``facetwork.examples`` entry point."""
    eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    found: list[ExamplePackage] = []
    for ep in eps:
        pkg = _load_entry_point(ep)
        if pkg is not None:
            found.append(pkg)
    return found


def _parse_runner_env(path: Path) -> dict[str, str]:
    """Parse a shell-style KEY=VALUE file.

    Strips a trailing ``# comment`` from unquoted values (matching shell
    assignment semantics where ``X=foo  # bar`` assigns ``foo``).
    """
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.lstrip()
        if value[:1] in ('"', "'"):
            quote = value[0]
            end = value.find(quote, 1)
            value = value[1:end] if end != -1 else value[1:]
        else:
            split_at = value.find(" #")
            if split_at != -1:
                value = value[:split_at]
            value = value.rstrip()
        if key:
            out[key] = value
    return out


def _make_local_register(example_dir: Path) -> Callable[[Any], None]:
    """Return a closure that imports ``handlers`` from ``example_dir`` and runs
    its ``register_all_registry_handlers(runner)``.

    Each call re-imports cleanly so multiple local examples can share the
    package name ``handlers`` without collision.
    """

    def register(runner: Any) -> None:
        path_str = str(example_dir)
        added = False
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
            added = True
        try:
            for key in [k for k in sys.modules if k == "handlers" or k.startswith("handlers.")]:
                del sys.modules[key]
            module = importlib.import_module("handlers")
            module.register_all_registry_handlers(runner)
        finally:
            if added and path_str in sys.path:
                sys.path.remove(path_str)

    return register


def discover_local_examples(repo_root: Path) -> list[ExamplePackage]:
    """Scan ``<repo_root>/examples/<name>/`` for in-repo example directories.

    An example qualifies if it has either ``handlers/__init__.py`` or an
    ``ffl/`` directory.
    """
    examples_dir = repo_root / "examples"
    if not examples_dir.is_dir():
        return []

    found: list[ExamplePackage] = []
    for entry in sorted(examples_dir.iterdir()):
        if not entry.is_dir():
            continue
        handlers_init = entry / "handlers" / "__init__.py"
        ffl_dir = entry / "ffl"
        has_handlers = handlers_init.is_file()
        has_ffl = ffl_dir.is_dir()
        if not has_handlers and not has_ffl:
            continue

        runner_env_path = entry / "runner.env"
        runner_env = _parse_runner_env(runner_env_path) if runner_env_path.is_file() else {}

        register = _make_local_register(entry) if has_handlers else (lambda _r: None)

        found.append(
            ExamplePackage(
                name=entry.name,
                ffl_dir=ffl_dir if has_ffl else None,
                register_handlers=register,
                runner_env=runner_env,
                source="local",
                handlers_path=entry if has_handlers else None,
            )
        )
    return found


def discover_all_examples(repo_root: Path | None = None) -> list[ExamplePackage]:
    """Return entry-point + local examples merged by name (entry-point wins)."""
    by_name: dict[str, ExamplePackage] = {}
    if repo_root is not None:
        for pkg in discover_local_examples(repo_root):
            by_name[pkg.name] = pkg
    for pkg in discover_entry_point_examples():
        by_name[pkg.name] = pkg
    return sorted(by_name.values(), key=lambda p: p.name)


def get_example(name: str, repo_root: Path | None = None) -> ExamplePackage | None:
    for pkg in discover_all_examples(repo_root):
        if pkg.name == name:
            return pkg
    return None


def filter_examples(
    examples: Iterable[ExamplePackage],
    *,
    include: list[str] | None = None,
) -> Iterator[ExamplePackage]:
    """Yield only examples whose names are in ``include`` (no filter if None)."""
    if include is None:
        for pkg in examples:
            yield pkg
        return
    wanted = set(include)
    for pkg in examples:
        if pkg.name in wanted:
            yield pkg


def _is_excluded_test_fixture(path: Path) -> bool:
    """Skip files under ``tests/`` unless they're under ``tests/real/``."""
    parts = path.parts
    if "tests" not in parts:
        return False
    i = parts.index("tests")
    return not (i + 1 < len(parts) and parts[i + 1] == "real")


def collect_ffl_files(pkg: ExamplePackage) -> list[Path]:
    """Return all .ffl files for ``pkg``, deduped and sorted.

    Walks three locations:
      1. ``pkg.ffl_dir`` (rglob).
      2. ``*/ffl/*.ffl`` under the example/package root — the convention used
         by domain pipelines like osm-geocoder where per-domain FFL lives
         alongside its handlers. Files outside the root are dropped.
      3. ``pkg.extra_ffl_dirs`` (each rglob'd) — explicit opt-in for FFL
         fixtures that live outside the installed package tree, e.g. an
         entry-point package's ``tests/real/ffl/`` at the repo root.

    Test fixtures are excluded everywhere except under ``tests/real/``.

    Root selection for (2):
      * Local example — ``handlers_path`` is the example dir.
      * Entry-point package — ``ffl_dir.parent`` is the installed package root.
    """
    files: list[Path] = []

    if pkg.handlers_path is not None:
        root = pkg.handlers_path
    elif pkg.ffl_dir is not None:
        root = pkg.ffl_dir.parent
    else:
        root = None

    if pkg.ffl_dir is not None and pkg.ffl_dir.is_dir():
        files.extend(sorted(pkg.ffl_dir.rglob("*.ffl")))

    if root is not None:
        real_root = root.resolve()
        for f in sorted(root.rglob("ffl/*.ffl")):
            try:
                f.resolve().relative_to(real_root)
            except ValueError:
                continue
            files.append(f)

    for extra in pkg.extra_ffl_dirs:
        if extra.is_dir():
            files.extend(sorted(extra.rglob("*.ffl")))

    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        real_f = f.resolve()
        if _is_excluded_test_fixture(real_f):
            continue
        if real_f in seen:
            continue
        seen.add(real_f)
        unique.append(f)
    return unique


# ---------------------------------------------------------------------------
# Seeding example workflows (FlowDefinition + WorkflowDefinition)
# ---------------------------------------------------------------------------


def _collect_workflow_names(node: dict, prefix: str = "") -> list[str]:
    """Collect fully-qualified workflow names from a compiled FFL program dict.

    Handles both the nested (``workflows`` / ``namespaces``) and the flat
    (``declarations`` with ``WorkflowDecl`` / ``Namespace``) emitter shapes.
    """
    names: list[str] = []
    for w in node.get("workflows", []):
        names.append(f"{prefix}{w['name']}" if prefix else w["name"])
    for decl in node.get("declarations", []):
        if decl.get("type") == "WorkflowDecl":
            names.append(f"{prefix}{decl['name']}" if prefix else decl["name"])
        elif decl.get("type") == "Namespace":
            names.extend(_collect_workflow_names(decl, f"{prefix}{decl['name']}."))
    for ns in node.get("namespaces", []):
        names.extend(_collect_workflow_names(ns, f"{prefix}{ns['name']}."))
    return names


def _compile_ffl_files(files: list[Path]) -> tuple[dict, str, list[str]]:
    """Parse + merge + emit a list of ``.ffl`` files.

    Returns ``(program_dict, combined_source, warnings)``. Parse errors raise;
    validation problems become warnings (an example may legitimately reference
    facets defined by another example).
    """
    from facetwork.ast import Program
    from facetwork.emitter import JSONEmitter
    from facetwork.parser import FFLParser
    from facetwork.validator import validate

    parser = FFLParser()
    programs = []
    parts: list[str] = []
    for path in files:
        text = Path(path).read_text()
        parts.append(text)
        programs.append(parser.parse(text, filename=str(path)))
    merged = Program.merge(programs)

    warnings: list[str] = []
    result = validate(merged)
    if not result.is_valid:
        warnings.append(f"{len(result.errors)} validation warning(s)")

    program_dict = json.loads(JSONEmitter(include_locations=False).emit(merged))
    return program_dict, "\n".join(parts), warnings


def seed_example_flows(
    pkg: ExamplePackage, store: Any, *, replace: bool = True
) -> tuple[int, int, list[str]]:
    """Compile ``pkg``'s FFL and upsert a FlowDefinition + its WorkflowDefinitions.

    Each example is seeded under its own path (``example:<name>``); when
    ``replace`` is set (default) any flows/workflows previously seeded under that
    path are deleted first, so re-running this — e.g. every time a runner
    container restarts — is idempotent rather than accumulating duplicates.

    Returns ``(flows_seeded, workflows_seeded, warnings)``; ``(0, 0, [...])`` when
    the example ships no ``.ffl`` files or declares no workflows.
    """
    from facetwork.runtime.entities import (
        FlowDefinition,
        FlowIdentity,
        SourceText,
        WorkflowDefinition,
    )
    from facetwork.runtime.types import generate_id

    files = collect_ffl_files(pkg)
    if not files:
        return 0, 0, []

    program_dict, combined_source, warnings = _compile_ffl_files(files)
    workflow_names = _collect_workflow_names(program_dict)
    if not workflow_names:
        return 0, 0, warnings

    seed_path = f"{SEED_PATH_PREFIX}{pkg.name}"

    if replace:
        # FlowDefinition deletion isn't part of PersistenceAPI; fall through to
        # the Mongo collection like scripts/seed-examples does. No-op on stores
        # without a ``_db`` (e.g. MemoryStore in tests).
        db = getattr(store, "_db", None)
        if db is not None:
            old_ids = [d["uuid"] for d in db.flows.find({"name.path": seed_path}, {"uuid": 1})]
            if old_ids:
                db.workflows.delete_many({"flow_id": {"$in": old_ids}})
            db.flows.delete_many({"name.path": seed_path})

    now_ms = int(time.time() * 1000)
    flow_id = generate_id()
    store.save_flow(
        FlowDefinition(
            uuid=flow_id,
            name=FlowIdentity(name=pkg.name, path=seed_path, uuid=flow_id),
            compiled_sources=[SourceText(name="source.ffl", content=combined_source)],
            compiled_ast=program_dict,
        )
    )
    for qname in workflow_names:
        wf_id = generate_id()
        store.save_workflow(
            WorkflowDefinition(
                uuid=wf_id,
                name=qname,
                namespace_id=seed_path,
                facet_id=wf_id,
                flow_id=flow_id,
                starting_step="",
                version="1.0",
                date=now_ms,
            )
        )
    return 1, len(workflow_names), warnings
