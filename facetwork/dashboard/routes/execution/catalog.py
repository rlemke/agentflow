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

"""Claude workflow catalog browser routes.

Read views over the catalog (`facetwork.catalog`) plus publish (review-gate)
and run actions. The catalog requires a MongoStore-backed store (`_db`); with
any other store the pages render an "unavailable" notice rather than erroring.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ...dependencies import get_store

router = APIRouter(prefix="/catalog")


def _service(store):
    """Build a CatalogService over the store, or None when the store has no
    Mongo `_db` (e.g. a bare MemoryStore)."""
    db = getattr(store, "_db", None)
    if db is None:
        return None
    from facetwork.catalog import CatalogService, MongoCatalogStore

    return CatalogService(MongoCatalogStore(db), store)


def _parse_version(raw: str | None) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@router.get("")
def catalog_list(request: Request, q: str = "", package: str = "", store=Depends(get_store)):
    """Catalog browser with three modes:

    - ``?q=`` — ranked search results (flat).
    - ``?package=<slug>`` — the workflows belonging to one library/package (flat).
    - neither — a grouped overview: packages/libraries (with member counts),
      standalone workflows, and a per-package workflow tally.
    """
    svc = _service(store)
    ctx: dict = {
        "q": q,
        "package": package,
        "unavailable": svc is None,
        "active_tab": "catalog",
    }
    if svc is None:
        ctx["flat"] = True
        ctx["entries"] = []
        return request.app.state.templates.TemplateResponse(request, "catalog/list.html", ctx)

    if q:
        ctx["flat"] = True
        ctx["entries"] = svc.search(q)
        return request.app.state.templates.TemplateResponse(request, "catalog/list.html", ctx)

    rows = svc.list_all()
    if package:
        ctx["flat"] = True
        ctx["entries"] = [s for s in rows if s.get("package") == package]
        return request.app.state.templates.TemplateResponse(request, "catalog/list.html", ctx)

    counts: dict[str, int] = {}
    for s in rows:
        if s["kind"] == "workflow" and s.get("package"):
            counts[s["package"]] = counts.get(s["package"], 0) + 1
    ctx.update(
        flat=False,
        libraries=[s for s in rows if s["kind"] == "library"],
        standalone=[s for s in rows if s["kind"] == "workflow" and not s.get("package")],
        package_counts=sorted(counts.items()),
        total=len(rows),
    )
    return request.app.state.templates.TemplateResponse(request, "catalog/list.html", ctx)


@router.get("/{slug}")
def catalog_detail(
    request: Request, slug: str, version: str | None = None, error: str = "", store=Depends(get_store)
):
    """Show one catalog entry + a revision (FFL, params, deps, versions)."""
    svc = _service(store)
    detail = svc.get(slug, _parse_version(version)) if svc else None
    default_inputs = {}
    if detail:
        for p in detail.get("param_schema", []) or []:
            default_inputs[p["name"]] = p.get("default")
    return request.app.state.templates.TemplateResponse(
        request,
        "catalog/detail.html",
        {
            "d": detail,
            "slug": slug,
            "error": error,
            "default_inputs_json": json.dumps(default_inputs, indent=2, default=str),
            "unavailable": svc is None,
            "active_tab": "catalog",
        },
    )


@router.post("/{slug}/publish")
def catalog_publish(
    request: Request, slug: str, version: str = Form(""), store=Depends(get_store)
):
    """Publish (review-approve) a revision so it can run unattended."""
    svc = _service(store)
    if svc is not None:
        try:
            svc.publish(slug, _parse_version(version))
        except Exception as e:
            return RedirectResponse(f"/catalog/{slug}?error={str(e)[:200]}", status_code=303)
    return RedirectResponse(f"/catalog/{slug}", status_code=303)


@router.post("/{slug}/run")
def catalog_run(
    request: Request,
    slug: str,
    version: str = Form(""),
    inputs_json: str = Form("{}"),
    allow_unpublished: str = Form(""),
    store=Depends(get_store),
):
    """Pin a revision and submit a bootstrap run with the given inputs."""
    svc = _service(store)
    if svc is None:
        return RedirectResponse(f"/catalog/{slug}?error=catalog+unavailable", status_code=303)
    try:
        inputs = json.loads(inputs_json) if inputs_json.strip() else {}
    except json.JSONDecodeError as e:
        return RedirectResponse(f"/catalog/{slug}?error=bad+inputs+JSON:+{e}", status_code=303)
    try:
        res = svc.run(
            slug,
            version=_parse_version(version),
            inputs=inputs,
            allow_unpublished=bool(allow_unpublished),
        )
    except Exception as e:
        return RedirectResponse(f"/catalog/{slug}?error={str(e)[:200]}", status_code=303)
    return RedirectResponse(f"/runners/{res['runner_id']}", status_code=303)
