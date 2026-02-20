## Non-functional Requirements (90_nonfunctional.md)

---

## Dependencies

### Runtime Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥3.11 | Runtime |
| lark | ≥1.1.0 | Parser generator |

### Optional Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| pymongo | ≥4.0 | MongoDB connectivity |
| pyarrow | ≥14.0 | HDFS storage backend |

### Development Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| pytest | ≥7.0 | Test framework |
| pytest-cov | ≥4.0 | Coverage reporting |

### Forbidden Dependencies
No other parsing, compiler, or DSL libraries are permitted in v1:
- ❌ ANTLR
- ❌ PLY
- ❌ Parsimonious
- ❌ pyparsing
- ❌ regex-based parsers
- ❌ handwritten parsers

---

## Performance

### Parser Performance
- Grammar uses LALR mode (linear time parsing)
- No backtracking required
- Single-pass parsing

### Memory
- AST nodes use dataclasses (memory efficient)
- No caching of intermediate results
- Parse tree discarded after transformation

---

## Compatibility

### Python Version
- Minimum: Python 3.11
- Tested: Python 3.14
- Uses: dataclasses, type hints, `kw_only` parameter

### Platform
- OS-independent (pure Python)
- No native extensions
- No system dependencies

---

## Code Quality

### Style
- Type hints on all public functions
- Docstrings on all public classes and functions
- No global mutable state

### Testing
- 302 tests total (including 26 MongoDB persistence tests via mongomock)
- 81% code coverage
- Tests for all grammar constructs
- Tests for error reporting
- MongoDB store tests using mongomock (no real database required)

### Documentation
- README with usage examples
- Spec files for language definition
- CLAUDE.md for development guidance

---

## Security

### Input Handling
- All input treated as untrusted
- No eval() or exec() usage
- No file system access beyond reading input

### Error Messages
- No sensitive data in error messages
- Line/column info only (no source excerpts in errors)

---

## Versioning

### Current Version
- `0.1.0` (initial implementation)

### Semantic Versioning
- MAJOR: Breaking changes to AST structure or JSON format
- MINOR: New language features, new AST nodes
- PATCH: Bug fixes, performance improvements

### JSON Format Stability
- JSON output format is considered stable within MAJOR version
- `type` field present on all nodes
- Location fields optional (controlled by flag)
- As of v0.12.52, the emitter produces **declarations-only** format (no categorized `namespaces`/`facets`/`eventFacets`/`workflows`/`implicits`/`schemas` keys)
- `normalize_program_ast()` in `afl/ast_utils.py` handles backward compatibility for legacy JSON that uses categorized keys

---

## Build & Run Reference

