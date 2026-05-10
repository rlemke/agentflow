# Continental LZ Pipeline

FFL workflows that orchestrate the OpenStreetMap **Low-Zoom (LZ) road
infrastructure** pipeline and GTFS transit analysis across continental regions
(US, Canada, Europe).

This example is **FFL-only** — it provides the workflow definitions but
relies on the standalone [osm-geocoder](https://github.com/rlemke/fwh_osm)
package for the underlying handlers (region cache, OSM downloads,
GraphHopper graph builds, GTFS extraction, population filters, zoom
builders).

## Regions

| Region | PBF Size | GH Graph | LZ Time (est.) |
|--------|----------|----------|-----------------|
| United States | ~9 GB | ~15 GB | 4-8 hrs |
| Canada | ~3 GB | ~5 GB | 1-3 hrs |
| Germany | ~3.8 GB | ~6 GB | 2-4 hrs |
| France | ~3.8 GB | ~6 GB | 2-4 hrs |
| UK | ~1.3 GB | ~2 GB | 1-2 hrs |
| Spain | ~1.0 GB | ~1.5 GB | 1-2 hrs |
| Italy | ~1.5 GB | ~2.5 GB | 1-2 hrs |
| Poland | ~1.2 GB | ~2 GB | 1-2 hrs |
| Netherlands | ~1.1 GB | ~1.5 GB | 30-60 min |
| Belgium | ~0.4 GB | ~0.5 GB | 15-30 min |
| Switzerland | ~0.4 GB | ~0.5 GB | 15-30 min |
| Austria | ~0.5 GB | ~0.7 GB | 20-40 min |
| Sweden | ~0.8 GB | ~1.2 GB | 30-60 min |
| Norway | ~0.6 GB | ~0.9 GB | 20-40 min |
| **Total** | **~28 GB** | **~44 GB** | **12-30 hrs** |

## GTFS Transit Agencies (11)

**US**: Amtrak, MBTA (Boston), CTA (Chicago), MTA (NYC Subway)
**Canada**: TransLink (Vancouver), TTC (Toronto), OC Transpo (Ottawa)
**Europe**: Deutsche Bahn, SNCF (France), Renfe (Spain), Trenitalia

## Setup

Install the osm-geocoder package so its handlers register with the runner:

```bash
git clone https://github.com/rlemke/fwh_osm.git ~/fw_handlers/fwh_osm
pip install -e ~/fw_handlers/fwh_osm
```

Then seed both flows and start the runner:

```bash
scripts/seed-examples --include "^(continental-lz|osm-geocoder)$"
scripts/start-runner --example osm-geocoder -- --log-format text
```

Continental-lz workflows reference osm namespaces (`osm.cache.<continent>.<country>`,
`osm.cache.GraphHopper.<continent>.<country>`, `osm.Roads.ZoomBuilder.*`,
`osm.Transit.GTFS.*`) — the osm-geocoder package supplies those handlers
so the workflows execute end-to-end.

## Workflows

| Workflow | Purpose |
|----------|---------|
| `FullContinentalPipeline` | Bundle: LZ road infra + GTFS transit |
| `BuildContinentalLZ` | LZ pipeline across all 14 regions |
| `ContinentalTransitAnalysis` | GTFS feeds + transit stats for 11 agencies |

Run from the dashboard at http://localhost:8080 or via
`scripts/run-workflow continental.lz.FullContinentalPipeline`.

## Layout

```
continental-lz/
├── ffl/
│   ├── continental_types.ffl
│   ├── continental_lz_workflows.ffl
│   ├── continental_gtfs_workflows.ffl
│   └── continental_full.ffl
├── README.md
└── USER_GUIDE.md
```

No Python handlers or scripts — those live in the osm-geocoder package.
