# NOAA Weather Station Analysis — User Guide

> See also: [Examples Guide](../doc/GUIDE.md) | [README](../README.md)

## When to Use This Example

Use this as your starting point if you are:
- Building **real HTTP data pipelines** that download, parse, and analyze external data
- Using **prompt blocks with graceful LLM fallback** (works with or without `ANTHROPIC_API_KEY`)
- Learning **andThen when** (conditional branching), **catch** (error recovery), and **andThen foreach** (batch processing)
- Combining **script blocks** (inline QC) with **prompt blocks** (LLM narrative) in the same workflow
- Using **RegistryRunner** with per-namespace handler modules

## What You'll Learn

1. How NOAA ISD-Lite hourly data is downloaded and parsed via real HTTP calls
2. How `andThen when` branches on QC pass/fail (sparse vs. full analysis)
3. How `catch` blocks recover from download failures without aborting the workflow
4. How `andThen foreach` fans out across stations or years for batch processing
5. How a `prompt` block drives LLM narrative generation with deterministic fallback
6. How OSM Nominatim reverse geocoding enriches station data with location context
7. How `TokenUsage` and `token_budget` track and limit Claude API costs

## Step-by-Step Walkthrough

### 1. The Problem

Given a NOAA weather station ID and year, download hourly observations, validate data quality, compute daily statistics, generate a meteorologist-style narrative, and produce an HTML report with a map. Handle download failures gracefully and branch on QC results.

### 2. Schemas — Typed Data Structures

Six schemas in `weather.types` define the data flowing between steps:

| Schema | Purpose |
|--------|---------|
| `StationMeta` | Station identity, location, elevation, date range |
| `HourlyObs` | Single hourly observation (temp, wind, precip, sky) |
| `QCResult` | Quality check output (plausible flag, missing %, message) |
| `DailyStats` | Aggregated daily statistics (temp min/max/mean, precip, wind) |
| `GeoContext` | Reverse geocode result (city, state, country, county) |
| `StationReport` | Final report combining all analysis results |

### 3. Event Facets — The Processing Steps

Ten event facets across seven namespaces:

| Namespace | Event Facet | Mechanism |
|-----------|-------------|-----------|
| `weather.Discovery` | `DiscoverStations` | Real HTTP (NOAA station inventory) |
| `weather.Ingest` | `DownloadObservations` | Real HTTP (ISD-Lite FTP/HTTPS) |
| `weather.Ingest` | `ParseObservations` | Fixed-width file parser |
| `weather.QC` | `ValidateQuality` | **Script block** — inline Python QC |
| `weather.Analysis` | `ComputeDailyStats` | Aggregation handler |
| `weather.Analysis` | `SparseAnalysis` | Lightweight fallback for poor data |
| `weather.Geocode` | `ReverseGeocode` | Real HTTP (OSM Nominatim) |
| `weather.Interpret` | `GenerateNarrative` | **Prompt block** — Claude API with fallback |
| `weather.Report` | `GenerateStationReport` | JSON report builder |
| `weather.Report` | `GenerateBatchSummary` | Batch summary across stations |
| `weather.Visualize` | `RenderHTMLReport` | HTML table report |
| `weather.Visualize` | `RenderStationMap` | Interactive folium map |

### 4. The AnalyzeStation Pipeline

The main workflow has three sequential `andThen` blocks:

**Block 1 — Download with error recovery:**
```afl
dl = DownloadObservations(usaf = $.usaf, wban = $.wban, year = $.year) catch {
    yield AnalyzeStation(status = "download_failed", detail = "Download failed for " ++ $.usaf ++ "-" ++ $.wban)
}
```
If the download fails, the `catch` block yields immediately with an error status instead of aborting.

**Block 2 — Parse, geocode, and QC (concurrent):**
```afl
parsed = ParseObservations(raw_path = dl.raw_path, station_id = dl.station_id)
geo = ReverseGeocode(lat = $.lat, lon = $.lon)
qc_check = ValidateQuality(observations = parsed.observations, station_id = dl.station_id)
```
Three independent steps execute concurrently. `ValidateQuality` uses a script block for inline Python QC.

