#!/usr/bin/env python3
"""Offline test for the Volcano Query agent.

Demonstrates the full workflow execution cycle with mock handlers
(no network calls). Four-step pipeline: LoadVolcanoData → FilterByRegion
→ FilterByElevation → FormatVolcanoes.

Run from the repo root:

    PYTHONPATH=. python examples/volcano-query/test_volcano.py
"""

import json

from afl.runtime import Evaluator, ExecutionStatus, MemoryStore, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

# Runtime AST for:
#
#   namespace volcano {
#       event facet LoadVolcanoData() => (result: VolcanoDataset)
#       event facet FilterByRegion(volcanoes: Json, state: String) => (result: VolcanoList)
#       event facet FilterByElevation(volcanoes: Json, min_elevation_ft: Long) => (result: VolcanoList)
#       event facet FormatVolcanoes(volcanoes: Json, count: Long) => (result: FormattedResult)
#       event facet RenderMap(volcanoes: Json, title: String) => (result: MapResult)
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
                    "name": "LoadVolcanoData",
                    "params": [],
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


def mock_load_handler(payload: dict) -> dict:
    """Return full mock dataset."""
    return {
        "result": {
            "volcanoes": json.dumps(MOCK_ALL_VOLCANOES),
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
    poller.register("volcano.LoadVolcanoData", mock_load_handler)
    poller.register("volcano.FilterByRegion", mock_filter_region_handler)
    poller.register("volcano.FilterByElevation", mock_filter_elevation_handler)
    poller.register("volcano.FormatVolcanoes", mock_format_handler)

    # 1. Execute workflow — pauses at the LoadVolcanoData event step
    print("Executing FindVolcanoes workflow...")
    result = evaluator.execute(
        WORKFLOW_AST,
        inputs={"state": "California", "min_elevation_ft": 5000},
        program_ast=PROGRAM_AST,
    )
    print(f"  Status: {result.status}")
    assert result.status == ExecutionStatus.PAUSED, "Should pause at LoadVolcanoData event"

    # 2. Agent processes the LoadVolcanoData event
    print("Agent processing LoadVolcanoData event...")
    dispatched = poller.poll_once()
    print(f"  Dispatched: {dispatched} task(s)")
    assert dispatched == 1

    # 3. Resume — hits FilterByRegion event, pauses again
    print("Resuming workflow (should pause at FilterByRegion)...")
    result2 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result2.status}")
    assert result2.status == ExecutionStatus.PAUSED, "Should pause at FilterByRegion event"

    # 4. Agent processes the FilterByRegion event
    print("Agent processing FilterByRegion event...")
    dispatched2 = poller.poll_once()
    print(f"  Dispatched: {dispatched2} task(s)")
    assert dispatched2 == 1

    # 5. Resume — hits FilterByElevation event, pauses again
    print("Resuming workflow (should pause at FilterByElevation)...")
    result3 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result3.status}")
    assert result3.status == ExecutionStatus.PAUSED, "Should pause at FilterByElevation event"

    # 6. Agent processes the FilterByElevation event
    print("Agent processing FilterByElevation event...")
    dispatched3 = poller.poll_once()
    print(f"  Dispatched: {dispatched3} task(s)")
    assert dispatched3 == 1

    # 7. Resume — hits FormatVolcanoes event, pauses again
    print("Resuming workflow (should pause at FormatVolcanoes)...")
    result4 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result4.status}")
    assert result4.status == ExecutionStatus.PAUSED, "Should pause at FormatVolcanoes event"

    # 8. Agent processes the FormatVolcanoes event
    print("Agent processing FormatVolcanoes event...")
    dispatched4 = poller.poll_once()
    print(f"  Dispatched: {dispatched4} task(s)")
    assert dispatched4 == 1

    # 9. Resume to completion
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
