#!/bin/bash
# Enable PostGIS (always) and pgRouting (only if available).
#
# The pgrouting/pgrouting image ships pgrouting; the stock
# postgis/postgis image does not. Treating pgrouting as required would
# fail the whole init on the stock image — and ON_ERROR_STOP=1 then
# aborts the rest of the init scripts in this directory, leaving the
# database half-initialized.  Run pgrouting as a best-effort follow-up.

set -e

echo "Enabling PostGIS extension in $POSTGRES_DB..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "Trying pgRouting (best effort — only present in pgrouting/pgrouting images)..."
if psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "CREATE EXTENSION IF NOT EXISTS pgrouting;" 2>/dev/null; then
    echo "  pgRouting enabled."
else
    echo "  pgRouting unavailable in this image — skipping."
fi
