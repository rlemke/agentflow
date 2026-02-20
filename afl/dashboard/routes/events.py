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

"""Event dashboard routes.

Events are now backed by the tasks collection. The /events UI shows
tasks (which represent event facet work dispatched to agents).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_store

router = APIRouter(prefix="/events")


@router.get("")
def event_list(request: Request, state: str | None = None, store=Depends(get_store)):
    """List all events (tasks), optionally filtered by state."""
    if state:
        tasks = store.get_tasks_by_state(state)
    else:
        tasks = store.get_all_tasks()

    step_names: dict[str, str] = {}
    for task in tasks:
        if task.step_id and task.step_id not in step_names:
            step = store.get_step(task.step_id)
            if step:
                step_names[task.step_id] = step.statement_name or step.facet_name or ""

    return request.app.state.templates.TemplateResponse(
        request,
        "events/list.html",
        {"events": tasks, "filter_state": state, "step_names": step_names},
    )


@router.get("/{task_id}")
def event_detail(task_id: str, request: Request, store=Depends(get_store)):
    """Show event (task) detail."""
    task = store.get_task(task_id)
    step_name = ""
    if task and task.step_id:
        step = store.get_step(task.step_id)
        if step:
            step_name = step.statement_name or step.facet_name or ""
    return request.app.state.templates.TemplateResponse(
        request,
        "events/detail.html",
        {"event": task, "step_name": step_name},
    )