**Block 3 — Conditional branching:**
```afl
andThen when {
    case qc_check.qc.plausible == false => {
        sparse = SparseAnalysis(...)
        yield AnalyzeStation(status = "sparse", detail = "Sparse analysis: " ++ sparse.summary)
    }
    case _ => {
        stats = ComputeDailyStats(...)
        narr = GenerateNarrative(station_name = $.station_name, year = $.year,
            daily_stats = stats.daily_stats,
            geo_context = #{"city": geo.geo.city, "state": geo.geo.state, "country": geo.geo.country})
        report = GenerateStationReport(...)
        html_report = RenderHTMLReport(...)
        station_map = RenderStationMap(...)
        yield AnalyzeStation(status = "completed", detail = "Report: " ++ report.report.report_id)
    }
}
```
If QC fails, a lightweight sparse analysis runs. Otherwise, the full pipeline executes: daily stats, narrative, report, HTML, and map.

### 5. Batch and Multi-Year Workflows

| Workflow | Purpose |
|----------|---------|
| `AnalyzeKnownStation` | Convenience wrapper — skip discovery, analyze one station directly |
| `BatchWeatherAnalysis` | Discover stations, then `andThen foreach` with per-station `catch` |
| `AnalyzeStationHistory` | One station across multiple years via `andThen foreach year in $.years` |
| `AnalyzeRegion` | Region across years — `foreach year` calling `BatchWeatherAnalysis` |

## LLM Integration — GenerateNarrative

### The AFL Prompt Block

```afl
event facet GenerateNarrative(station_name: String, year: Int, daily_stats: Json, geo_context: Json)
    => (narrative: String, highlights: Json) prompt {
    system "You are a meteorologist writing a concise annual weather summary for a station."
    template "Write a narrative summary for {station_name} in {year}. Daily statistics: {daily_stats}. Location context: {geo_context}. Highlight extremes (hottest day, coldest day, wettest day) and seasonal patterns."
    model "claude-sonnet-4-20250514"
}
```

The `prompt` block declares the LLM behavior declaratively in AFL. The runtime or handler uses these fields to construct the Claude API call.

### ANTHROPIC_API_KEY

Set the `ANTHROPIC_API_KEY` environment variable to enable live Claude API calls:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

When unset, the handler falls back to a deterministic narrative — tests and CI run without API access.

### Handler Fallback Pattern

The handler (`handlers/interpret/interpret_handlers.py`) implements a three-tier strategy:

```python
HAS_ANTHROPIC = False
try:
    import anthropic
    HAS_ANTHROPIC = bool(os.environ.get("ANTHROPIC_API_KEY"))
except ImportError:
    pass

def handle_generate_narrative(params):
    if HAS_ANTHROPIC:
        try:
            narrative, highlights = _generate_with_claude(...)
        except Exception:
            narrative, highlights = generate_narrative_fallback(...)
    else:
        narrative, highlights = generate_narrative_fallback(...)
    return {"narrative": narrative, "highlights": highlights}
```

1. **API key set + anthropic installed**: call Claude, parse JSON response
2. **Claude call fails**: fall back to deterministic narrative
3. **No API key or no anthropic package**: use deterministic narrative directly

### Example Claude Output (JFK Airport, 2023)

When run with a live API key, Claude generates prose like:

> *JFK International Airport experienced a year of notable weather contrasts in 2023.
> Temperatures ranged from a bone-chilling -10.2°C in late January to a sweltering 35.6°C
> during a mid-July heat wave. The station recorded 127 rainy days totaling 1,142mm of
> precipitation, with the wettest single day dropping 62mm during a nor'easter in October.
> Spring arrived gradually with temperatures climbing through March and April, while autumn
> brought an extended warm spell before winter set in during December.*

## Running on the Dashboard

### 1. Seed and start the runner

```bash
# From repo root
source .venv/bin/activate

# Seed the NOAA weather workflows into MongoDB
scripts/publish examples/noaa-weather/afl/weather.afl

# Register handlers and start runner + dashboard
scripts/start-runner --example noaa-weather -- --log-format text
```

### 2. Submit a workflow

Open `http://localhost:8080` in a browser. Navigate to the NOAA weather flow, select `AnalyzeKnownStation`, and submit with inputs:

```json
{
    "usaf": "744860",
    "wban": "94789",
    "station_name": "JFK INTERNATIONAL AIRPORT",
    "lat": 40.6386,
    "lon": -73.7622,
    "year": 2023
}
```

