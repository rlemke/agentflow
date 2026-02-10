# Volcano Query Agent

A volcano data agent that finds US volcanoes by state and elevation using a built-in dataset of ~30 notable volcanoes (sourced from USGS data). No external API calls required.

## What it does

This example demonstrates:
- **Schema declarations** for typed data structures (`Volcano`, `VolcanoList`, `FormattedResult`)
- **Event facets** for external agent dispatch (`QueryVolcanoes`, `FormatVolcanoes`)
- **Multi-step workflows** chaining query → format in a single `andThen` block
- **Foreach iteration** for querying multiple states in parallel (`FindVolcanoesMultiState`)
- **Built-in dataset** — self-contained with no external API calls

### AFL Workflow

```afl
namespace volcano {

    schema Volcano {
        name: String, state: String, elevation_ft: Long,
        type: String, latitude: String, longitude: String
    }

    schema VolcanoList { volcanoes: Json, count: Long }
    schema FormattedResult { text: String, count: Long }

    event facet QueryVolcanoes(state: String, min_elevation_ft: Long) => (result: VolcanoList)
    event facet FormatVolcanoes(volcanoes: Json, count: Long) => (result: FormattedResult)

    workflow FindVolcanoes(state: String, min_elevation_ft: Long) => (text: String, count: Long) andThen {
        query = QueryVolcanoes(state = $.state, min_elevation_ft = $.min_elevation_ft)
        fmt = FormatVolcanoes(volcanoes = query.result.volcanoes, count = query.result.count)
        yield FindVolcanoes(text = fmt.result.text, count = fmt.result.count)
    }
}
```

### Execution flow

1. `FindVolcanoes` workflow receives a state name and minimum elevation
2. The `QueryVolcanoes` event step pauses execution and creates a task
3. The agent picks up the task, filters the built-in dataset, writes the result
4. The workflow resumes and hits the `FormatVolcanoes` event step, pausing again
5. The agent formats the results into human-readable text
6. The workflow resumes and yields the formatted text and count as output

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
Agent processing QueryVolcanoes event...
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

This starts a long-running agent that polls for `volcano.QueryVolcanoes` and `volcano.FormatVolcanoes` tasks. In production, pair it with a runner service that executes workflows.

### Compile check

```bash
afl examples/volcano-query/afl/volcano.afl --check
```

## Handler modules

| Module | Event facets | Description |
|--------|-------------|-------------|
| `volcano_handlers.py` | 2 | Query and format volcano data from built-in dataset |
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
