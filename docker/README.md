# AgentFlow Docker Stack

This directory contains Docker configurations for running the AgentFlow development stack.

## Quick Start

```bash
# Start the core stack (MongoDB, Dashboard, Runner, AddOne Agent)
docker compose up -d

# View the dashboard
open http://localhost:8080

# Seed example workflows
docker compose --profile seed run --rm seed

# View logs
docker compose logs -f
```

## Services

### Core Services (always started)

| Service | Port | Description |
|---------|------|-------------|
| `mongodb` | 27018 | MongoDB database (27018 externally to avoid conflicts) |
| `dashboard` | 8080 | Web dashboard for monitoring workflows |
| `runner` | - | Distributed runner service |
| `agent-addone` | - | Sample agent handling AddOne/Multiply/Greet events |

### Optional Services (profiles)

#### Seed Profile
Populates the database with example workflows:

```bash
docker compose --profile seed run --rm seed
```

#### OSM Profile
Adds the OSM Geocoder agent for geographic data processing:

```bash
docker compose --profile osm up -d
```

#### MCP Profile
Runs the MCP (Model Context Protocol) server for LLM agent integration:

```bash
# MCP uses stdio transport, run interactively
docker compose --profile mcp run --rm mcp
```

## Configuration

Environment variables can be set in a `.env` file:

```env
MONGODB_PORT=27018
AFL_MONGODB_DATABASE=afl
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Dashboard │     │   Runner    │     │   Agents    │
│   (8080)    │     │   Service   │     │  (AddOne,   │
└──────┬──────┘     └──────┬──────┘     │   OSM, ...) │
       │                   │            └──────┬──────┘
       └───────────────────┴───────────────────┘
                           │
                    ┌──────┴──────┐
                    │   MongoDB   │
                    │   (27018)   │
                    └─────────────┘
```

## MCP Server Usage

The MCP (Model Context Protocol) server allows LLM agents to interact with AgentFlow.

### Starting the MCP Server

```bash
# Run interactively (stdio transport)
docker compose --profile mcp run --rm mcp
```

### Connecting from Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentflow": {
      "command": "docker",
      "args": ["compose", "-f", "/path/to/agentflow/docker-compose.yml", "--profile", "mcp", "run", "--rm", "mcp"]
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `afl_compile` | Compile AFL source to JSON |
| `afl_validate` | Validate AFL source |
| `afl_execute_workflow` | Execute a workflow |
| `afl_continue_step` | Continue a paused step |
| `afl_resume_workflow` | Resume a paused workflow |
| `afl_manage_runner` | Cancel/pause/resume runners |

### Available MCP Resources

| URI Pattern | Description |
|-------------|-------------|
| `afl://runners` | List all runners |
| `afl://runners/{id}` | Get runner details |
| `afl://runners/{id}/steps` | Get runner steps |
| `afl://runners/{id}/logs` | Get runner logs |
| `afl://steps/{id}` | Get step details |
| `afl://flows` | List all flows |
| `afl://flows/{id}` | Get flow details |
| `afl://flows/{id}/source` | Get flow AFL source |
| `afl://servers` | List all servers |
| `afl://tasks` | List all tasks |

## Troubleshooting

### MongoDB Connection Issues

If services can't connect to MongoDB:

```bash
# Check MongoDB is healthy
docker compose ps

# View MongoDB logs
docker compose logs mongodb
```

### Rebuilding Images

After code changes:

```bash
docker compose build --no-cache
docker compose up -d
```

### Clearing Data

```bash
# Stop and remove containers and volumes
docker compose down -v
```
