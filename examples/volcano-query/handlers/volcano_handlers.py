"""Volcano query handlers with built-in USGS volcano dataset.

Provides ~30 notable US volcanoes with real name, state, elevation,
type, and coordinate data. No external API calls needed.

Each handler implements ONE atomic operation:
- CheckRegionCache: check if volcano data is cached for a region
- DownloadVolcanoData: download/load raw volcano data
- FilterByType: filter volcanoes by type
- FilterByRegion: filter by state name
- FilterByElevation: filter by minimum elevation
- FormatVolcanoes: format as human-readable text
- RenderMap: generate simple HTML map
"""

import json
import logging

log = logging.getLogger(__name__)

NAMESPACE = "volcano"

# Built-in dataset of notable US volcanoes (source: USGS Volcano Hazards Program)
US_VOLCANOES = [
    # California
    {"name": "Mount Shasta", "state": "California", "elevation_ft": 14179, "type": "Stratovolcano", "latitude": "41.4092", "longitude": "-122.1949"},
    {"name": "Lassen Peak", "state": "California", "elevation_ft": 10457, "type": "Lava dome", "latitude": "40.4882", "longitude": "-121.5049"},
    {"name": "Medicine Lake", "state": "California", "elevation_ft": 7913, "type": "Shield volcano", "latitude": "41.6108", "longitude": "-121.5541"},
    {"name": "Mammoth Mountain", "state": "California", "elevation_ft": 11053, "type": "Lava dome", "latitude": "37.6311", "longitude": "-119.0325"},
    {"name": "Mono Craters", "state": "California", "elevation_ft": 9172, "type": "Lava domes", "latitude": "37.8800", "longitude": "-119.0000"},
    {"name": "Clear Lake Volcanic Field", "state": "California", "elevation_ft": 4544, "type": "Volcanic field", "latitude": "38.9700", "longitude": "-122.7700"},
    # Washington
    {"name": "Mount Rainier", "state": "Washington", "elevation_ft": 14411, "type": "Stratovolcano", "latitude": "46.8529", "longitude": "-121.7604"},
    {"name": "Mount St. Helens", "state": "Washington", "elevation_ft": 8363, "type": "Stratovolcano", "latitude": "46.1914", "longitude": "-122.1956"},
    {"name": "Mount Adams", "state": "Washington", "elevation_ft": 12281, "type": "Stratovolcano", "latitude": "46.2024", "longitude": "-121.4909"},
    {"name": "Mount Baker", "state": "Washington", "elevation_ft": 10781, "type": "Stratovolcano", "latitude": "48.7768", "longitude": "-121.8145"},
    {"name": "Glacier Peak", "state": "Washington", "elevation_ft": 10541, "type": "Stratovolcano", "latitude": "48.1120", "longitude": "-121.1139"},
    # Oregon
    {"name": "Mount Hood", "state": "Oregon", "elevation_ft": 11249, "type": "Stratovolcano", "latitude": "45.3735", "longitude": "-121.6960"},
    {"name": "Mount Jefferson", "state": "Oregon", "elevation_ft": 10497, "type": "Stratovolcano", "latitude": "44.6742", "longitude": "-121.7999"},
    {"name": "South Sister", "state": "Oregon", "elevation_ft": 10358, "type": "Stratovolcano", "latitude": "44.1033", "longitude": "-121.7692"},
    {"name": "Crater Lake", "state": "Oregon", "elevation_ft": 8159, "type": "Caldera", "latitude": "42.9446", "longitude": "-122.1090"},
    {"name": "Newberry Volcano", "state": "Oregon", "elevation_ft": 7985, "type": "Shield volcano", "latitude": "43.7221", "longitude": "-121.2290"},
    {"name": "Mount McLoughlin", "state": "Oregon", "elevation_ft": 9495, "type": "Stratovolcano", "latitude": "42.3747", "longitude": "-122.3152"},
    # Hawaii
    {"name": "Mauna Kea", "state": "Hawaii", "elevation_ft": 13796, "type": "Shield volcano", "latitude": "19.8207", "longitude": "-155.4680"},
    {"name": "Mauna Loa", "state": "Hawaii", "elevation_ft": 13681, "type": "Shield volcano", "latitude": "19.4756", "longitude": "-155.6054"},
    {"name": "Kilauea", "state": "Hawaii", "elevation_ft": 4091, "type": "Shield volcano", "latitude": "19.4069", "longitude": "-155.2834"},
    {"name": "Haleakala", "state": "Hawaii", "elevation_ft": 10023, "type": "Shield volcano", "latitude": "20.7097", "longitude": "-156.2533"},
    {"name": "Hualalai", "state": "Hawaii", "elevation_ft": 8271, "type": "Shield volcano", "latitude": "19.6914", "longitude": "-155.8675"},
    # Alaska
    {"name": "Mount Wrangell", "state": "Alaska", "elevation_ft": 14163, "type": "Shield volcano", "latitude": "62.0059", "longitude": "-144.0187"},
    {"name": "Mount Redoubt", "state": "Alaska", "elevation_ft": 10197, "type": "Stratovolcano", "latitude": "60.4854", "longitude": "-152.7420"},
    {"name": "Mount Shishaldin", "state": "Alaska", "elevation_ft": 9373, "type": "Stratovolcano", "latitude": "54.7561", "longitude": "-163.9706"},
    {"name": "Mount Pavlof", "state": "Alaska", "elevation_ft": 8261, "type": "Stratovolcano", "latitude": "55.4173", "longitude": "-161.8937"},
    {"name": "Mount Spurr", "state": "Alaska", "elevation_ft": 11070, "type": "Stratovolcano", "latitude": "61.2989", "longitude": "-152.2511"},
    # Wyoming
    {"name": "Yellowstone Caldera", "state": "Wyoming", "elevation_ft": 9203, "type": "Caldera", "latitude": "44.4280", "longitude": "-110.5885"},
    # New Mexico
    {"name": "Valles Caldera", "state": "New Mexico", "elevation_ft": 11254, "type": "Caldera", "latitude": "35.8700", "longitude": "-106.5700"},
]


