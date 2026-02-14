"""Visualization event facet handlers for GeoJSON map rendering.

Handles visualization events defined in osmvisualization.afl under osm.geo.Visualization.
"""

import logging
import os
from datetime import datetime, timezone

from .map_renderer import (
    HAS_FOLIUM,
    HAS_STATIC,
    LayerStyle,
    MapResult,
    preview_map,
    render_layers,
    render_map,
)

log = logging.getLogger(__name__)

NAMESPACE = "osm.geo.Visualization"


def _make_render_map_handler(facet_name: str):
    """Create handler for RenderMap event facet."""

    def handler(payload: dict) -> dict:
        geojson_path = payload.get("geojson_path", "")
        title = payload.get("title", "Map")
        format = payload.get("format", "html")
        width = payload.get("width", 800)
        height = payload.get("height", 600)
        color = payload.get("color", "#3388ff")
        fill_opacity = payload.get("fill_opacity", 0.4)

        log.info("%s rendering %s as %s", facet_name, geojson_path, format)

        if not geojson_path:
            return {"result": _empty_result(title, format)}

        if format == "html" and not HAS_FOLIUM:
            log.error("folium not installed, cannot render HTML map")
            return {"result": _empty_result(title, format)}

        if format == "png" and not HAS_STATIC:
            log.error("geopandas/contextily not installed, cannot render PNG")
            return {"result": _empty_result(title, format)}

        try:
            style = LayerStyle(color=color, fill_opacity=fill_opacity)
            result = render_map(
                geojson_path,
                title=title,
                format=format,
                style=style,
                width=width,
                height=height,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to render map: %s", e)
            return {"result": _empty_result(title, format)}

    return handler


def _make_render_map_at_handler(facet_name: str):
    """Create handler for RenderMapAt event facet."""

    def handler(payload: dict) -> dict:
        geojson_path = payload.get("geojson_path", "")
        lat = payload.get("lat", 0.0)
        lon = payload.get("lon", 0.0)
        zoom = payload.get("zoom", 10)
        title = payload.get("title", "Map")

        log.info("%s rendering %s at (%.4f, %.4f) zoom %d",
                 facet_name, geojson_path, lat, lon, zoom)

        if not geojson_path:
            return {"result": _empty_result(title, "html")}

        if not HAS_FOLIUM:
            log.error("folium not installed")
            return {"result": _empty_result(title, "html")}

        try:
            result = render_map(
                geojson_path,
                title=title,
                format="html",
                center=(lat, lon),
                zoom=zoom,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to render map: %s", e)
            return {"result": _empty_result(title, "html")}

    return handler


def _make_render_layers_handler(facet_name: str):
    """Create handler for RenderLayers event facet."""

    def handler(payload: dict) -> dict:
        layers = payload.get("layers", [])
        colors = payload.get("colors", [])
        title = payload.get("title", "Map")
        format = payload.get("format", "html")

        # Normalize layers to list
        if isinstance(layers, str):
            layers = [l.strip() for l in layers.split(",") if l.strip()]
        if isinstance(colors, str):
            colors = [c.strip() for c in colors.split(",") if c.strip()]

        log.info("%s rendering %d layers", facet_name, len(layers))

        if not layers:
            return {"result": _empty_result(title, format)}

        if not HAS_FOLIUM:
            log.error("folium not installed")
            return {"result": _empty_result(title, format)}

        try:
            result = render_layers(
                layers,
                colors=colors if colors else None,
                title=title,
                format=format,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to render layers: %s", e)
            return {"result": _empty_result(title, format)}

    return handler


def _make_render_styled_map_handler(facet_name: str):
    """Create handler for RenderStyledMap event facet."""

    def handler(payload: dict) -> dict:
        geojson_path = payload.get("geojson_path", "")
        style_dict = payload.get("style", {})
        title = payload.get("title", "Map")

        log.info("%s rendering %s with custom style", facet_name, geojson_path)

        if not geojson_path:
            return {"result": _empty_result(title, "html")}

        if not HAS_FOLIUM:
            log.error("folium not installed")
            return {"result": _empty_result(title, "html")}

        try:
            style = LayerStyle(
                color=style_dict.get("color", "#3388ff"),
                fill_color=style_dict.get("fill_color"),
                weight=style_dict.get("weight", 2),
                opacity=style_dict.get("opacity", 1.0),
                fill_opacity=style_dict.get("fill_opacity", 0.4),
            )
            result = render_map(
                geojson_path,
                title=title,
                format="html",
                style=style,
            )
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to render styled map: %s", e)
            return {"result": _empty_result(title, "html")}

    return handler


def _make_preview_map_handler(facet_name: str):
    """Create handler for PreviewMap event facet."""

    def handler(payload: dict) -> dict:
        geojson_path = payload.get("geojson_path", "")

        log.info("%s previewing %s", facet_name, geojson_path)

        if not geojson_path:
            return {"result": _empty_result("Preview", "html")}

        if not HAS_FOLIUM:
            log.error("folium not installed")
            return {"result": _empty_result("Preview", "html")}

        try:
            result = preview_map(geojson_path)
            return {"result": _result_to_dict(result)}
        except Exception as e:
            log.error("Failed to preview map: %s", e)
            return {"result": _empty_result("Preview", "html")}

    return handler


def _result_to_dict(result: MapResult) -> dict:
    """Convert a MapResult to a dictionary."""
    return {
        "output_path": result.output_path,
        "format": result.format,
        "feature_count": result.feature_count,
        "bounds": result.bounds,
        "title": result.title,
        "extraction_date": result.extraction_date,
    }


def _empty_result(title: str, format: str) -> dict:
    """Return an empty result dict."""
    return {
        "output_path": "",
        "format": format,
        "feature_count": 0,
        "bounds": "",
        "title": title,
        "extraction_date": datetime.now(timezone.utc).isoformat(),
    }


# Event facet definitions for handler registration
VISUALIZATION_FACETS = [
    ("RenderMap", _make_render_map_handler),
    ("RenderMapAt", _make_render_map_at_handler),
    ("RenderLayers", _make_render_layers_handler),
    ("RenderStyledMap", _make_render_styled_map_handler),
    ("PreviewMap", _make_preview_map_handler),
]


# RegistryRunner dispatch adapter
_DISPATCH: dict[str, callable] = {}


def _build_dispatch() -> None:
    for facet_name, handler_factory in VISUALIZATION_FACETS:
        _DISPATCH[f"{NAMESPACE}.{facet_name}"] = handler_factory(facet_name)


_build_dispatch()


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_visualization_handlers(poller) -> None:
    """Register all visualization event facet handlers with the poller."""
    for facet_name, handler_factory in VISUALIZATION_FACETS:
        qualified_name = f"{NAMESPACE}.{facet_name}"
        poller.register(qualified_name, handler_factory(facet_name))
        log.debug("Registered visualization handler: %s", qualified_name)
