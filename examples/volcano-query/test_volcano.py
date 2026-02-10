#!/usr/bin/env python3
"""Offline test for the Volcano Query agent.

Demonstrates the full workflow execution cycle with mock handlers
(no network calls). Two-step workflow: QueryVolcanoes → FormatVolcanoes.

Run from the repo root:

    PYTHONPATH=. python examples/volcano-query/test_volcano.py
"""

from afl.runtime import Evaluator, ExecutionStatus, MemoryStore, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig

# Runtime AST for:
#
#   namespace volcano {
#       event facet QueryVolcanoes(state: String, min_elevation_ft: Long) => (result: VolcanoList)
#       event facet FormatVolcanoes(volcanoes: Json, count: Long) => (result: FormattedResult)
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
                    "name": "QueryVolcanoes",
                    "params": [
                        {"name": "state", "type": "String"},
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
            ],
        },
    ],
}

# Runtime AST for:
#
#   workflow FindVolcanoes(state: String, min_elevation_ft: Long) => (text: String, count: Long) andThen {
#       query = QueryVolcanoes(state = $.state, min_elevation_ft = $.min_elevation_ft)
#       fmt = FormatVolcanoes(volcanoes = query.result.volcanoes, count = query.result.count)
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
                "id": "step-query",
                "name": "query",
                "call": {
                    "type": "CallExpr",
                    "target": "QueryVolcanoes",
                    "args": [
                        {
                            "name": "state",
                            "value": {"type": "InputRef", "path": ["state"]},
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
                                "path": ["query", "result", "volcanoes"],
                            },
                        },
                        {
                            "name": "count",
                            "value": {
                                "type": "StepRef",
                                "path": ["query", "result", "count"],
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

MOCK_CA_VOLCANOES = [
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
]


def mock_query_handler(payload: dict) -> dict:
    """Return known California volcanoes over 5000 ft."""
    import json

    return {
        "result": {
            "volcanoes": json.dumps(MOCK_CA_VOLCANOES),
            "count": len(MOCK_CA_VOLCANOES),
        }
    }


def mock_format_handler(payload: dict) -> dict:
    """Format volcano list into text."""
    import json

    volcanoes = json.loads(payload["volcanoes"]) if isinstance(payload["volcanoes"], str) else payload["volcanoes"]
    count = payload["count"]
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
    poller.register("volcano.QueryVolcanoes", mock_query_handler)
    poller.register("volcano.FormatVolcanoes", mock_format_handler)

    # 1. Execute workflow — pauses at the QueryVolcanoes event step
    print("Executing FindVolcanoes workflow...")
    result = evaluator.execute(
        WORKFLOW_AST,
        inputs={"state": "California", "min_elevation_ft": 5000},
        program_ast=PROGRAM_AST,
    )
    print(f"  Status: {result.status}")
    assert result.status == ExecutionStatus.PAUSED, "Should pause at QueryVolcanoes event"

    # NOTE: We do NOT cache the workflow AST with the poller because
    # the poller's internal resume does not pass program_ast, which
    # means it can't identify the second event facet. Instead we let
    # the poller handle event dispatch only and resume manually.

    # 2. Agent processes the QueryVolcanoes event
    print("Agent processing QueryVolcanoes event...")
    dispatched = poller.poll_once()
    print(f"  Dispatched: {dispatched} task(s)")
    assert dispatched == 1

    # 3. Resume with program_ast — hits FormatVolcanoes event, pauses again
    print("Resuming workflow (should pause at FormatVolcanoes)...")
    result2 = evaluator.resume(result.workflow_id, WORKFLOW_AST, PROGRAM_AST)
    print(f"  Status: {result2.status}")
    assert result2.status == ExecutionStatus.PAUSED, "Should pause at FormatVolcanoes event"

    # 4. Agent processes the FormatVolcanoes event
    print("Agent processing FormatVolcanoes event...")
    dispatched2 = poller.poll_once()
    print(f"  Dispatched: {dispatched2} task(s)")
    assert dispatched2 == 1

    # 5. Resume to completion
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
