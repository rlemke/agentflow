# Shared environment helper for AgentFlow scripts.
# Source this at the top of every script:
#   source "$(dirname "$0")/_env.sh"
#
# Loads .env (without overriding already-set vars) and exports
# _compute_compose_args which populates AFL_COMPOSE_FILES and AFL_PROFILE_ARGS.

_ENV_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load .env from project root (set only vars that are not already set)
if [ -f "$_ENV_PROJECT_DIR/.env" ]; then
    while IFS='=' read -r _key _value; do
        # Skip comments and blank lines
        [[ -z "$_key" || "$_key" == \#* ]] && continue
        # Strip leading/trailing whitespace from key
        _key="$(echo "$_key" | xargs)"
        # Only set if not already in environment
        if [ -z "${!_key+x}" ]; then
            export "$_key=$_value"
        fi
    done < "$_ENV_PROJECT_DIR/.env"
fi

# Compute compose file args and profile args from active overlay state.
# Sets: AFL_COMPOSE_FILES, AFL_PROFILE_ARGS
_compute_compose_args() {
    AFL_COMPOSE_FILES="-f docker-compose.yml"
    AFL_PROFILE_ARGS=""

    if [ "${AFL_HDFS:-false}" = true ]; then
        AFL_COMPOSE_FILES="$AFL_COMPOSE_FILES -f docker-compose.hdfs.yml"
        AFL_PROFILE_ARGS="$AFL_PROFILE_ARGS --profile hdfs"
    fi
    if [ "${AFL_POSTGIS:-false}" = true ]; then
        AFL_COMPOSE_FILES="$AFL_COMPOSE_FILES -f docker-compose.postgis.yml"
        AFL_PROFILE_ARGS="$AFL_PROFILE_ARGS --profile postgis"
    fi
    if [ "${AFL_JENKINS:-false}" = true ]; then
        AFL_PROFILE_ARGS="$AFL_PROFILE_ARGS --profile jenkins"
    fi
    if [ -n "${AFL_GEOFABRIK_MIRROR:-}" ]; then
        AFL_COMPOSE_FILES="$AFL_COMPOSE_FILES -f docker-compose.mirror.yml"
    fi
}
