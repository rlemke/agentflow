# Claude workflow catalog

A way for Claude (or any author) to **write, store, version, discover, and run
FFL workflows without a file** — and to re-run them with different parameters
against a frozen, immutable body so an LLM can't inadvertently change the
workflow underneath an existing run configuration.

It is a thin layer over machinery the runtime already has: workflows are
stored as `FlowDefinition`s (not files), the dashboard already renders any
stored flow, and execution is the existing `fw:execute` bootstrap-task path.
The catalog adds discovery metadata, immutable versioning, library
composition, and a review gate.

## Two layers

1. **Runnable layer (reused).** Every saved revision materializes a normal
   `FlowDefinition` + `WorkflowDefinition`(s) under the path
   `claude:<slug>:v<version>` (mirroring the `example:<name>` seed path). This
   gives UI rendering, the runner, repair tooling, and the bootstrap run-path
   for free.
2. **Catalog layer (new).** Two collections:
   - `claude_workflows` — one **`CatalogEntry`** per logical workflow/library
     (stable `slug`, `kind`, `title`, `description`, `tags`, `latest_version`,
     `published_version`). Mutable metadata.
   - `claude_workflow_revisions` — append-only, immutable **`CatalogRevision`**s
     (frozen `ffl_source`, `content_hash`, the materialized `flow_id` +
     entry `workflow_id`, `param_schema`, `facets_used`, pinned `depends_on`,
     `status`, `is_valid`).

`facetwork/catalog/`: `entities.py`, `store.py` (`CatalogStore` protocol +
`InMemoryCatalogStore` + `MongoCatalogStore`), `service.py` (`CatalogService`).
The service is storage-agnostic — it takes a `CatalogStore` plus a `flow_store`
(`MongoStore` in prod, an in-memory store in tests) — so the logic is fully
testable offline.

## Immutability & versioning

- **Parameters are runtime inputs, never part of the body.** Changing params
  cannot change the workflow; the catalog records the `param_schema` (read from
  the compiled AST) for the UI form and for callers.
- **Revisions are content-hashed and append-only.** `content_hash =
  sha256(ffl_source + sorted pinned-dep hashes)`. Saving identical content
  **de-dupes** to the existing revision (no version churn); any change creates a
  new version. The old revision — its own `FlowDefinition` — stays runnable
  forever. A run **pins a revision**, so re-running with new inputs always
  re-uses the identical body.

## Review gate

Each revision has `status: draft | published`. `CatalogService.run` requires a
**published** revision on its default (unattended) path; a draft can only be run
with `allow_unpublished=True` (an explicit attended test). `publish()` refuses
an invalid revision. This keeps LLM-authored drafts from running unattended
until reviewed.

## Library composition

A `kind="library"` entry defines reusable facets/sub-workflows (no entry
point). A workflow `depends_on` libraries **pinned by revision**; at save time
the service merges the pinned library sources + the workflow source into one
compiled program (the same multi-file merge the seeder uses). Because deps are
pinned by revision, evolving a base library never alters an existing dependent —
upgrading is an explicit new dependent revision.

FFL `use` statements resolve **only** against this merged set (own source +
pinned libraries) — the catalog never reads the filesystem or the resolver's
`afl_sources` collection, so a `use` of a file-based namespace must first be
imported as a library and pinned. See
[`use` resolution: file-based vs. the catalog](catalog-use-resolution.md).

## MCP tools (the author-facing API)

On the `agentflow` MCP server:

| Tool | Purpose |
|------|---------|
| `fw_catalog_search` | Find a reusable workflow before authoring (query/tags/facet/kind) |
| `fw_catalog_get` | Inspect an entry + a revision (FFL, params, deps, versions) |
| `fw_catalog_save` | Validate + merge deps + compile → immutable draft revision (no file) |
| `fw_catalog_publish` | Review-approve a revision for unattended runs |
| `fw_catalog_run` | Pin a revision + post a `fw:execute` task with inputs |

Typical loop: `fw_catalog_search` → reuse, or `fw_validate` → `fw_catalog_save`
→ (review) `fw_catalog_publish` → `fw_catalog_run` (re-run with new inputs any
time; the body is pinned).

## Backup / restore / import (`scripts/catalog`)

The catalog is self-describing — each revision carries its FFL, content hash,
version, status, and pinned deps — so a backup is just the entries + revisions as
JSON; the materialized `FlowDefinition`s are NOT backed up (they're regenerable).
`facetwork/catalog/backup.py` + `facetwork/catalog/cli.py`, driven by
`scripts/catalog`:

```bash
scripts/catalog backup catalog.json          # dump entries + revisions to JSON
scripts/catalog restore catalog.json          # restore + rebuild runnable flows
scripts/catalog import path/to/wf.ffl --slug demo.x --publish   # file -> catalog
scripts/catalog import examples/dir/ --tags imported            # whole directory
scripts/catalog import-package osm-geocoder --tags osm          # whole package
```

- **Backup** writes a portable, readable, git-friendly JSON (`format:
  facetwork-catalog-backup`).
- **Restore** writes entries + revisions verbatim — **preserving revision_id,
  version, content_hash, status, and pinned deps** — then recompiles each
  revision to rebuild a runnable flow in the target DB (so the publish gate and
  dependency pins survive a wipe). A revision whose FFL no longer compiles is
  restored as a non-runnable record and reported. `--no-recompile` skips the flow
  rebuild.
- **Import** registers file-based `.ffl` workflows so Claude can discover and run
  them: each file becomes a catalog entry (slug from the file stem or `--slug`),
  validated and (optionally) published. This is how existing file-based workflows
  enter the catalog. Verified end-to-end against MongoDB: import → backup → wipe
  DB → restore → published + runnable.
- **Import-package** brings a whole multi-file FFL package (e.g. `osm-geocoder`,
  84 files / 99 workflows that only compile together via cross-file `use`) into
  the catalog. It merges every `.ffl` once into a single `kind="library"` entry —
  the **one shared flow** holding all the workflows — then creates one thin
  `kind="workflow"` entry per workflow: empty own FFL, a single pinned dependency
  on the library, pointing at its workflow within the shared flow. This keeps the
  catalog at one materialized flow per package instead of one (multi-MB) compiled
  program per workflow. `rematerialize` is shared-flow aware: a thin entry rebinds
  to the library's flow rather than building its own, so backup/restore stays at
  one flow per package too (verified live: 99 osm workflows → 1 `FlowDefinition`,
  preserved across a full backup → restore into a wiped DB). `--also <pkg>` merges
  extra packages for cross-package `use` deps; `--dir` imports a loose directory.

## Dashboard

A **Catalog** page (`/catalog`, `facetwork/dashboard/routes/execution/catalog.py`)
lists entries (search by name/description/tag/facet) and, per entry, shows the
revision history with **Publish** buttons, the parameter schema, pinned library
deps, the FFL source, a link to the materialized compiled flow, and a **Run**
form (inputs as JSON, with an "allow unpublished" opt-in) that submits a
bootstrap run to the fleet. With a non-Mongo store the page degrades to an
"unavailable" notice.

## What's not here yet

- Semantic/embedding search (current search is tags + keyword ranking).
- Handler-availability preflight on run (the catalog records `facets_used`;
  cross-checking against `fw_list_handlers` before running is a follow-up).