def check_region_cache_handler(payload: dict) -> dict:
    """Check if volcano data is cached for the given region."""
    region = payload.get("region", "US")
    cache_path = f"/data/volcanoes/{region.lower()}.json"
    log.info("CheckRegionCache: region=%s, path=%s (always cached)", region, cache_path)
    return {
        "result": {
            "region": region,
            "path": cache_path,
            "cached": True,
        }
    }


def download_volcano_data_handler(payload: dict) -> dict:
    """Download/load raw volcano data for the given region."""
    region = payload.get("region", "US")
    cache_path = payload.get("cache_path", "")
    log.info("DownloadVolcanoData: region=%s, cache_path=%s, returning %d volcanoes",
             region, cache_path, len(US_VOLCANOES))
    return {
        "result": {
            "volcanoes": json.dumps(US_VOLCANOES),
        }
    }


def filter_by_type_handler(payload: dict) -> dict:
    """Filter volcanoes by volcano type."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    volcano_type = payload.get("volcano_type", "all")

    if isinstance(volcanoes_raw, str):
        volcanoes = json.loads(volcanoes_raw)
    else:
        volcanoes = volcanoes_raw

    if volcano_type.lower() == "all":
        matches = volcanoes
    else:
        matches = [v for v in volcanoes if v["type"].lower() == volcano_type.lower()]

    log.info("FilterByType: %d matches for type=%s", len(matches), volcano_type)

    return {
        "result": {
            "volcanoes": json.dumps(matches),
        }
    }


def filter_by_region_handler(payload: dict) -> dict:
    """Filter volcanoes by state name."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    state = payload.get("state", "")

    if isinstance(volcanoes_raw, str):
        volcanoes = json.loads(volcanoes_raw)
    else:
        volcanoes = volcanoes_raw

    matches = [v for v in volcanoes if v["state"].lower() == state.lower()]
    matches.sort(key=lambda v: v["elevation_ft"], reverse=True)

    log.info("FilterByRegion: %d matches for state=%s", len(matches), state)

    return {
        "result": {
            "volcanoes": json.dumps(matches),
            "count": len(matches),
        }
    }


def filter_by_elevation_handler(payload: dict) -> dict:
    """Filter volcanoes by minimum elevation."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    min_elevation = payload.get("min_elevation_ft", 0)

    if isinstance(volcanoes_raw, str):
        volcanoes = json.loads(volcanoes_raw)
    else:
        volcanoes = volcanoes_raw

    matches = [v for v in volcanoes if v["elevation_ft"] >= min_elevation]
    matches.sort(key=lambda v: v["elevation_ft"], reverse=True)

    log.info(
        "FilterByElevation: %d matches for min_elevation=%d",
        len(matches), min_elevation,
    )

    return {
        "result": {
            "volcanoes": json.dumps(matches),
            "count": len(matches),
        }
    }


def format_volcanoes_handler(payload: dict) -> dict:
    """Format a volcano list into human-readable text."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    count = payload.get("count", 0)

    if isinstance(volcanoes_raw, str):
        volcanoes = json.loads(volcanoes_raw)
    else:
        volcanoes = volcanoes_raw

    if not volcanoes:
        text = "No volcanoes found matching the criteria."
    else:
        lines = []
        for v in volcanoes:
            lines.append(
                f"  {v['name']} — {v['elevation_ft']:,} ft ({v['type']}, "
                f"{v['latitude']}N {v['longitude']}W)"
            )
        header = f"Found {count} volcano(es):\n"
        text = header + "\n".join(lines)

    log.info("FormatVolcanoes: formatted %d entries", count)

    return {
        "result": {
            "text": text,
            "count": count,
        }
    }


def render_map_handler(payload: dict) -> dict:
    """Generate a simple HTML page with volcano markers."""
    volcanoes_raw = payload.get("volcanoes", "[]")
    title = payload.get("title", "Volcano Map")

    if isinstance(volcanoes_raw, str):
        volcanoes = json.loads(volcanoes_raw)
    else:
        volcanoes = volcanoes_raw

    rows = []
    for v in volcanoes:
        rows.append(
            f"<tr><td>{v['name']}</td><td>{v['elevation_ft']:,} ft</td>"
            f"<td>{v['latitude']}, {v['longitude']}</td></tr>"
        )
    table_body = "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
<table border="1">
<tr><th>Name</th><th>Elevation</th><th>Coordinates</th></tr>
{table_body}
</table>
</body>
</html>"""

    log.info("RenderMap: generated map for %d volcanoes", len(volcanoes))

    return {
        "result": {
            "html": html,
            "title": title,
        }
    }


def register_volcano_handlers(poller) -> None:
    """Register all volcano event facet handlers with the given poller."""
    poller.register(f"{NAMESPACE}.CheckRegionCache", check_region_cache_handler)
    poller.register(f"{NAMESPACE}.DownloadVolcanoData", download_volcano_data_handler)
    poller.register(f"{NAMESPACE}.FilterByType", filter_by_type_handler)
    poller.register(f"{NAMESPACE}.FilterByRegion", filter_by_region_handler)
    poller.register(f"{NAMESPACE}.FilterByElevation", filter_by_elevation_handler)
    poller.register(f"{NAMESPACE}.FormatVolcanoes", format_volcanoes_handler)
    poller.register(f"{NAMESPACE}.RenderMap", render_map_handler)
