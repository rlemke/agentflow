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

"""Home / summary dashboard route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_store

router = APIRouter()


@router.get("/")
def home(request: Request, store=Depends(get_store)):
    """Render the summary dashboard."""
    runners = store.get_all_runners(limit=500)
    servers = store.get_all_servers()
    tasks = store.get_all_tasks(limit=500)

    # Count runners by state
    runner_counts: dict[str, int] = {}
    for r in runners:
        runner_counts[r.state] = runner_counts.get(r.state, 0) + 1

    # Count tasks by state
    task_counts: dict[str, int] = {}
    for t in tasks:
        task_counts[t.state] = task_counts.get(t.state, 0) + 1

    return request.app.state.templates.TemplateResponse(
        request,
        "index.html",
        {
            "runner_counts": runner_counts,
            "total_runners": len(runners),
            "server_count": len(servers),
            "task_counts": task_counts,
            "total_tasks": len(tasks),
        },
    )