### Setup virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"                           # dev only
pip install -e ".[dev,test,dashboard,mcp,mongodb]" # full stack
```

### CLI usage
```bash
afl input.afl -o output.json       # compile to JSON
echo 'facet Test()' | afl          # parse from stdin
afl input.afl --check              # syntax check only
afl input.afl --config config.json # custom config
```

### Services
```bash
python -m afl.dashboard                              # dashboard (port 8080)
python -m afl.dashboard --port 9000 --reload         # dev mode
python -m afl.runtime.runner                         # runner service
python -m afl.runtime.runner --topics TopicA TopicB  # filtered topics
python -m afl.runtime.runner --max-concurrent 10     # increase concurrency
python -m afl.mcp                                    # MCP server (stdio)
```

### Scala agent library
```bash
cd agents/scala/afl-agent && sbt compile  # compile
cd agents/scala/afl-agent && sbt test     # run tests
cd agents/scala/afl-agent && sbt package  # package JAR
```

### Convenience scripts
All scripts are in `scripts/` and are self-contained:
```bash
scripts/_env.sh                                # shared env loader (sourced by other scripts)
scripts/easy.sh                                # one-command pipeline (teardown → rebuild → setup → seed)
scripts/setup                                  # bootstrap Docker stack
scripts/setup --runners 3 --agents 2           # start with scaling
scripts/compile input.afl -o output.json       # compile AFL
scripts/publish input.afl                      # compile + publish to MongoDB
scripts/publish input.afl --auto-resolve       # with dependency resolution
scripts/run-workflow                           # interactive workflow execution
scripts/run-workflow --workflow Name            # run specific workflow
scripts/server --workflow MyWorkflow           # execute workflow (server mode)
scripts/runner                                 # start runner
scripts/dashboard                              # start dashboard
scripts/mcp-server                             # start MCP server
scripts/db-stats                               # show DB statistics
```

### Docker stack
The `docker-compose.yml` defines the full development stack:
```bash
scripts/setup                                               # bootstrap
scripts/setup --runners 3 --agents 2 --osm-agents 1        # with scaling
docker compose up -d                                        # start directly
docker compose --profile seed run --rm seed                 # seed workflows
docker compose --profile mcp run --rm mcp                   # MCP server
docker compose --profile hdfs up -d                         # start HDFS
scripts/setup --hdfs                                        # bootstrap with HDFS
docker compose down                                         # stop
docker compose down -v                                      # stop + remove volumes
```

#### Services

| Service | Port | Scalable | Description |
|---------|------|----------|-------------|
| `mongodb` | 27018 | No | MongoDB 7 database |
| `dashboard` | 8080 | No | Web dashboard |
| `runner` | - | Yes | Distributed runner service |
| `agent-addone` | - | Yes | Sample AddOne agent |
| `agent-osm-geocoder` | - | Yes | Full OSM agent (osmium, Java, GraphHopper) |
| `agent-osm-geocoder-lite` | - | Yes | Lightweight OSM agent (requests only) |
| `seed` | - | No | One-shot workflow seeder (profile: seed) |
| `mcp` | - | No | MCP server, stdio transport (profile: mcp) |
| `namenode` | 9870, 8020 | No | HDFS NameNode (profile: hdfs) |
| `datanode` | - | No | HDFS DataNode (profile: hdfs) |

#### Setup script options

| Option | Default | Description |
|--------|---------|-------------|
| `--runners N` | 1 | Runner service instances |
| `--agents N` | 1 | AddOne agent instances |
| `--osm-agents N` | 0 | Full OSM Geocoder agent instances |
| `--osm-lite-agents N` | 0 | Lightweight OSM agent instances |
| `--hdfs` | - | Start HDFS namenode + datanode services |
| `--build` | - | Force image rebuild before starting |
| `--check-only` | - | Verify Docker availability, then exit |

### Environment Configuration

The `.env` file is the primary way to configure the Docker stack and convenience scripts.

**Setup:**
```bash
cp .env.example .env   # one-time copy
# Edit .env to set MongoDB port, scaling, overlays, data directories
scripts/easy.sh        # runs the full pipeline using .env values
```

**How it works:**
- `scripts/_env.sh` is sourced by every convenience script. It reads `.env` from the project root and exports each variable **only if it is not already set** in the environment.
- `scripts/easy.sh` translates `.env` variables into `scripts/setup` CLI flags and runs the full pipeline (teardown → rebuild → setup → seed).
- Precedence: **CLI flags > env vars > `.env` > defaults**

**Variable reference:**

| Variable | Default | Description |
|----------|---------|-------------|
| **MongoDB** | | |
| `MONGODB_PORT` | `27018` | Host port for MongoDB container |
| `AFL_MONGODB_URL` | `mongodb://localhost:27018` | MongoDB connection URL |
| `AFL_MONGODB_DATABASE` | `afl` | Database name |
| `MONGODB_DATA_DIR` | *(Docker volume)* | Host path for MongoDB data |
| **Scaling** | | |
| `AFL_RUNNERS` | `1` | Number of runner service instances |
| `AFL_AGENTS` | `1` | Number of AddOne agent instances |
| `AFL_OSM_AGENTS` | `0` | Full OSM Geocoder agent instances |
| `AFL_OSM_LITE_AGENTS` | `0` | Lightweight OSM agent instances |
| **Overlays** | | |
| `AFL_HDFS` | `false` | Enable HDFS overlay compose file and profile |
| `AFL_POSTGIS` | `false` | Enable PostGIS overlay compose file and profile |
| `AFL_JENKINS` | `false` | Enable Jenkins profile |
| `AFL_GEOFABRIK_MIRROR` | *(empty)* | Path to local Geofabrik mirror; enables mirror overlay |
| **Data directories** | | |
| `HDFS_NAMENODE_DIR` | *(Docker volume)* | Host path for HDFS NameNode data |
| `HDFS_DATANODE_DIR` | *(Docker volume)* | Host path for HDFS DataNode data |
| `GRAPHHOPPER_DATA_DIR` | *(Docker volume)* | Host path for GraphHopper data |
| `POSTGIS_DATA_DIR` | *(Docker volume)* | Host path for PostGIS data |
| `JENKINS_HOME_DIR` | *(Docker volume)* | Host path for Jenkins home |

### Configuration

AFL uses a JSON config file (`afl.config.json`) for service connections. Resolution order:

1. Explicit `--config FILE` CLI argument
2. `AFL_CONFIG` environment variable
3. `afl.config.json` in the current directory, `~/.afl/`, or `/etc/afl/`
4. Environment variables (`AFL_MONGODB_*`)
5. Built-in defaults

**Example configuration:**
```json
{
  "mongodb": {
    "url": "mongodb://localhost:27017",
    "username": "",
    "password": "",
    "authSource": "admin",
    "database": "afl"
  }
}
```

**Environment variables:**
| Variable | Default |
|----------|---------|
| `AFL_MONGODB_URL` | `mongodb://localhost:27017` |
| `AFL_MONGODB_USERNAME` | (empty) |
| `AFL_MONGODB_PASSWORD` | (empty) |
| `AFL_MONGODB_AUTH_SOURCE` | `admin` |
| `AFL_MONGODB_DATABASE` | `afl` |
