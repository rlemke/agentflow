# Volcano Query Agent

A volcano data agent that finds US volcanoes by state and elevation using a built-in dataset of ~30 notable volcanoes (sourced from USGS data). No external API calls required.

## Design principle: atomic event facets

Each event facet does **one thing**. Workflows compose atomic facets into pipelines. An LLM agent sees the facet catalog (signatures) and can compose new workflows from the same building blocks — rather than creating monolithic "do everything" handlers.

**5 atomic event facets:**

| Facet | Input | Output | Purpose |
|-------|-------|--------|---------|
| `LoadVolcanoData()` | — | `VolcanoDataset` | Load the raw dataset |
| `FilterByRegion(volcanoes, state)` | JSON + state name | `VolcanoList` | Filter by US state |
| `FilterByElevation(volcanoes, min_elevation_ft)` | JSON + threshold | `VolcanoList` | Filter by min height |
| `FormatVolcanoes(volcanoes, count)` | JSON + count | `FormattedResult` | Format as text |
| `RenderMap(volcanoes, title)` | JSON + title | `MapResult` | Generate HTML map |

**3 composed workflows:**

| Workflow | Pipeline | Description |
|----------|----------|-------------|
| `FindVolcanoes` | Load → Region → Elevation → Format | Basic query pipeline |
| `FindVolcanoesWithMap` | Load → Region → Elevation → Format + Map | Adds map visualization |
| `FindVolcanoesMultiState` | foreach state: Load → Region → Elevation → Format | Parallel multi-state query |

## What it demonstrates

- **Atomic event facets** — each handler does one operation on the data
- **Pipeline composition** — workflows chain facets via `andThen` blocks
- **Parallel steps** — `FindVolcanoesWithMap` runs Format and RenderMap concurrently
- **Foreach iteration** — `FindVolcanoesMultiState` iterates over states in parallel
- **Schema typing** — `VolcanoDataset`, `VolcanoList`, `FormattedResult`, `MapResult`
- **Built-in dataset** — self-contained with no external API calls

### AFL Workflow

```afl
namespace volcano {

    schema VolcanoDataset { volcanoes: Json }
    schema VolcanoList { volcanoes: Json, count: Long }
    schema FormattedResult { text: String, count: Long }
    schema MapResult { html: String, title: String }

    event facet LoadVolcanoData() => (result: VolcanoDataset)
    event facet FilterByRegion(volcanoes: Json, state: String) => (result: VolcanoList)
    event facet FilterByElevation(volcanoes: Json, min_elevation_ft: Long) => (result: VolcanoList)
    event facet FormatVolcanoes(volcanoes: Json, count: Long) => (result: FormattedResult)
    event facet RenderMap(volcanoes: Json, title: String) => (result: MapResult)

    workflow FindVolcanoes(state: String, min_elevation_ft: Long) => (text: String, count: Long) andThen {
        data = LoadVolcanoData()
        regional = FilterByRegion(volcanoes = data.result.volcanoes, state = $.state)
        elevated = FilterByElevation(volcanoes = regional.result.volcanoes, min_elevation_ft = $.min_elevation_ft)
        fmt = FormatVolcanoes(volcanoes = elevated.result.volcanoes, count = elevated.result.count)
        yield FindVolcanoes(text = fmt.result.text, count = fmt.result.count)
    }
}
```

### Execution flow (FindVolcanoes)

1. Workflow receives `state` and `min_elevation_ft` inputs
2. `LoadVolcanoData` event pauses → agent returns the full dataset
3. `FilterByRegion` event pauses → agent filters by state
4. `FilterByElevation` event pauses → agent filters by min elevation
5. `FormatVolcanoes` event pauses → agent formats results as text
6. Workflow yields formatted text and count as output

## Prerequisites

```bash
# From the repo root
source .venv/bin/activate
```

No additional dependencies beyond core `afl` are needed.

## Running

### Offline test (no network, mock handlers)

```bash
PYTHONPATH=. python examples/volcano-query/test_volcano.py
```

Expected output:
```
Executing FindVolcanoes workflow...
  Status: ExecutionStatus.PAUSED
Agent processing LoadVolcanoData event...
  Dispatched: 1 task(s)
Resuming workflow (should pause at FilterByRegion)...
  Status: ExecutionStatus.PAUSED
Agent processing FilterByRegion event...
  Dispatched: 1 task(s)
Resuming workflow (should pause at FilterByElevation)...
  Status: ExecutionStatus.PAUSED
Agent processing FilterByElevation event...
  Dispatched: 1 task(s)
Resuming workflow (should pause at FormatVolcanoes)...
  Status: ExecutionStatus.PAUSED
Agent processing FormatVolcanoes event...
  Dispatched: 1 task(s)
Resuming workflow to completion...
  Status: ExecutionStatus.COMPLETED
  Outputs: {'text': 'Found 5 volcano(es):\n  Mount Shasta — 14,179 ft ...', 'count': 5}

All assertions passed.
```

### Live agent

```bash
PYTHONPATH=. python examples/volcano-query/agent.py
```

This starts a long-running agent that polls for all 5 volcano event facet tasks. In production, pair it with a runner service that executes workflows.

### Compile check

```bash
afl examples/volcano-query/afl/volcano.afl --check
```

## Handler modules

| Module | Event facets | Description |
|--------|-------------|-------------|
| `volcano_handlers.py` | 5 | Load, filter, format, and map volcano data from built-in dataset |
| `__init__.py` | — | `register_all_handlers(poller)` convenience function |

## Built-in dataset

The agent includes ~30 notable US volcanoes across 7 states:

| State | Volcanoes | Notable peaks |
|-------|-----------|---------------|
| California | 6 | Mount Shasta (14,179 ft), Mammoth Mountain, Lassen Peak |
| Washington | 5 | Mount Rainier (14,411 ft), Mount St. Helens, Mount Adams |
| Oregon | 6 | Mount Hood (11,249 ft), Crater Lake, South Sister |
| Hawaii | 5 | Mauna Kea (13,796 ft), Mauna Loa, Kilauea |
| Alaska | 5 | Mount Wrangell (14,163 ft), Mount Spurr, Mount Redoubt |
| Wyoming | 1 | Yellowstone Caldera (9,203 ft) |
| New Mexico | 1 | Valles Caldera (11,254 ft) |

## Example query

"Display all volcanoes over 5,000 ft in California" returns:

```
Found 5 volcano(es):
  Mount Shasta — 14,179 ft (Stratovolcano, 41.4092N -122.1949W)
  Mammoth Mountain — 11,053 ft (Lava dome, 37.6311N -119.0325W)
  Lassen Peak — 10,457 ft (Lava dome, 40.4882N -121.5049W)
  Mono Craters — 9,172 ft (Lava domes, 37.8800N -119.0000W)
  Medicine Lake — 7,913 ft (Shield volcano, 41.6108N -121.5541W)
```
