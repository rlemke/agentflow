#!/usr/bin/env python3
"""Tests for the standalone OSM downloader module.

All tests are offline — HTTP requests and filesystem access are mocked.

    PYTHONPATH=. python -m pytest examples/osm-geocoder/test_downloader.py -v
"""

import os
import sys
from unittest import mock

import pytest

# The example directory uses hyphens, so add it to sys.path for direct import.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from handlers.downloader import (  # noqa: E402
    CACHE_DIR,
    GEOFABRIK_BASE,
    cache_path,
    download,
    geofabrik_url,
)

MODULE = "handlers.downloader"


class TestGeofabrikUrl:
    def test_simple_region(self):
        assert geofabrik_url("africa/algeria") == (
            f"{GEOFABRIK_BASE}/africa/algeria-latest.osm.pbf"
        )

    def test_nested_region(self):
        assert geofabrik_url("north-america/us/california") == (
            f"{GEOFABRIK_BASE}/north-america/us/california-latest.osm.pbf"
        )

    def test_continent(self):
        assert geofabrik_url("antarctica") == (f"{GEOFABRIK_BASE}/antarctica-latest.osm.pbf")


class TestGeofabrikUrlShapefile:
    def test_simple_region_shp(self):
        assert geofabrik_url("africa/algeria", fmt="shp") == (
            f"{GEOFABRIK_BASE}/africa/algeria-latest.free.shp.zip"
        )

    def test_nested_region_shp(self):
        assert geofabrik_url("north-america/us/california", fmt="shp") == (
            f"{GEOFABRIK_BASE}/north-america/us/california-latest.free.shp.zip"
        )

    def test_continent_shp(self):
        assert geofabrik_url("antarctica", fmt="shp") == (
            f"{GEOFABRIK_BASE}/antarctica-latest.free.shp.zip"
        )


class TestCachePath:
    def test_simple_region(self):
        result = cache_path("africa/algeria")
        assert result == os.path.join(CACHE_DIR, "africa/algeria-latest.osm.pbf")

    def test_nested_region(self):
        result = cache_path("north-america/us/california")
        assert result == os.path.join(CACHE_DIR, "north-america/us/california-latest.osm.pbf")

    def test_continent(self):
        result = cache_path("antarctica")
        assert result == os.path.join(CACHE_DIR, "antarctica-latest.osm.pbf")


class TestCachePathShapefile:
    def test_simple_region_shp(self):
        result = cache_path("africa/algeria", fmt="shp")
        assert result == os.path.join(CACHE_DIR, "africa/algeria-latest.free.shp.zip")

    def test_nested_region_shp(self):
        result = cache_path("north-america/us/california", fmt="shp")
        assert result == os.path.join(CACHE_DIR, "north-america/us/california-latest.free.shp.zip")

    def test_continent_shp(self):
        result = cache_path("antarctica", fmt="shp")
        assert result == os.path.join(CACHE_DIR, "antarctica-latest.free.shp.zip")


class TestDownloadCacheHit:
    """When the file already exists locally, no HTTP request is made."""

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=5000)
    @mock.patch(f"{MODULE}.os.path.exists", return_value=True)
    def test_returns_cache_hit(self, mock_exists, mock_getsize):
        result = download("africa/algeria")

        assert result["wasInCache"] is True
        assert result["size"] == 5000
        assert result["url"] == geofabrik_url("africa/algeria")
        assert result["path"] == cache_path("africa/algeria")
        assert "date" in result

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=5000)
    @mock.patch(f"{MODULE}.os.path.exists", return_value=True)
    @mock.patch(f"{MODULE}.requests.get")
    def test_no_http_request(self, mock_get, mock_exists, mock_getsize):
        download("africa/algeria")
        mock_get.assert_not_called()


class TestDownloadCacheMiss:
    """When the file is not cached, it is downloaded via HTTP."""

    def _setup_mocks(self, mock_get):
        mock_response = mock.Mock()
        mock_response.iter_content.return_value = [b"fake-pbf-data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        return mock_response

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=13)
    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_returns_cache_miss(
        self, mock_exists, mock_get, mock_open, mock_makedirs, mock_getsize
    ):
        self._setup_mocks(mock_get)

        result = download("africa/algeria")

        assert result["wasInCache"] is False
        assert result["size"] == 13
        assert result["url"] == geofabrik_url("africa/algeria")
        assert result["path"] == cache_path("africa/algeria")

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=13)
    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_streams_to_file(self, mock_exists, mock_get, mock_open, mock_makedirs, mock_getsize):
        self._setup_mocks(mock_get)

        download("africa/algeria")

        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["stream"] is True
        mock_open().write.assert_called_once_with(b"fake-pbf-data")

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=13)
    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_creates_parent_directories(
        self, mock_exists, mock_get, mock_open, mock_makedirs, mock_getsize
    ):
        self._setup_mocks(mock_get)

        download("north-america/us/california")

        expected_dir = os.path.dirname(cache_path("north-america/us/california"))
        mock_makedirs.assert_called_once_with(expected_dir, exist_ok=True)

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=13)
    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_sets_user_agent(self, mock_exists, mock_get, mock_open, mock_makedirs, mock_getsize):
        self._setup_mocks(mock_get)

        download("africa/algeria")

        headers = mock_get.call_args.kwargs["headers"]
        assert headers["User-Agent"] == "AgentFlow-OSM-Example/1.0"


class TestDownloadHttpError:
    """HTTP errors propagate as exceptions."""

    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_raises_on_http_error(self, mock_exists, mock_get, mock_makedirs):
        import requests

        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError, match="404 Not Found"):
            download("nonexistent/region")


class TestDownloadShapefileCacheHit:
    """Shapefile format: when the file already exists locally."""

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=12000)
    @mock.patch(f"{MODULE}.os.path.exists", return_value=True)
    def test_returns_cache_hit_shp(self, mock_exists, mock_getsize):
        result = download("africa/algeria", fmt="shp")

        assert result["wasInCache"] is True
        assert result["size"] == 12000
        assert result["url"] == geofabrik_url("africa/algeria", fmt="shp")
        assert result["path"] == cache_path("africa/algeria", fmt="shp")
        assert "date" in result


class TestDownloadShapefileCacheMiss:
    """Shapefile format: when the file is not cached."""

    def _setup_mocks(self, mock_get):
        mock_response = mock.Mock()
        mock_response.iter_content.return_value = [b"fake-shp-data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        return mock_response

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=13)
    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_returns_cache_miss_shp(
        self, mock_exists, mock_get, mock_open, mock_makedirs, mock_getsize
    ):
        self._setup_mocks(mock_get)

        result = download("africa/algeria", fmt="shp")

        assert result["wasInCache"] is False
        assert result["url"] == geofabrik_url("africa/algeria", fmt="shp")
        assert result["path"] == cache_path("africa/algeria", fmt="shp")

    @mock.patch(f"{MODULE}.os.path.getsize", return_value=13)
    @mock.patch(f"{MODULE}.os.makedirs")
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch(f"{MODULE}.requests.get")
    @mock.patch(f"{MODULE}.os.path.exists", return_value=False)
    def test_requests_shp_url(self, mock_exists, mock_get, mock_open, mock_makedirs, mock_getsize):
        self._setup_mocks(mock_get)

        download("africa/algeria", fmt="shp")

        called_url = mock_get.call_args[0][0]
        assert called_url.endswith("-latest.free.shp.zip")
