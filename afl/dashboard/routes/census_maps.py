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

"""Census data map visualization routes."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..dependencies import get_store

router = APIRouter(prefix="/census")


@router.get("/maps")
def census_map_list(request: Request, store=Depends(get_store)):
    """List handler_output_meta entries that have GeoJSON geometry."""
    db = store._db
    metas = list(
        db.handler_output_meta.find(
            {"data_type": "geojson_feature"},
        ).sort("dataset_key", 1)
    )
    for m in metas:
        m.pop("_id", None)

    return request.app.state.templates.TemplateResponse(
        request,
        "census/maps.html",
        {"datasets": metas, "active_tab": "census_maps"},
    )


@router.get("/maps/{dataset_key:path}")
def census_map_view(
    dataset_key: str,
    request: Request,
    store=Depends(get_store),
):
    """Render a Leaflet map for a single dataset's GeoJSON features."""
    db = store._db
    docs = list(db.handler_output.find({"dataset_key": dataset_key}))

    features: list[dict[str, Any]] = []
    for doc in docs:
        geom = doc.get("geometry")
        props = doc.get("properties", {})
        if geom:
            features.append({"type": "Feature", "geometry": geom, "properties": props})

    geojson: dict[str, Any] = {"type": "FeatureCollection", "features": features}

    # Identify numeric property fields for the choropleth dropdown.
    numeric_fields: list[str] = []
    if features:
        sample = features[0].get("properties", {})
        for key, val in sample.items():
            if isinstance(val, (int, float)):
                numeric_fields.append(key)

    geojson_str = json.dumps(geojson)

    return request.app.state.templates.TemplateResponse(
        request,
        "census/map_view.html",
        {
            "dataset_key": dataset_key,
            "geojson_str": geojson_str,
            "feature_count": len(features),
            "numeric_fields": numeric_fields,
            "active_tab": "census_maps",
        },
    )


@router.get("/api/maps/{dataset_key:path}")
def census_map_api(
    dataset_key: str,
    store=Depends(get_store),
):
    """Return raw GeoJSON FeatureCollection as JSON."""
    db = store._db
    docs = list(db.handler_output.find({"dataset_key": dataset_key}))

    features: list[dict[str, Any]] = []
    for doc in docs:
        geom = doc.get("geometry")
        props = doc.get("properties", {})
        if geom:
            features.append({"type": "Feature", "geometry": geom, "properties": props})

    return JSONResponse({"type": "FeatureCollection", "features": features})
