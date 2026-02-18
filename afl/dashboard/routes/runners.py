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

"""Runner routes — list, detail, actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from ..dependencies import get_store
from ..tree import build_step_tree

router = APIRouter(prefix="/runners")


@router.get("")
def runner_list(request: Request, state: str | None = None, store=Depends(get_store)):
    """List all runners, optionally filtered by state."""
    if state:
        runners = store.get_runners_by_state(state)
    else:
        runners = store.get_all_runners()

    return request.app.state.templates.TemplateResponse(
        request,
        "runners/list.html",
        {"runners": runners, "filter_state": state},
    )


@router.get("/{runner_id}")
def runner_detail(runner_id: str, request: Request, store=Depends(get_store)):
    """Show runner detail with steps, logs, and parameters."""
    runner = store.get_runner(runner_id)
    if not runner:
        return request.app.state.templates.TemplateResponse(
            request,
            "runners/detail.html",
            {"runner": None, "steps": [], "logs": []},
        )

    steps = store.get_steps_by_workflow(runner.workflow_id)
    logs = store.get_logs_by_runner(runner_id)

    return request.app.state.templates.TemplateResponse(
        request,
        "runners/detail.html",
        {"runner": runner, "steps": steps, "tree": build_step_tree(list(steps)), "logs": logs},
    )


@router.get("/{runner_id}/steps")
def runner_steps(runner_id: str, request: Request, store=Depends(get_store)):
    """Steps list for a runner's workflow."""
    runner = store.get_runner(runner_id)
    steps = store.get_steps_by_workflow(runner.workflow_id) if runner else []
    return request.app.state.templates.TemplateResponse(
        request,
        "steps/list.html",
        {"steps": steps, "tree": build_step_tree(list(steps)), "runner": runner},
    )


@router.get("/{runner_id}/logs")
def runner_logs(runner_id: str, request: Request, store=Depends(get_store)):
    """Logs for a runner."""
    runner = store.get_runner(runner_id)
    logs = store.get_logs_by_runner(runner_id)
    return request.app.state.templates.TemplateResponse(
        request,
        "logs/list.html",
        {"logs": logs, "runner": runner},
    )


# --- Action endpoints ---


@router.post("/{runner_id}/cancel")
def cancel_runner(runner_id: str, store=Depends(get_store)):
    """Cancel a runner."""
    store.update_runner_state(runner_id, "cancelled")
    return RedirectResponse(url=f"/runners/{runner_id}", status_code=303)


@router.post("/{runner_id}/pause")
def pause_runner(runner_id: str, store=Depends(get_store)):
    """Pause a running runner."""
    store.update_runner_state(runner_id, "paused")
    return RedirectResponse(url=f"/runners/{runner_id}", status_code=303)


@router.post("/{runner_id}/resume")
def resume_runner(runner_id: str, store=Depends(get_store)):
    """Resume a paused runner."""
    store.update_runner_state(runner_id, "running")
    return RedirectResponse(url=f"/runners/{runner_id}", status_code=303)
