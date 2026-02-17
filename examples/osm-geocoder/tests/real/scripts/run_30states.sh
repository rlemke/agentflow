#!/usr/bin/env bash
# Download 30 Random US States — convenience startup script
#
# Sets up HDFS + MongoDB with external data directories under ~/data,
# starts the AgentFlow stack, compiles the workflow, and submits it.
#
# Usage:
#   examples/osm-geocoder/tests/real/scripts/run_30states.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXAMPLE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

HDFS_BASE="$HOME/data/hdfs"
MONGODB_DATA="$HOME/data/mongodb"

# ---------------------------------------------------------------------------
# 1. Create data directories
# ---------------------------------------------------------------------------
echo "=== Creating data directories ==="
mkdir -p "$HDFS_BASE/namenode" "$HDFS_BASE/datanode" "$MONGODB_DATA"
echo "  HDFS NameNode: $HDFS_BASE/namenode"
echo "  HDFS DataNode: $HDFS_BASE/datanode"
echo "  MongoDB:       $MONGODB_DATA"
echo ""

# ---------------------------------------------------------------------------
# 2. Bootstrap Docker stack via scripts/setup
# ---------------------------------------------------------------------------
echo "=== Starting AgentFlow stack ==="
"$PROJECT_DIR/scripts/setup" \
    --hdfs \
    --hdfs-namenode-dir "$HDFS_BASE/namenode" \
    --hdfs-datanode-dir "$HDFS_BASE/datanode" \
    --mongodb-data-dir "$MONGODB_DATA" \
    --osm-agents 1
echo ""

# ---------------------------------------------------------------------------
# 3. Wait for services to be ready
# ---------------------------------------------------------------------------
echo "=== Waiting for services ==="
echo "Waiting for MongoDB..."
for i in $(seq 1 30); do
    if docker compose -f "$PROJECT_DIR/docker-compose.yml" exec -T mongodb mongosh --eval "db.runCommand({ping:1})" &>/dev/null; then
        echo "  MongoDB is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  WARNING: MongoDB did not become ready in 30s — continuing anyway."
    fi
    sleep 1
done
echo ""

# ---------------------------------------------------------------------------
# 4. Compile the AFL workflow
# ---------------------------------------------------------------------------
echo "=== Compiling osmstates30.afl ==="
AFL_FILE="$REAL_DIR/afl/osmstates30.afl"
OUTPUT_FILE="$REAL_DIR/osmstates30.json"

cd "$PROJECT_DIR"
source .venv/bin/activate 2>/dev/null || true

afl --primary "$AFL_FILE" \
    --library "$EXAMPLE_DIR/afl/osmtypes.afl" \
    --library "$EXAMPLE_DIR/afl/osmoperations.afl" \
    --library "$EXAMPLE_DIR/afl/osmcache.afl" \
    -o "$OUTPUT_FILE"

echo "  Compiled to: $OUTPUT_FILE"
echo ""

# ---------------------------------------------------------------------------
# 5. Submit the workflow
# ---------------------------------------------------------------------------
echo "=== Submitting Download30States workflow ==="
python -m afl.runtime.submit "$OUTPUT_FILE" \
    --workflow "osm.geo.UnitedStates.sample.Download30States" 2>/dev/null || \
    echo "  (Submit via dashboard or MCP if the CLI submit is not available)"
echo ""

# ---------------------------------------------------------------------------
# 6. Done
# ---------------------------------------------------------------------------
echo "=== Done ==="
echo ""
echo "Access the dashboard at: http://localhost:8080"
echo ""
echo "Useful commands:"
echo "  docker compose ps              # List running services"
echo "  docker compose logs -f         # Follow logs"
echo "  docker compose down            # Stop everything"
echo ""
