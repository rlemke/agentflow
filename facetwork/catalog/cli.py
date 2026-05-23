# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CLI for the Claude workflow catalog: backup, restore, import.

    python -m facetwork.catalog.cli backup catalog.json
    python -m facetwork.catalog.cli restore catalog.json
    python -m facetwork.catalog.cli import path/to/workflow.ffl --slug demo.x --publish
    python -m facetwork.catalog.cli import examples/dir/ --tags imported

Connects to MongoDB via the FFL config (AFL_MONGODB_URL etc.).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _service(config_path: str | None):
    from facetwork.catalog import CatalogService, MongoCatalogStore
    from facetwork.config import load_config
    from facetwork.runtime.mongo_store import MongoStore

    store = MongoStore.from_config(load_config(config_path).mongodb)
    return CatalogService(MongoCatalogStore(store._db), store)


def _parse_depends_on(raw: str) -> list[dict]:
    """'lib.a,lib.b@2' -> [{'slug':'lib.a'}, {'slug':'lib.b','version':2}]."""
    deps: list[dict] = []
    for part in (p.strip() for p in raw.split(",")):
        if not part:
            continue
        if "@" in part:
            slug, ver = part.rsplit("@", 1)
            deps.append({"slug": slug, "version": int(ver)})
        else:
            deps.append({"slug": part})
    return deps


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="facetwork-catalog", description=__doc__)
    p.add_argument("--config", default=None, help="FFL config file path")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("backup", help="Export the catalog to a JSON file")
    pb.add_argument("outfile", help="Destination .json path")

    pr = sub.add_parser("restore", help="Restore the catalog from a JSON backup")
    pr.add_argument("infile", help="Backup .json path")
    pr.add_argument(
        "--no-recompile",
        action="store_true",
        help="Restore records only; do not rebuild runnable flows from FFL",
    )

    pi = sub.add_parser("import", help="Import file-based .ffl workflows into the catalog")
    pi.add_argument("path", nargs="+", help=".ffl file(s) or directory(ies)")
    pi.add_argument("--slug", default=None, help="Slug (single file only; default: file stem)")
    pi.add_argument("--kind", default="workflow", help="workflow | library")
    pi.add_argument("--title", default="")
    pi.add_argument("--description", default="")
    pi.add_argument("--tags", default="", help="Comma-separated tags")
    pi.add_argument("--entry-workflow", default=None, help="Entry workflow name if multiple")
    pi.add_argument("--depends-on", default="", help="Comma-separated lib slugs, e.g. lib.a,lib.b@2")
    pi.add_argument("--publish", action="store_true", help="Publish each imported revision")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    from facetwork.catalog import backup

    try:
        svc = _service(args.config)
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}", file=sys.stderr)
        return 1

    if args.cmd == "backup":
        summary = backup.export_to_file(svc, args.outfile)
        print(f"Backed up {summary['entries']} entries / {summary['revisions']} revisions "
              f"-> {summary['path']}")
        return 0

    if args.cmd == "restore":
        res = backup.restore_from_file(args.infile, svc, rematerialize=not args.no_recompile)
        print(f"Restored {res['entries']} entries / {res['revisions']} revisions; "
              f"rebuilt {res['rematerialized']} flow(s).")
        for f in res["failed"]:
            print(f"  WARN {f['slug']} v{f['version']} not runnable: {'; '.join(f['warnings'])}",
                  file=sys.stderr)
        return 0

    if args.cmd == "import":
        meta: dict[str, Any] = {
            "kind": args.kind,
            "title": args.title,
            "description": args.description,
            "tags": [t.strip() for t in args.tags.split(",") if t.strip()] or None,
            "entry_workflow": args.entry_workflow,
            "depends_on": _parse_depends_on(args.depends_on) or None,
            "author": "import",
        }
        try:
            results = backup.import_files(
                svc, args.path, slug=args.slug, publish=args.publish, **meta
            )
        except (ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        rc = 0
        for path, res in results:
            if res.ok:
                tag = " (deduped)" if res.deduped else ""
                valid = "valid" if res.is_valid else "INVALID"
                print(f"  {res.slug} v{res.version} [{res.status}, {valid}]{tag}  <- {path}")
                if not res.is_valid:
                    rc = 1
            else:
                print(f"  FAILED {path}: {res.error}", file=sys.stderr)
                rc = 1
        return rc

    return 0


if __name__ == "__main__":
    sys.exit(main())