Or via curl:

```bash
# Find the flow ID
FLOW_ID=$(python3 -c "
from afl.runtime.mongo_store import MongoStore
store = MongoStore('mongodb://localhost:27018')
for f in store.get_flows():
    if 'noaa' in f.name.lower() or 'weather' in f.name.lower():
        print(f.uuid); break
")

# Submit
curl -X POST "http://localhost:8080/flows/$FLOW_ID/run/AnalyzeKnownStation" \
  -d 'inputs_json={"usaf":"744860","wban":"94789","station_name":"JFK INTERNATIONAL AIRPORT","lat":40.6386,"lon":-73.7622,"year":2023}'
```

### 3. Monitor progress

The dashboard shows each step progressing through states: `Created → Ready → Running → Completed`. The full pipeline (download → parse → QC → stats → narrative → report → HTML → map) completes in ~30 seconds with real HTTP calls.

## Token Usage Tracking

`ClaudeAgentRunner` and `LLMHandler` track cumulative token usage via the `TokenUsage` dataclass:

```python
from afl.runtime.agent import ClaudeAgentRunner, TokenUsage

runner = ClaudeAgentRunner(
    evaluator=evaluator,
    persistence=store,
    token_budget=50000,  # optional limit
)
result = runner.run(workflow_ast, inputs={...}, program_ast=program_ast)
print(result.token_usage.to_dict())
# {"input_tokens": 1234, "output_tokens": 567, "total_tokens": 1801, "api_calls": 1}
```

When `token_budget` is set and total tokens exceed it, a `TokenBudgetExceededError` is raised:

```python
from afl.runtime.errors import TokenBudgetExceededError

try:
    result = runner.run(workflow_ast, inputs={...}, program_ast=program_ast)
except TokenBudgetExceededError as e:
    print(e)  # "Token budget exceeded at step ...: used 50123 of 50000 tokens"
```

## Key Concepts

### Prompt Block Fallback Pattern
Every prompt-block handler should detect `ANTHROPIC_API_KEY` at import time and fall back to deterministic output when the key is missing. This keeps tests fast and CI independent of API access.

### Script Block for Inline QC
`ValidateQuality` uses `script python "..."` to run QC logic inline — no handler module needed. The code receives `params` and writes to `result`.

### Catch for Error Recovery
Download failures don't abort the workflow — the `catch` block yields an error status, allowing batch workflows to continue processing other stations.

### Map Literals for Structured Data
Geo context is passed as a map literal: `#{"city": geo.geo.city, "state": geo.geo.state, "country": geo.geo.country}`.

### String Concatenation
The `++` operator builds station IDs and detail messages: `$.usaf ++ "-" ++ $.wban`.

## Adapting for Your Use Case

### Add a new prompt-block facet

1. Define the event facet with a `prompt` block in AFL:
```afl
event facet SummarizeRegion(region: String, stations: Json) => (summary: String) prompt {
    system "You are a regional climate analyst."
    template "Summarize weather patterns for {region} based on station data: {stations}"
    model "claude-sonnet-4-20250514"
}
```

2. Write a handler with the fallback pattern:
```python
HAS_ANTHROPIC = bool(os.environ.get("ANTHROPIC_API_KEY"))

def handle_summarize_region(params):
    if HAS_ANTHROPIC:
        # Call Claude API
        ...
    else:
        # Deterministic fallback
        return {"summary": f"Region summary for {params['region']}"}
```

### Use different weather data sources

Replace `DownloadObservations` and `ParseObservations` handlers with your data source (ERA5, local CSV, etc.) while keeping the same AFL workflow structure.

### Add multi-year trend analysis

Use `AnalyzeStationHistory` or `AnalyzeRegion` to process multiple years, then add a new facet that compares results across years.

## Next Steps

- **[hiv-drug-resistance](../hiv-drug-resistance/)** — bioinformatics pipeline with similar patterns (catch, when, foreach, prompt, script)
- **[research-agent](../research-agent/USER_GUIDE.md)** — full LLM pipeline with ClaudeAgentRunner
- **[devops-deploy](../devops-deploy/)** — first `andThen when` showcase with nested conditions
