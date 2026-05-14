#!/usr/bin/env bash
# Entrypoint for the "main" Facetwork runner container — the one that
# hosts the bundled in-repo examples (save_earth, multi-agent-debate,
# research-agent, etc.).
#
# Per-example runners get one Python package per container (bind-mounted
# at /handlers/fwh_<name>) and seed exactly that package. The main runner
# is the dual: it has every in-repo example mounted at /app/examples and
# seeds all of them in one pass, then drops into --registry mode so the
# claim loop only advertises facets whose handler modules verify-load.
#
# Without this step the main runner registers only the built-in fw:execute
# handler, which is enough to claim bootstrap tasks but not to dispatch
# the child event facets they create — those pile up pending on the
# default list with no listener.
#
# Required env:
#   AFL_MONGODB_URL      mongodb://mongodb:27017
#
# Optional env:
#   AFL_REGISTRY_RUNNER_ARGS  extra args forwarded to the runner (e.g. --task-list X)

set -euo pipefail

: "${AFL_MONGODB_URL:?must be set}"

# Make sure /app/examples is on the import path so register_handlers'
# `file://` URIs resolve. The runner image's WORKDIR is /app and the
# in-repo examples are bind-mounted there at runtime by compose.
export REPO_ROOT="/app"

echo "==> main runner — seeding in-repo examples"
echo "    mongodb=$AFL_MONGODB_URL"
echo "    examples=/app/examples"

python -m facetwork.examples --seed

echo "    Starting runner (registry mode)"
exec python -m facetwork.runtime.runner --registry ${AFL_REGISTRY_RUNNER_ARGS:-}
