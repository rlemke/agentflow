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

"""Backup, restore, and file-import for the Claude workflow catalog.

The catalog is self-describing — each revision carries its FFL source, content
hash, version, status, and pinned dependencies — so a backup is just the
entries + revisions as JSON. The materialized ``FlowDefinition``s are NOT backed
up; restore re-materializes them by recompiling the FFL (the FFL is the source
of truth), which keeps backups small, readable, and git-friendly.

- ``export_to_file`` / ``export`` — dump the catalog to a JSON file/dict.
- ``restore_from_file`` / ``restore`` — load a backup, preserving revision
  identity (id, version, content_hash, status, pins) and rebuilding runnable
  flows in the target database.
- ``import_files`` / ``import_ffl`` — register file-based ``.ffl`` workflows
  into the catalog so Claude can discover and run them.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .store import _doc_to_entry, _doc_to_revision

BACKUP_FORMAT = "facetwork-catalog-backup"
BACKUP_VERSION = 1


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def export(service: Any) -> dict:
    """Return a JSON-serializable snapshot of the catalog (entries + revisions)."""
    catalog = service._catalog
    entries = catalog.list_entries()
    revisions: list = []
    for e in entries:
        revisions.extend(catalog.get_revisions_for_slug(e.slug))
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": int(time.time() * 1000),
        "entries": [asdict(e) for e in entries],
        "revisions": [asdict(r) for r in revisions],  # asdict recurses DependencyPin
    }


def export_to_file(service: Any, path: str | Path) -> dict:
    """Write ``export(service)`` to ``path`` as indented JSON. Returns a summary."""
    data = export(service)
    Path(path).write_text(json.dumps(data, indent=2, default=str))
    return {
        "path": str(path),
        "entries": len(data["entries"]),
        "revisions": len(data["revisions"]),
    }


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


def restore(data: dict, service: Any, *, rematerialize: bool = True) -> dict:
    """Load a backup into ``service``'s store.

    Writes entries + revisions verbatim (preserving revision_id, version,
    content_hash, status, and pinned deps), then — unless ``rematerialize`` is
    false — recompiles each revision to rebuild a runnable ``FlowDefinition`` in
    the target database. Idempotent. A revision whose FFL no longer compiles is
    restored as a non-runnable record (flow_id="" , is_valid=False) and reported.
    """
    fmt = data.get("format")
    if fmt != BACKUP_FORMAT:
        raise ValueError(f"not a catalog backup (format={fmt!r})")
    catalog = service._catalog

    for ed in data.get("entries", []):
        catalog.save_entry(_doc_to_entry(ed))
    for rd in data.get("revisions", []):
        catalog.save_revision(_doc_to_revision(rd))

    result: dict = {
        "entries": len(data.get("entries", [])),
        "revisions": len(data.get("revisions", [])),
        "rematerialized": 0,
        "failed": [],
    }
    if not rematerialize:
        return result

    # All revisions are now in the store, so pinned deps resolve regardless of order.
    for rd in data.get("revisions", []):
        rev = catalog.get_revision(rd["revision_id"])
        rebuilt = service.rematerialize(rev)
        catalog.save_revision(rebuilt)
        if rebuilt.flow_id:
            result["rematerialized"] += 1
        else:
            result["failed"].append(
                {"slug": rebuilt.slug, "version": rebuilt.version, "warnings": rebuilt.warnings}
            )
    return result


def restore_from_file(path: str | Path, service: Any, *, rematerialize: bool = True) -> dict:
    """Read a backup JSON file and ``restore`` it."""
    data = json.loads(Path(path).read_text())
    return restore(data, service, rematerialize=rematerialize)


# ---------------------------------------------------------------------------
# Import file-based FFL workflows
# ---------------------------------------------------------------------------


def import_ffl(service: Any, ffl_source: str, slug: str, *, publish: bool = False, **meta: Any):
    """Register one FFL string in the catalog (a thin wrapper over ``save`` that
    optionally publishes). ``meta`` accepts kind/title/description/tags/
    depends_on/entry_workflow/author/note."""
    res = service.save(slug, ffl_source=ffl_source, **meta)
    if publish and res.ok and res.is_valid:
        service.publish(slug, res.version)
        res.status = "published"
    return res


def import_files(
    service: Any,
    paths: list[str | Path],
    *,
    slug: str | None = None,
    publish: bool = False,
    **meta: Any,
) -> list[tuple[str, Any]]:
    """Import file-based ``.ffl`` workflows into the catalog.

    Each file becomes one catalog entry; directories are searched recursively
    for ``*.ffl``. The slug defaults to the file stem (``_`` → ``-``); an
    explicit ``--slug`` is only valid for a single file. Returns
    ``[(path, SaveResult), ...]``.
    """
    files: list[Path] = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            files.extend(sorted(pp.rglob("*.ffl")))
        elif pp.exists():
            files.append(pp)
        else:
            raise FileNotFoundError(str(pp))
    if slug and len(files) != 1:
        raise ValueError("--slug is only valid with a single .ffl file")

    out: list[tuple[str, Any]] = []
    for f in files:
        file_meta = dict(meta)
        file_meta.setdefault("title", f.stem)
        s = slug or f.stem.replace("_", "-")
        res = import_ffl(service, f.read_text(), s, publish=publish, **file_meta)
        out.append((str(f), res))
    return out
