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

"""JSON API endpoints — used by htmx partials and for programmatic access."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..dependencies import get_store

router = APIRouter(prefix="/api")


# -- Runners -----------------------------------------------------------------


@router.get("/runners")
def api_runners(
    request: Request,
    state: str | None = None,
    partial: bool = False,
    store=Depends(get_store),
):
    """Return runners as JSON or htmx partial rows."""
    if state:
        runners = store.get_runners_by_state(state)
    else:
        runners = store.get_all_runners()

    if partial:
        templates = request.app.state.templates
        html = ""
        for runner in runners:
            html += templates.get_template("partials/runner_row.html").render(
                runner=runner, request=request
            )
        return HTMLResponse(html)

    return JSONResponse([_runner_dict(r) for r in runners])


@router.get("/runners/{runner_id}")
def api_runner_detail(runner_id: str, store=Depends(get_store)):
    """Return a single runner as JSON."""
    runner = store.get_runner(runner_id)
    if not runner:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_runner_dict(runner))


@router.get("/runners/{runner_id}/steps")
def api_runner_steps(
    runner_id: str,
    request: Request,
    partial: bool = False,
    store=Depends(get_store),
):
    """Return steps for a runner's workflow."""
    runner = store.get_runner(runner_id)
    if not runner:
        return JSONResponse({"error": "not found"}, status_code=404)

    steps = store.get_steps_by_workflow(runner.workflow_id)

    if partial:
        templates = request.app.state.templates
        html = ""
        for step in steps:
            html += templates.get_template("partials/step_row.html").render(
                step=step, request=request
            )
        return HTMLResponse(html)

    return JSONResponse([_step_dict(s) for s in steps])


# -- Steps -------------------------------------------------------------------


@router.get("/steps/{step_id}")
def api_step_detail(step_id: str, store=Depends(get_store)):
    """Return a single step as JSON."""
    step = store.get_step(step_id)
    if not step:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_step_dict(step))


# -- Flows -------------------------------------------------------------------


@router.get("/flows")
def api_flows(store=Depends(get_store)):
    """Return all flows as JSON."""
    flows = store.get_all_flows()
    return JSONResponse(
        [
            {
                "uuid": f.uuid,
                "name": f.name.name,
                "path": f.name.path,
                "workflows": len(f.workflows),
                "sources": len(f.compiled_sources),
            }
            for f in flows
        ]
    )


# -- Servers -----------------------------------------------------------------


@router.get("/servers")
def api_servers(store=Depends(get_store)):
    """Return all servers as JSON."""
    servers = store.get_all_servers()
    return JSONResponse(
        [
            {
                "uuid": s.uuid,
                "server_name": s.server_name,
                "server_group": s.server_group,
                "service_name": s.service_name,
                "state": s.state,
                "ping_time": s.ping_time,
                "handlers": s.handlers,
            }
            for s in servers
        ]
    )


# -- Handlers ----------------------------------------------------------------


@router.get("/handlers")
def api_handlers(store=Depends(get_store)):
    """Return all handler registrations as JSON."""
    handlers = store.list_handler_registrations()
    return JSONResponse(
        [
            {
                "facet_name": h.facet_name,
                "module_uri": h.module_uri,
                "entrypoint": h.entrypoint,
                "version": h.version,
                "timeout_ms": h.timeout_ms,
                "created": h.created,
                "updated": h.updated,
            }
            for h in handlers
        ]
    )


# -- Events ------------------------------------------------------------------


@router.get("/events")
def api_events(store=Depends(get_store)):
    """Return all events as JSON."""
    events = store.get_all_events()
    return JSONResponse(
        [
            {
                "id": e.id,
                "step_id": e.step_id,
                "workflow_id": e.workflow_id,
                "state": e.state,
                "event_type": e.event_type,
                "payload": e.payload,
            }
            for e in events
        ]
    )


# -- Helpers -----------------------------------------------------------------


def _runner_dict(runner) -> dict:
    return {
        "uuid": runner.uuid,
        "workflow_id": runner.workflow_id,
        "workflow_name": runner.workflow.name,
        "state": runner.state,
        "start_time": runner.start_time,
        "end_time": runner.end_time,
        "duration": runner.duration,
    }


def _step_dict(step) -> dict:
    return {
        "id": step.id,
        "workflow_id": step.workflow_id,
        "object_type": step.object_type,
        "state": step.state,
        "statement_id": step.statement_id,
        "container_id": step.container_id,
        "block_id": step.block_id,
    }
