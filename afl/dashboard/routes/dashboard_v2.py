# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Dashboard v2 routes — namespace-grouped workflow views."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_store
from ..helpers import categorize_step_state, group_runners_by_namespace

router = APIRouter(prefix="/v2")

# Runner states by tab
_RUNNING_STATES = {"created", "running", "paused"}
_COMPLETED_STATES = {"completed"}
_FAILED_STATES = {"failed", "cancelled"}

_TAB_STATES = {
    "running": _RUNNING_STATES,
    "completed": _COMPLETED_STATES,
    "failed": _FAILED_STATES,
}


def _filter_runners(runners: list, tab: str) -> list:
    """Filter runners by tab selection."""
    allowed = _TAB_STATES.get(tab, _RUNNING_STATES)
    return [r for r in runners if r.state in allowed]


def _count_by_tab(runners: list) -> dict[str, int]:
    """Count runners per tab."""
    counts = {"running": 0, "completed": 0, "failed": 0}
    for r in runners:
        if r.state in _RUNNING_STATES:
            counts["running"] += 1
        elif r.state in _COMPLETED_STATES:
            counts["completed"] += 1
        elif r.state in _FAILED_STATES:
            counts["failed"] += 1
    return counts


@router.get("/workflows")
def workflow_list(
    request: Request,
    tab: str = "running",
    store=Depends(get_store),
):
    """Main workflow list with state tabs and namespace grouping."""
    all_runners = store.get_all_runners(limit=1000)
    tab_counts = _count_by_tab(all_runners)
    filtered = _filter_runners(all_runners, tab)
    groups = group_runners_by_namespace(filtered)

    return request.app.state.templates.TemplateResponse(
        request,
        "v2/workflows/list.html",
        {
            "groups": groups,
            "tab": tab,
            "tab_counts": tab_counts,
            "active_tab": "workflows",
        },
    )


@router.get("/workflows/partial")
def workflow_list_partial(
    request: Request,
    tab: str = "running",
    store=Depends(get_store),
):
    """HTMX partial for auto-refresh of runner groups."""
    all_runners = store.get_all_runners(limit=1000)
    tab_counts = _count_by_tab(all_runners)
    filtered = _filter_runners(all_runners, tab)
    groups = group_runners_by_namespace(filtered)

    return request.app.state.templates.TemplateResponse(
        request,
        "v2/workflows/_runner_groups.html",
        {
            "groups": groups,
            "tab": tab,
            "tab_counts": tab_counts,
        },
    )


@router.get("/workflows/{runner_id}")
def workflow_detail(
    runner_id: str,
    request: Request,
    step_tab: str = "running",
    store=Depends(get_store),
):
    """Workflow detail with step sub-tabs."""
    runner = store.get_runner(runner_id)
    if not runner:
        return request.app.state.templates.TemplateResponse(
            request,
            "v2/workflows/detail.html",
            {
                "runner": None,
                "steps": [],
                "step_counts": {},
                "step_tab": step_tab,
                "active_tab": "workflows",
            },
        )

    all_steps = list(store.get_steps_by_workflow(runner.workflow_id))

    # Categorize and count steps
    step_counts = {"running": 0, "error": 0, "complete": 0}
    for s in all_steps:
        cat = categorize_step_state(s.state)
        step_counts[cat] = step_counts.get(cat, 0) + 1

    # Filter steps by selected tab
    filtered_steps = [s for s in all_steps if categorize_step_state(s.state) == step_tab]

    return request.app.state.templates.TemplateResponse(
        request,
        "v2/workflows/detail.html",
        {
            "runner": runner,
            "steps": filtered_steps,
            "step_counts": step_counts,
            "step_tab": step_tab,
            "active_tab": "workflows",
        },
    )


@router.get("/workflows/{runner_id}/steps/partial")
def step_rows_partial(
    runner_id: str,
    request: Request,
    step_tab: str = "running",
    store=Depends(get_store),
):
    """HTMX partial for step table refresh."""
    runner = store.get_runner(runner_id)
    if not runner:
        return request.app.state.templates.TemplateResponse(
            request,
            "v2/workflows/_step_rows.html",
            {"steps": [], "runner": None, "step_tab": step_tab, "step_counts": {}},
        )

    all_steps = list(store.get_steps_by_workflow(runner.workflow_id))
    step_counts = {"running": 0, "error": 0, "complete": 0}
    for s in all_steps:
        cat = categorize_step_state(s.state)
        step_counts[cat] = step_counts.get(cat, 0) + 1

    filtered_steps = [s for s in all_steps if categorize_step_state(s.state) == step_tab]

    return request.app.state.templates.TemplateResponse(
        request,
        "v2/workflows/_step_rows.html",
        {
            "steps": filtered_steps,
            "runner": runner,
            "step_tab": step_tab,
            "step_counts": step_counts,
        },
    )


@router.get("/workflows/{runner_id}/steps/{step_id}/expand")
def step_detail_expand(
    runner_id: str,
    step_id: str,
    request: Request,
    store=Depends(get_store),
):
    """HTMX partial for inline step expansion."""
    runner = store.get_runner(runner_id)
    step = store.get_step(step_id) if runner else None
    task = None
    if step:
        try:
            task = store.get_task_for_step(step_id)
        except Exception:
            pass

    return request.app.state.templates.TemplateResponse(
        request,
        "v2/workflows/_step_detail.html",
        {
            "step": step,
            "task": task,
            "runner": runner,
        },
    )
