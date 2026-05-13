#!/usr/bin/env bash
# Entrypoint for the per-example Facetwork runner container.
#
# Required env:
#   AFL_EXAMPLE_NAME     short name (e.g. `anthropic`, `osm-geocoder`)
#   AFL_EXAMPLE_REPO     fwh_* directory name (e.g. `fwh_anthropic`)
#   AFL_MONGODB_URL      mongodb://mongodb:27017
#
# Optional env:
#   AFL_HANDLERS_ROOT    default /handlers — bind-mount root for fwh_* repos
#   AFL_EXAMPLE_EXTRAS   comma-separated pip extras
#                        (e.g. "agent_sdk,mcp" for anthropic)
#   AFL_REGISTRY_RUNNER_ARGS  extra args to forward to the registry runner

set -euo pipefail

: "${AFL_EXAMPLE_NAME:?must be set}"
: "${AFL_EXAMPLE_REPO:?must be set}"
: "${AFL_MONGODB_URL:?must be set}"

HANDLERS_ROOT="${AFL_HANDLERS_ROOT:-/handlers}"
EXAMPLE_DIR="$HANDLERS_ROOT/$AFL_EXAMPLE_REPO"

echo "==> example=$AFL_EXAMPLE_NAME repo=$AFL_EXAMPLE_REPO"
echo "    mongodb=$AFL_MONGODB_URL"
echo "    handlers=$EXAMPLE_DIR"

if [[ ! -d "$EXAMPLE_DIR" ]]; then
    echo "ERROR: $EXAMPLE_DIR not found. Bind-mount ~/fw_handlers/$AFL_EXAMPLE_REPO into the container." >&2
    exit 1
fi

# Install the example as editable so handlers stay in lockstep with
# the bind-mounted source.  Run from /tmp so the egg-info doesn't
# pollute the read-only mount if the user mounted it ro.
if [[ -n "${AFL_EXAMPLE_EXTRAS:-}" ]]; then
    echo "    pip install -e $EXAMPLE_DIR[$AFL_EXAMPLE_EXTRAS]"
    pip install --quiet --no-cache-dir -e "$EXAMPLE_DIR[$AFL_EXAMPLE_EXTRAS]"
else
    echo "    pip install -e $EXAMPLE_DIR"
    pip install --quiet --no-cache-dir -e "$EXAMPLE_DIR"
fi

# Register handler routing in MongoDB so the registry runner knows which
# facets map to this container's module/entrypoint, AND seed the example's
# FFL workflows so they appear in the dashboard's Flows tab. `--seed` is
# idempotent: re-running replaces this example's prior seed (no duplicates
# across container restarts).
echo "    Registering handlers + seeding workflows for $AFL_EXAMPLE_NAME"
python -m facetwork.examples --seed "$AFL_EXAMPLE_NAME"

# Hand off to the runner service in registry mode.
echo "    Starting runner (registry mode)"
exec python -m facetwork.runtime.runner --registry ${AFL_REGISTRY_RUNNER_ARGS:-}
