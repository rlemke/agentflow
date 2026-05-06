"""CLI: register handlers for one or more examples into the registry.

Usage::

    python -m facetwork.examples [NAME ...]

With no names, registers handlers for every discovered example. Used by
``scripts/start-runner`` and ``scripts/seed-examples``; safe to call
directly for ad-hoc registration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from facetwork.examples import discover_all_examples, filter_examples
from facetwork.runtime import Evaluator, RegistryRunner, Telemetry
from facetwork.runtime.mongo_store import MongoStore


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    selected = argv or None

    repo_root = Path(os.environ.get("REPO_ROOT", os.getcwd()))
    examples = list(filter_examples(discover_all_examples(repo_root), include=selected))

    if not examples:
        print("No examples found (checked entry points and examples/).", file=sys.stderr)
        return 1

    mongo_url = os.environ.get("AFL_MONGODB_URL", "mongodb://afl-mongodb:27017")
    store = MongoStore(mongo_url)
    runner = RegistryRunner(store, Evaluator(store, Telemetry()))

    print("Registering handlers (upsert)...")
    print()
    total = 0
    for pkg in examples:
        if pkg.handlers_path is None and pkg.source == "local":
            print(f"  {pkg.name}: SKIP (no handlers/)")
            continue
        before = store._db.handler_registrations.count_documents({})
        try:
            pkg.register_handlers(runner)
        except Exception as e:
            print(f"  {pkg.name}: ERROR — {e}")
            continue
        count = store._db.handler_registrations.count_documents({}) - before
        total += count
        print(f"  {pkg.name}: {count} handlers registered  [{pkg.source}]")

    print()
    print(f"Total: {total} handlers registered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
