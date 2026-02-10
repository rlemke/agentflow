#!/usr/bin/env python3
"""Offline test for the Volcano Query agent.

Demonstrates the full workflow execution cycle with mock handlers
(no network calls). Six-step pipeline: LoadVolcanoData (Cache → Download
→ FilterByType) → FilterByRegion → FilterByElevation → FormatVolcanoes.

Run from the repo root:

    PYTHONPATH=. python examples/volcano-query/test_volcano.py
"""

import json

from afl.runtime import Evaluator, ExecutionStatus, MemoryStore, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

# Runtime AST for:
#
#   namespace volcano {
#       event facet CheckRegionCache(region: String) => (result: VolcanoCache)
#       event facet DownloadVolcanoData(region: String, cache_path: String) => (result: VolcanoDataset)
#       event facet FilterByType(volcanoes: Json, volcano_type: String) => (result: VolcanoDataset)
#       event facet FilterByRegion(volcanoes: Json, state: String) => (result: VolcanoList)
#       event facet FilterByElevation(volcanoes: Json, min_elevation_ft: Long) => (result: VolcanoList)
#       event facet FormatVolcanoes(volcanoes: Json, count: Long) => (result: FormattedResult)
#       event facet RenderMap(volcanoes: Json, title: String) => (result: MapResult)
#
#       facet LoadVolcanoData(region: String = "US", volcano_type: String = "all")
#           => (result: VolcanoDataset) andThen {
#           cache = CheckRegionCache(region = $.region)
#           raw = DownloadVolcanoData(region = $.region, cache_path = cache.result.path)
#           typed = FilterByType(volcanoes = raw.result.volcanoes, volcano_type = $.volcano_type)
#           yield LoadVolcanoData(result = typed.result)
#       }
#   }
#
PROGRAM_AST = {
    "type": "Program",
    "declarations": [
        {
            "type": "Namespace",
            "name": "volcano",
            "declarations": [
                {
                    "type": "EventFacetDecl",
                    "name": "CheckRegionCache",
                    "params": [
                        {"name": "region", "type": "String"},
                    ],
                    "returns": [{"name": "result", "type": "VolcanoCache"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "DownloadVolcanoData",
                    "params": [
                        {"name": "region", "type": "String"},
                        {"name": "cache_path", "type": "String"},
                    ],
                    "returns": [{"name": "result", "type": "VolcanoDataset"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "FilterByType",
                    "params": [
                        {"name": "volcanoes", "type": "Json"},
                        {"name": "volcano_type", "type": "String"},
                    ],
                    "returns": [{"name": "result", "type": "VolcanoDataset"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "FilterByRegion",
                    "params": [
                        {"name": "volcanoes", "type": "Json"},
                        {"name": "state", "type": "String"},
                    ],
                    "returns": [{"name": "result", "type": "VolcanoList"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "FilterByElevation",
                    "params": [
                        {"name": "volcanoes", "type": "Json"},
                        {"name": "min_elevation_ft", "type": "Long"},
                    ],
                    "returns": [{"name": "result", "type": "VolcanoList"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "FormatVolcanoes",
                    "params": [
                        {"name": "volcanoes", "type": "Json"},
                        {"name": "count", "type": "Long"},
                    ],
                    "returns": [{"name": "result", "type": "FormattedResult"}],
                },
                {
                    "type": "EventFacetDecl",
                    "name": "RenderMap",
                    "params": [
                        {"name": "volcanoes", "type": "Json"},
                        {"name": "title", "type": "String"},
                    ],
                    "returns": [{"name": "result", "type": "MapResult"}],
                },
                {
                    "type": "FacetDecl",
                    "name": "LoadVolcanoData",
                    "params": [
                        {"name": "region", "type": "String", "default": {"type": "String", "value": "US"}},
                        {"name": "volcano_type", "type": "String", "default": {"type": "String", "value": "all"}},
                    ],
                    "returns": [{"name": "result", "type": "VolcanoDataset"}],
                    "body": {
                        "type": "AndThenBlock",
                        "steps": [
                            {
                                "type": "StepStmt",
                                "id": "step-cache",
                                "name": "cache",
                                "call": {
                                    "type": "CallExpr",
                                    "target": "CheckRegionCache",
                                    "args": [
                                        {
                                            "name": "region",
                                            "value": {"type": "InputRef", "path": ["region"]},
                                        },
                                    ],
                                },
                            },
                            {
                                "type": "StepStmt",
                                "id": "step-download",
                                "name": "raw",
                                "call": {
                                    "type": "CallExpr",
                                    "target": "DownloadVolcanoData",
                                    "args": [
                                        {
                                            "name": "region",
                                            "value": {"type": "InputRef", "path": ["region"]},
                                        },
                                        {
                                            "name": "cache_path",
                                            "value": {
                                                "type": "StepRef",
                                                "path": ["cache", "result", "path"],
                                            },
                                        },
                                    ],
                                },
                            },
                            {
                                "type": "StepStmt",
                                "id": "step-filter-type",
                                "name": "typed",
                                "call": {
                                    "type": "CallExpr",
                                    "target": "FilterByType",
                                    "args": [
                                        {
                                            "name": "volcanoes",
                                            "value": {
                                                "type": "StepRef",
                                                "path": ["raw", "result", "volcanoes"],
                                            },
                                        },
                                        {
                                            "name": "volcano_type",
                                            "value": {"type": "InputRef", "path": ["volcano_type"]},
                                        },
                                    ],
                                },
                            },
                        ],
                        "yield": {
                            "type": "YieldStmt",
                            "id": "yield-LoadVolcanoData",
                            "call": {
                                "type": "CallExpr",
                                "target": "LoadVolcanoData",
                                "args": [
                                    {
                                        "name": "result",
                                        "value": {
                                            "type": "StepRef",
                                            "path": ["typed", "result"],
                                        },
                                    },
                                ],
                            },
                        },
                    },
                },
            ],
        },
    ],
}

# Runtime AST for:
#
#   workflow FindVolcanoes(state: String, min_elevation_ft: Long) => (text: String, count: Long) andThen {
#       data = LoadVolcanoData()
#       regional = FilterByRegion(volcanoes = data.result.volcanoes, state = $.state)
#       elevated = FilterByElevation(volcanoes = regional.result.volcanoes, min_elevation_ft = $.min_elevation_ft)
#       fmt = FormatVolcanoes(volcanoes = elevated.result.volcanoes, count = elevated.result.count)
#       yield FindVolcanoes(text = fmt.result.text, count = fmt.result.count)
#   }
#
WORKFLOW_AST = {
    "type": "WorkflowDecl",
    "name": "FindVolcanoes",
    "params": [
        {"name": "state", "type": "String"},
        {"name": "min_elevation_ft", "type": "Long"},
    ],
    "returns": [
        {"name": "text", "type": "String"},
        {"name": "count", "type": "Long"},
    ],
    "body": {
        "type": "AndThenBlock",
        "steps": [
            {
                "type": "StepStmt",
                "id": "step-load",
                "name": "data",
                "call": {
                    "type": "CallExpr",
                    "target": "LoadVolcanoData",
                    "args": [],
                },
            },
            {
                "type": "StepStmt",
                "id": "step-region",
                "name": "regional",
                "call": {
                    "type": "CallExpr",
                    "target": "FilterByRegion",
                    "args": [
                        {
                            "name": "volcanoes",
                            "value": {
                                "type": "StepRef",
                                "path": ["data", "result", "volcanoes"],
                            },
                        },
                        {
                            "name": "state",
                            "value": {"type": "InputRef", "path": ["state"]},
                        },
                    ],
                },
            },
            {
                "type": "StepStmt",
                "id": "step-elevation",
                "name": "elevated",
                "call": {
                    "type": "CallExpr",
                    "target": "FilterByElevation",
                    "args": [
                        {
                            "name": "volcanoes",
                            "value": {
                                "type": "StepRef",
                                "path": ["regional", "result", "volcanoes"],
                            },
                        },
                        {
                            "name": "min_elevation_ft",
                            "value": {"type": "InputRef", "path": ["min_elevation_ft"]},
                        },
                    ],
                },
            },
            {
                "type": "StepStmt",
                "id": "step-format",
                "name": "fmt",
                "call": {
                    "type": "CallExpr",
                    "target": "FormatVolcanoes",
                    "args": [
                        {
                            "name": "volcanoes",
                            "value": {
                                "type": "StepRef",
                                "path": ["elevated", "result", "volcanoes"],
                            },
                        },
                        {
                            "name": "count",
                            "value": {
                                "type": "StepRef",
                                "path": ["elevated", "result", "count"],
                            },
                        },
                    ],
                },
            },
        ],
        "yield": {
            "type": "YieldStmt",
            "id": "yield-FindVolcanoes",
            "call": {
                "type": "CallExpr",
                "target": "FindVolcanoes",
                "args": [
                    {
                        "name": "text",
                        "value": {
                            "type": "StepRef",
                            "path": ["fmt", "result", "text"],
                        },
                    },
                    {
                        "name": "count",
                        "value": {
                            "type": "StepRef",
                            "path": ["fmt", "result", "count"],
                        },
                    },
                ],
            },
        },
    },
}


# ── Mock handlers ────────────────────────────────────────────────────

MOCK_ALL_VOLCANOES = [
    {"name": "Mount Shasta", "state": "California", "elevation_ft": 14179,
     "type": "Stratovolcano", "latitude": "41.4092", "longitude": "-122.1949"},
    {"name": "Mammoth Mountain", "state": "California", "elevation_ft": 11053,
     "type": "Lava dome", "latitude": "37.6311", "longitude": "-119.0325"},
    {"name": "Lassen Peak", "state": "California", "elevation_ft": 10457,
     "type": "Lava dome", "latitude": "40.4882", "longitude": "-121.5049"},
    {"name": "Mono Craters", "state": "California", "elevation_ft": 9172,
     "type": "Lava domes", "latitude": "37.8800", "longitude": "-119.0000"},
    {"name": "Medicine Lake", "state": "California", "elevation_ft": 7913,
     "type": "Shield volcano", "latitude": "41.6108", "longitude": "-121.5541"},
    {"name": "Clear Lake Volcanic Field", "state": "California", "elevation_ft": 4544,
     "type": "Volcanic field", "latitude": "38.9700", "longitude": "-122.7700"},
    {"name": "Mount Rainier", "state": "Washington", "elevation_ft": 14411,
     "type": "Stratovolcano", "latitude": "46.8529", "longitude": "-121.7604"},
]


def mock_cache_handler(payload: dict) -> dict:
    """Check cache for the region (always returns cached)."""
    region = payload.get("region", "US")
    return {
        "result": {
            "region": region,
            "path": f"/data/volcanoes/{region.lower()}.json",
            "cached": True,
        }
    }


def mock_download_handler(payload: dict) -> dict:
    """Return full mock dataset."""
    return {
        "result": {
            "volcanoes": json.dumps(MOCK_ALL_VOLCANOES),
        }
    }


def mock_filter_type_handler(payload: dict) -> dict:
    """Filter by volcano type (all = passthrough)."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    volcano_type = payload.get("volcano_type", "all")
    volcanoes = json.loads(volcanoes_raw) if isinstance(volcanoes_raw, str) else volcanoes_raw
    if volcano_type.lower() == "all":
        matches = volcanoes
    else:
        matches = [v for v in volcanoes if v["type"].lower() == volcano_type.lower()]
    return {
        "result": {
            "volcanoes": json.dumps(matches),
        }
    }


def mock_filter_region_handler(payload: dict) -> dict:
    """Filter by state."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    state = payload.get("state", "")
    volcanoes = json.loads(volcanoes_raw) if isinstance(volcanoes_raw, str) else volcanoes_raw
    matches = [v for v in volcanoes if v["state"].lower() == state.lower()]
    matches.sort(key=lambda v: v["elevation_ft"], reverse=True)
    return {
        "result": {
            "volcanoes": json.dumps(matches),
            "count": len(matches),
        }
    }


def mock_filter_elevation_handler(payload: dict) -> dict:
    """Filter by minimum elevation."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    min_elev = payload.get("min_elevation_ft", 0)
    volcanoes = json.loads(volcanoes_raw) if isinstance(volcanoes_raw, str) else volcanoes_raw
    matches = [v for v in volcanoes if v["elevation_ft"] >= min_elev]
    matches.sort(key=lambda v: v["elevation_ft"], reverse=True)
    return {
        "result": {
            "volcanoes": json.dumps(matches),
            "count": len(matches),
        }
    }


def mock_format_handler(payload: dict) -> dict:
    """Format volcano list into text."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    count = payload.get("count", 0)
    volcanoes = json.loads(volcanoes_raw) if isinstance(volcanoes_raw, str) else volcanoes_raw
    lines = []
    for v in volcanoes:
        lines.append(f"  {v['name']} — {v['elevation_ft']:,} ft ({v['type']})")
    text = f"Found {count} volcano(es):\n" + "\n".join(lines)
    return {
        "result": {
            "text": text,
            "count": count,
        }
    }


# ── Main test ────────────────────────────────────────────────────────


def main() -> None:
    """Run the FindVolcanoes workflow end-to-end with mock handlers."""
    store = MemoryStore()
    evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))

    poller = AgentPoller(
        persistence=store,
        evaluator=evaluator,
        config=AgentPollerConfig(service_name="test-volcano"),
    )
    poller.register("volcano.CheckRegionCache", mock_cache_handler)
    poller.register("volcano.DownloadVolcanoData", mock_download_handler)
    poller.register("volcano.FilterByType", mock_filter_type_handler)
    poller.register("volcano.FilterByRegion", mock_filter_region_handler)
    poller.register("volcano.FilterByElevation", mock_filter_elevation_handler)
    poller.register("volcano.FormatVolcanoes", mock_format_handler)

    # 1. Execute workflow — LoadVolcanoData expands its body,
    #    pauses at the CheckRegionCache event step
    print("Executing FindVolcanoes workflow...")
    result = evaluator.execute(
        WORKFLOW_AST,
        inputs={"state": "California", "min_elevation_ft": 5000},
        program_ast=PROGRAM_AST,
    )
    print(f"  Status: {result.status}")
    assert result.status == ExecutionStatus.PAUSED, "Should pause at CheckRegionCache event"

    # 2. Agent processes the CheckRegionCache event
    print("Agent processing CheckRegionCache event...")
    dispatched = poller.poll_once()
    print(f"  Dispatched: {dispatched} task(s)")
    assert dispatched == 1

    # 3. Resume — hits DownloadVolcanoData event, pauses again
    print("Resuming workflow (should pause at DownloadVolcanoData)...")
    result2 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result2.status}")
    assert result2.status == ExecutionStatus.PAUSED, "Should pause at DownloadVolcanoData event"

    # 4. Agent processes the DownloadVolcanoData event
    print("Agent processing DownloadVolcanoData event...")
    dispatched2 = poller.poll_once()
    print(f"  Dispatched: {dispatched2} task(s)")
    assert dispatched2 == 1

    # 5. Resume — hits FilterByType event, pauses again
    print("Resuming workflow (should pause at FilterByType)...")
    result3 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result3.status}")
    assert result3.status == ExecutionStatus.PAUSED, "Should pause at FilterByType event"

    # 6. Agent processes the FilterByType event
    print("Agent processing FilterByType event...")
    dispatched3 = poller.poll_once()
    print(f"  Dispatched: {dispatched3} task(s)")
    assert dispatched3 == 1

    # 7. Resume — LoadVolcanoData body completes, hits FilterByRegion event, pauses
    print("Resuming workflow (should pause at FilterByRegion)...")
    result4 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result4.status}")
    assert result4.status == ExecutionStatus.PAUSED, "Should pause at FilterByRegion event"

    # 8. Agent processes the FilterByRegion event
    print("Agent processing FilterByRegion event...")
    dispatched4 = poller.poll_once()
    print(f"  Dispatched: {dispatched4} task(s)")
    assert dispatched4 == 1

    # 9. Resume — hits FilterByElevation event, pauses again
    print("Resuming workflow (should pause at FilterByElevation)...")
    result5 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result5.status}")
    assert result5.status == ExecutionStatus.PAUSED, "Should pause at FilterByElevation event"

    # 10. Agent processes the FilterByElevation event
    print("Agent processing FilterByElevation event...")
    dispatched5 = poller.poll_once()
    print(f"  Dispatched: {dispatched5} task(s)")
    assert dispatched5 == 1

    # 11. Resume — hits FormatVolcanoes event, pauses again
    print("Resuming workflow (should pause at FormatVolcanoes)...")
    result6 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result6.status}")
    assert result6.status == ExecutionStatus.PAUSED, "Should pause at FormatVolcanoes event"

    # 12. Agent processes the FormatVolcanoes event
    print("Agent processing FormatVolcanoes event...")
    dispatched6 = poller.poll_once()
    print(f"  Dispatched: {dispatched6} task(s)")
    assert dispatched6 == 1

    # 13. Resume to completion
    print("Resuming workflow to completion...")
    final = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {final.status}")
    print(f"  Outputs: {final.outputs}")

    assert final.success
    assert final.status == ExecutionStatus.COMPLETED
    assert final.outputs["count"] == 5
    assert "Mount Shasta" in final.outputs["text"]
    assert "Lassen Peak" in final.outputs["text"]
    assert "14,179 ft" in final.outputs["text"]

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
