# Facetwork Example Template

Skeleton for a **standalone Facetwork example package**. Copy this directory
to a new git repo, rename `example_template` to your example's import name,
and you have an installable example that Facetwork's runner and seeder will
discover automatically — no changes to the Facetwork repo required.

## Layout

```
example-template/
├── pyproject.toml                          # declares facetwork.examples entry point
├── README.md
├── src/example_template/
│   ├── __init__.py                         # exports `example: ExamplePackage`
│   ├── handlers/
│   │   ├── __init__.py                     # register_all_registry_handlers(runner)
│   │   └── greeter_handlers.py
│   └── ffl/
│       └── greeter.ffl
└── tests/
```

The package exposes a single attribute via the `facetwork.examples` entry
point group:

```toml
[project.entry-points."facetwork.examples"]
example-template = "example_template:example"
```

`example` is an `ExamplePackage` instance from `facetwork.examples` with the
example's display name, FFL directory, and a `register_handlers(runner)`
callable.

## Install & run

```bash
# In the example repo:
pip install -e .

# In the Facetwork repo (no edits needed):
scripts/seed-examples --include example-template
scripts/start-runner --example example-template
```

`scripts/start-runner --example NAME` and `scripts/seed-examples` discover
both in-repo `examples/<name>/` directories and pip-installed packages
declaring the `facetwork.examples` entry point — installed packages take
precedence on name collision.

## Optional: per-runner env overrides

If your example needs runner env overrides (e.g. longer execution timeouts),
populate `runner_env` on the `ExamplePackage`:

```python
example = ExamplePackage(
    name="example-template",
    ffl_dir=Path(__file__).parent / "ffl",
    register_handlers=register_all_registry_handlers,
    runner_env={
        "AFL_TASK_EXECUTION_TIMEOUT_MS": "14400000",
    },
)
```

These are exported into the runner's environment by `scripts/start-runner`.

## Migrating an existing `examples/<name>/` directory

1. Create a new git repo from this template.
2. Rename `example_template` → your example's package name (e.g. `osm_geocoder_facetwork`).
3. Move `examples/<name>/handlers/` → `src/<package>/handlers/`.
4. Move `examples/<name>/ffl/` (and any nested `ffl/` dirs) → `src/<package>/ffl/`.
5. Update `module_uri` strings in your handler registrations from
   `file:///.../handlers/foo.py` (or relative names like `handlers.foo`) to
   the package-qualified form `<package>.handlers.foo`.
6. If `examples/<name>/runner.env` exists, copy its values into
   `runner_env={...}` on the `ExamplePackage`.
7. `pip install -e .` from your new repo, then verify with
   `scripts/seed-examples --include <name>`.
8. Remove `examples/<name>/` from the Facetwork repo.
