"""Ingest handlers for the noaa-weather example."""

from __future__ import annotations

import os
import time
from typing import Any

from handlers.shared.weather_utils import (
    ISD_LITE_URL_TEMPLATE,
    download_isd_lite,
    parse_isd_lite_file,
)

NAMESPACE = "weather.Ingest"


def _step_log_append(step_log, msg: str, level: str = "info") -> None:
    """Write a message to the step log (callable or list form)."""
    if step_log is None:
        return
    if callable(step_log):
        step_log(msg, level)
    else:
        step_log.append({"message": msg, "level": level})


def handle_download_observations(params: dict[str, Any]) -> dict[str, Any]:
    """Handle DownloadObservations event facet."""
    usaf = params.get("usaf", "")
    wban = params.get("wban", "")
    year = params.get("year", 2023)
    if isinstance(year, str):
        year = int(year)

    station_id = f"{usaf}-{wban}"
    step_log = params.get("_step_log")

    url = ISD_LITE_URL_TEMPLATE.format(year=year, usaf=usaf, wban=wban)
    _step_log_append(step_log, f"Starting download {station_id}-{year} from {url}")
    t0 = time.monotonic()
    raw_path = download_isd_lite(usaf, wban, year)
    elapsed = time.monotonic() - t0

    file_size = 0
    if os.path.exists(raw_path):
        file_size = os.path.getsize(raw_path)

    _step_log_append(
        step_log,
        f"Completed {station_id}-{year}: {file_size:,} bytes in {elapsed:.1f}s — {raw_path}",
        "success",
    )

    return {
        "raw_path": raw_path,
        "file_size": file_size,
        "station_id": station_id,
    }


def handle_parse_observations(params: dict[str, Any]) -> dict[str, Any]:
    """Handle ParseObservations event facet."""
    raw_path = params.get("raw_path", "")
    station_id = params.get("station_id", "")

    if raw_path and os.path.exists(raw_path):
        observations = parse_isd_lite_file(raw_path)
    else:
        observations = []

    step_log = params.get("_step_log")
    if step_log is not None:
        msg = f"Parsed {len(observations)} records for {station_id}"
        if callable(step_log):
            step_log(msg, "success")
        else:
            step_log.append({"message": msg, "level": "success"})

    return {
        "observations": observations,
        "record_count": len(observations),
    }


_DISPATCH: dict[str, Any] = {
    f"{NAMESPACE}.DownloadObservations": handle_download_observations,
    f"{NAMESPACE}.ParseObservations": handle_parse_observations,
}


def handle(payload: dict) -> dict:
    """RegistryRunner entrypoint."""
    facet = payload["_facet_name"]
    handler = _DISPATCH[facet]
    return handler(payload)


def register_handlers(runner) -> None:
    """Register with RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_ingest_handlers(poller) -> None:
    """Register with AgentPoller."""
    for facet_name, handler in _DISPATCH.items():
        poller.register(facet_name, handler)
