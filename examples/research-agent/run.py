#!/usr/bin/env python3
"""Research Agent — end-to-end smoke run.

Drives the ResearchTopic workflow against an in-memory store with a
mocked Anthropic client (so no API key needed). Each domain handler
calls fwh_anthropic's ``create_message`` under the hood; the mock
returns shape-correct JSON per stage based on the system-prompt
fragment.

Real runs (Claude API) — drop the mock and set ANTHROPIC_API_KEY:

    pip install -e ~/fw_handlers/fwh_anthropic
    export ANTHROPIC_API_KEY=sk-...
    python examples/research-agent/run.py --live    # not implemented; see notes

Usage:
    python examples/research-agent/run.py

Exits 0 on COMPLETED with the expected outputs, non-zero otherwise.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

RESEARCH_FFL = Path(__file__).parent / "ffl" / "research.ffl"
sys.path.insert(0, str(Path(__file__).parent))


# ---------------------------------------------------------------------------
# Canned LLM responses — picked by system-prompt fragment so each
# handler's CreateMessage call gets a shape-correct reply.
# ---------------------------------------------------------------------------


def _canned_response_for(system: str) -> str:
    s = system.lower()
    if "research planning assistant" in s:
        return json.dumps({
            "name": "quantum sensing",
            "depth": 3,
            "keywords": ["nv-center", "atomic clocks", "magnetometry"],
            "summary": "Three-axis exploration of quantum sensing modalities.",
            "max_subtopics": 3,
        })
    if "decomposition expert" in s:
        return json.dumps([
            {"name": "NV center magnetometry", "parent_topic": "quantum sensing",
             "description": "Diamond NV-center based magnetic field detection.",
             "priority": 3},
            {"name": "Atomic clocks", "parent_topic": "quantum sensing",
             "description": "Optical lattice and ion-trap clocks.", "priority": 2},
            {"name": "Quantum gravimetry", "parent_topic": "quantum sensing",
             "description": "Atom-interferometer gravimeters.", "priority": 1},
        ])
    if "research librarian" in s:
        return json.dumps([
            {"title": "Nature Phys 2024: NV ensembles", "url": "https://example/1",
             "relevance_score": 0.92, "source_type": "journal"},
            {"title": "PRX 2023: lattice clocks at 1e-19", "url": "https://example/2",
             "relevance_score": 0.88, "source_type": "journal"},
            {"title": "Science 2024: cold-atom gravimeter", "url": "https://example/3",
             "relevance_score": 0.85, "source_type": "journal"},
        ])
    if "research analyst" in s:
        return json.dumps([
            {"claim": "NV ensembles reach 1 pT sensitivity.",
             "evidence": "Nature Phys 2024 figure 3.",
             "confidence": 0.86, "source_title": "Nature Phys 2024: NV ensembles"},
            {"claim": "Optical clocks now stable to 1e-19.",
             "evidence": "PRX 2023 systematic table.",
             "confidence": 0.91, "source_title": "PRX 2023: lattice clocks at 1e-19"},
        ])
    if "research synthesizer" in s:
        return json.dumps({
            "themes": ["Sensitivity gains", "Field deployment readiness",
                       "Cross-platform interoperability"],
            "contradictions": ["NV vs. atomic-clock cost/SWaP tradeoff disputed"],
            "gaps": ["Few longitudinal field studies", "Limited public datasets"],
            "summary": "Quantum sensing is converging on lab-grade sensitivity outside the lab.",
            "confidence_score": 0.78,
        })
    if "research quality reviewer" in s:
        return json.dumps({
            "gaps": [
                {"description": "No fielded gravimeter benchmarks",
                 "severity": "high", "area": "deployment"},
            ],
            "recommendations": [
                {"action": "Commission a field-trial benchmark suite",
                 "priority": "high", "estimated_effort": "high"},
            ],
        })
    if "technical writer" in s:
        return json.dumps({
            "title": "Quantum Sensing: 2025 State of the Art",
            "sections": [
                {"title": "Introduction",
                 "content": "Quantum sensing has matured rapidly over the last decade."},
                {"title": "Methodology",
                 "content": "Survey of three primary modalities and their figures of merit."},
                {"title": "Findings",
                 "content": "Sensitivity gains are real; field readiness is uneven."},
                {"title": "Discussion",
                 "content": "Cross-platform interoperability remains a gap."},
                {"title": "Conclusion",
                 "content": "Investment is warranted in field-trial infrastructure."},
            ],
            "word_count": 50,
            "citations": ["[1] Nature Phys 2024", "[2] PRX 2023", "[3] Science 2024"],
        })
    if "peer reviewer" in s:
        return json.dumps({
            "score": 82,
            "approved": True,
            "feedback": ["Well-structured; cite more recent work in NV section."],
            "suggested_edits": [
                {"section": "Methodology",
                 "suggestion": "Add concrete sensitivity figures of merit."}
            ],
        })
    return json.dumps({"placeholder": True, "system_seen": system[:80]})


def _build_mock_client():
    client = MagicMock()

    def _create(*, system=None, messages=None, model=None, **kwargs):
        if isinstance(system, list):
            system_text = " ".join(b.get("text", "") for b in system if isinstance(b, dict))
        else:
            system_text = str(system or "")
        body = _canned_response_for(system_text)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=body)],
            model=model or "claude-sonnet-4-6",
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=120, output_tokens=80),
        )

    client.messages.create = MagicMock(side_effect=_create)
    return client


# ---------------------------------------------------------------------------
# Compile FFL
# ---------------------------------------------------------------------------


def _compile_workflow():
    from facetwork import FFLParser, emit_dict
    from facetwork.ast_utils import find_workflow

    program = emit_dict(FFLParser().parse(RESEARCH_FFL.read_text()))
    workflow_ast = find_workflow(program, "ResearchTopic")
    return program, workflow_ast


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def _register_research_handlers(poller):
    from handlers.analysis.analysis_handlers import _DISPATCH as analysis_d
    from handlers.gathering.gathering_handlers import _DISPATCH as gathering_d
    from handlers.planning.planning_handlers import _DISPATCH as planning_d
    from handlers.writing.writing_handlers import _DISPATCH as writing_d

    for d in (planning_d, gathering_d, analysis_d, writing_d):
        for facet, fn in d.items():
            poller.register(facet, fn)


# ---------------------------------------------------------------------------
# Drive the workflow
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("research-agent end-to-end smoke run (mocked Anthropic client)")
    print("=" * 70)

    from facetwork.runtime import Evaluator, ExecutionStatus, MemoryStore, Telemetry
    from facetwork.runtime.agent_poller import AgentPoller, AgentPollerConfig

    try:
        from anthropic_handlers.tools._lib import messages as msg_lib
    except ImportError:
        sys.exit(
            "ERROR: anthropic_handlers package not importable.\n"
            "  pip install -e ~/fw_handlers/fwh_anthropic"
        )

    mock_client = _build_mock_client()
    patcher = patch.object(msg_lib, "get_client", return_value=mock_client)
    patcher.start()

    try:
        program, workflow_ast = _compile_workflow()
        ns_count = sum(
            1 for d in program.get("declarations", []) if d.get("type") == "Namespace"
        )
        print(f"\nCompiled OK — {ns_count} namespaces, workflow=ResearchTopic\n")

        store = MemoryStore()
        evaluator = Evaluator(persistence=store, telemetry=Telemetry(enabled=False))
        poller = AgentPoller(
            persistence=store,
            evaluator=evaluator,
            config=AgentPollerConfig(service_name="research-agent-run"),
        )
        _register_research_handlers(poller)
        print(f"Registered {len(poller.registered_names())} research.* handlers")

        inputs = {
            "topic": "quantum sensing",
            "depth": 3,
            "max_subtopics": 3,
            "sources_per_subtopic": 3,
        }
        result = evaluator.execute(workflow_ast, inputs=inputs, program_ast=program)
        poller.cache_workflow_ast(result.workflow_id, workflow_ast, program_ast=program)
        wf_id = result.workflow_id
        print(f"\nInitial execute → status={result.status} workflow_id={wf_id}")

        # AgentPoller's _process_event auto-resumes after each handler,
        # so just poll until the workflow root reports terminal state.
        # Calling evaluator.resume() between polls races with the
        # poller's own resume and corrupts step output evaluation.
        max_iter = 200
        idle = 0
        last_dispatched_iter = -1
        for i in range(max_iter):
            root = store.get_workflow_root(wf_id)
            if root and root.is_complete:
                print(f"\nWorkflow COMPLETED after {i} poll iterations")
                break
            if root and root.is_error:
                err = root.transition.error if root.transition else "unknown"
                print(f"\nWorkflow ERROR: {err}")
                return 1
            dispatched = poller.poll_once()
            if dispatched > 0:
                last_dispatched_iter = i
                idle = 0
                print(f"iter {i}: dispatched {dispatched} task(s)")
            else:
                idle += 1
                # Give the workflow a chance to settle after the last
                # batch of handler calls — its resume schedules the
                # next round of event tasks.
                if idle >= 50:
                    break
                time.sleep(0.05)
        else:
            print(f"\nWorkflow did not finish within {max_iter} poll iterations")
            return 1
        print(f"Last dispatched at iter {last_dispatched_iter}")

        root = store.get_workflow_root(wf_id)
        if not root or not root.is_complete:
            # Show step states for diagnosis
            err = (root.transition.error if root and root.transition else "no terminal state")
            print(f"\nWorkflow did not reach COMPLETED: {err}")
            print("\nWorkflow root state:")
            if root:
                print(f"  is_complete: {root.is_complete}")
                print(f"  is_error: {root.is_error}")
                print(f"  transition: {root.transition}")
            print("\nAll steps:")
            for step in store.get_steps_by_workflow(wf_id):
                state = "?"
                if step.transition:
                    state = getattr(step.transition, "next_state", None) or getattr(step.transition, "state", "?")
                print(f"  step={getattr(step, 'name', '?')} facet={getattr(step, 'facet_name', '?')} state={state}")
            return 1
        outputs = {name: attr.value for name, attr in root.attributes.returns.items()}
        print(f"\nFinal status: COMPLETED")
        report = outputs.get("report") or {}
        review = outputs.get("review") or {}
        print("\n" + "=" * 70)
        print("OUTPUT — Draft")
        print("=" * 70)
        print(f"  title:        {report.get('title')}")
        print(f"  word_count:   {report.get('word_count')}")
        print(f"  sections:     {len(report.get('sections', []))} section(s)")
        for s in report.get("sections", []):
            print(f"    - {s.get('title')}: {s.get('content', '')[:70]}")
        print(f"  citations:    {report.get('citations')}")

        print("\n" + "=" * 70)
        print("OUTPUT — Review")
        print("=" * 70)
        print(f"  score:        {review.get('score')}")
        print(f"  approved:     {review.get('approved')}")
        print(f"  feedback:     {review.get('feedback')}")
        print(f"  summary:      {outputs.get('summary')}")
        print()

        problems = []
        if not isinstance(report.get("title"), str) or not report["title"]:
            problems.append("missing draft.title")
        if not report.get("sections"):
            problems.append("draft.sections empty")
        if not isinstance(review.get("score"), int):
            problems.append("review.score not an integer")
        if problems:
            print("FAIL — workflow output incomplete:")
            for p in problems:
                print(f"  - {p}")
            return 1

        call_count = mock_client.messages.create.call_count
        print(f"Mock Anthropic client.messages.create calls: {call_count}")
        if call_count < 8:
            print(f"FAIL — expected at least 8 LLM calls, got {call_count}")
            return 1

        print("\nSUCCESS — workflow ran end-to-end with mocked Anthropic client")
        return 0
    finally:
        patcher.stop()


if __name__ == "__main__":
    sys.exit(main())
