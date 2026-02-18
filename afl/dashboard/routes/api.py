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


# -- Tasks -------------------------------------------------------------------


@router.get("/tasks")
def api_tasks(state: str | None = None, store=Depends(get_store)):
    """Return all tasks as JSON, optionally filtered by state."""
    if state:
        tasks = store.get_tasks_by_state(state)
    else:
        tasks = store.get_all_tasks()
    return JSONResponse([_task_dict(t) for t in tasks])


@router.get("/tasks/{task_id}")
def api_task_detail(task_id: str, store=Depends(get_store)):
    """Return a single task as JSON."""
    task = store.get_task(task_id)
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_task_dict(task))


# -- Flows -------------------------------------------------------------------


@router.get("/flows")
def api_flows(q: str | None = None, store=Depends(get_store)):
    """Return all flows as JSON, optionally filtered by name search."""
    flows = store.get_all_flows()
    if q:
        flows = [f for f in flows if q.lower() in f.name.name.lower()]
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


@router.get("/flows/{flow_id}")
def api_flow_detail(flow_id: str, store=Depends(get_store)):
    """Return a single flow as JSON."""
    flow = store.get_flow(flow_id)
    if not flow:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(
        {
            "uuid": flow.uuid,
            "name": flow.name.name,
            "path": flow.name.path,
            "namespaces": [{"uuid": n.uuid, "name": n.name} for n in flow.namespaces],
            "facets": [
                {"uuid": f.uuid, "name": f.name, "namespace_id": f.namespace_id}
                for f in flow.facets
            ],
            "workflows": len(flow.workflows),
            "sources": len(flow.compiled_sources),
        }
    )


# -- Namespaces --------------------------------------------------------------


@router.get("/namespaces")
def api_namespaces(store=Depends(get_store)):
    """Return namespaces aggregated across all flows."""
    flows = store.get_all_flows()
    namespaces = []
    for flow in flows:
        for ns in flow.namespaces:
            namespaces.append(
                {
                    "uuid": ns.uuid,
                    "name": ns.name,
                    "flow_id": flow.uuid,
                    "flow_name": flow.name.name,
                }
            )
    return JSONResponse(namespaces)


# -- Servers -----------------------------------------------------------------


@router.get("/servers")
def api_servers(state: str | None = None, store=Depends(get_store)):
    """Return all servers as JSON, optionally filtered by state."""
    if state:
        servers = store.get_servers_by_state(state)
    else:
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
def api_handlers(q: str | None = None, store=Depends(get_store)):
    """Return all handler registrations as JSON, optionally filtered by facet name."""
    handlers = store.list_handler_registrations()
    if q:
        handlers = [h for h in handlers if q.lower() in h.facet_name.lower()]
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


@router.get("/servers/{server_id}")
def api_server_detail(server_id: str, store=Depends(get_store)):
    """Return a single server as JSON."""
    server = store.get_server(server_id)
    if not server:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(
        {
            "uuid": server.uuid,
            "server_name": server.server_name,
            "server_group": server.server_group,
            "service_name": server.service_name,
            "state": server.state,
            "ping_time": server.ping_time,
            "handlers": server.handlers,
            "topics": server.topics,
        }
    )


# -- Locks -------------------------------------------------------------------


@router.get("/locks")
def api_locks(store=Depends(get_store)):
    """Return all locks as JSON."""
    locks = store.get_all_locks()
    return JSONResponse(
        [
            {
                "key": l.key,
                "acquired_at": l.acquired_at,
                "expires_at": l.expires_at,
                "meta": {
                    "topic": l.meta.topic,
                    "handler": l.meta.handler,
                    "step_name": l.meta.step_name,
                    "step_id": l.meta.step_id,
                }
                if l.meta
                else None,
            }
            for l in locks
        ]
    )


# -- Sources -----------------------------------------------------------------


@router.get("/sources")
def api_sources(q: str | None = None, store=Depends(get_store)):
    """Return all published sources as JSON, optionally filtered by namespace."""
    sources = store.list_published_sources()
    if q:
        sources = [s for s in sources if q.lower() in s.namespace_name.lower()]
    return JSONResponse(
        [
            {
                "uuid": s.uuid,
                "namespace_name": s.namespace_name,
                "version": s.version,
                "origin": s.origin,
                "published_at": s.published_at,
                "checksum": s.checksum,
                "namespaces_defined": s.namespaces_defined,
            }
            for s in sources
        ]
    )


# -- Events ------------------------------------------------------------------


@router.get("/events")
def api_events(state: str | None = None, store=Depends(get_store)):
    """Return all events as JSON, optionally filtered by state."""
    if state:
        events = store.get_events_by_state(state)
    else:
        events = store.get_all_events()

    step_names: dict[str, str] = {}
    for e in events:
        if e.step_id and e.step_id not in step_names:
            step = store.get_step(e.step_id)
            if step:
                step_names[e.step_id] = step.statement_name or step.facet_name or ""

    return JSONResponse(
        [
            {
                "id": e.id,
                "step_id": e.step_id,
                "step_name": step_names.get(e.step_id, ""),
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
    d = {
        "id": step.id,
        "workflow_id": step.workflow_id,
        "object_type": step.object_type,
        "facet_name": step.facet_name,
        "state": step.state,
        "statement_id": step.statement_id,
        "statement_name": step.statement_name,
        "container_id": step.container_id,
        "block_id": step.block_id,
        "start_time": step.start_time,
        "last_modified": step.last_modified,
    }
    if step.attributes:
        d["params"] = {k: {"value": v.value, "type": v.type_hint} for k, v in step.attributes.params.items()}
        d["returns"] = {k: {"value": v.value, "type": v.type_hint} for k, v in step.attributes.returns.items()}
    return d


def _task_dict(task) -> dict:
    return {
        "uuid": task.uuid,
        "name": task.name,
        "state": task.state,
        "runner_id": task.runner_id,
        "workflow_id": task.workflow_id,
        "flow_id": task.flow_id,
        "step_id": task.step_id,
        "task_list_name": task.task_list_name,
        "data_type": task.data_type,
        "created": task.created,
        "updated": task.updated,
        "duration": task.updated - task.created if task.updated and task.created else 0,
    }
