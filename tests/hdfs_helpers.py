"""Shared WebHDFS test helpers.

Provides a minimal ``WebHDFSClient`` and reusable pytest fixtures for HDFS
integration tests.  Both ``tests/runtime/test_hdfs_storage.py`` and
``tests/test_osm_handlers_hdfs.py`` import from this module.
"""

import uuid
from urllib.parse import urlparse, urlunparse

import pytest
import requests

WEBHDFS_BASE = "http://localhost:9870/webhdfs/v1"
HDFS_USER = "root"


class WebHDFSClient:
    """Minimal WebHDFS client for integration testing.

    Rewrites redirect URLs so that container-internal hostnames
    (e.g. ``datanode``) become ``localhost``, allowing the test runner
    on the Docker host to follow WebHDFS two-step redirects.
    """

    def __init__(self, base_url: str = WEBHDFS_BASE, user: str = HDFS_USER):
        self.base_url = base_url
        self.user = user

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _params(self, **kwargs) -> dict:
        return {"user.name": self.user, **kwargs}

    @staticmethod
    def _localize_redirect(url: str) -> str:
        """Rewrite a redirect URL so container hostnames become localhost."""
        parsed = urlparse(url)
        if parsed.hostname != "localhost":
            parsed = parsed._replace(netloc=f"localhost:{parsed.port}")
        return urlunparse(parsed)

    def mkdirs(self, path: str) -> bool:
        r = requests.put(
            self._url(path), params=self._params(op="MKDIRS"), allow_redirects=True
        )
        r.raise_for_status()
        return r.json()["boolean"]

    def create(self, path: str, data: bytes) -> None:
        # WebHDFS CREATE is a two-step redirect to the datanode
        r = requests.put(
            self._url(path),
            params=self._params(op="CREATE", overwrite="true"),
            allow_redirects=False,
        )
        r.raise_for_status()
        assert r.status_code == 307, f"Expected redirect, got {r.status_code}"
        location = self._localize_redirect(r.headers["Location"])
        r2 = requests.put(location, data=data)
        r2.raise_for_status()

    def read(self, path: str) -> bytes:
        # OPEN also redirects to the datanode; handle manually
        r = requests.get(
            self._url(path),
            params=self._params(op="OPEN"),
            allow_redirects=False,
        )
        r.raise_for_status()
        if r.status_code == 307:
            location = self._localize_redirect(r.headers["Location"])
            r = requests.get(location)
            r.raise_for_status()
        return r.content

    def status(self, path: str) -> dict | None:
        r = requests.get(
            self._url(path), params=self._params(op="GETFILESTATUS")
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["FileStatus"]

    def listdir(self, path: str) -> list[dict]:
        r = requests.get(
            self._url(path), params=self._params(op="LISTSTATUS")
        )
        r.raise_for_status()
        return r.json()["FileStatuses"]["FileStatus"]

    def delete(self, path: str, recursive: bool = False) -> bool:
        r = requests.delete(
            self._url(path),
            params=self._params(op="DELETE", recursive=str(recursive).lower()),
        )
        r.raise_for_status()
        return r.json()["boolean"]

    def exists(self, path: str) -> bool:
        return self.status(path) is not None

    def isfile(self, path: str) -> bool:
        s = self.status(path)
        return s is not None and s["type"] == "FILE"

    def isdir(self, path: str) -> bool:
        s = self.status(path)
        return s is not None and s["type"] == "DIRECTORY"

    def getsize(self, path: str) -> int:
        s = self.status(path)
        if s is None:
            raise FileNotFoundError(path)
        return s["length"]


def _test_dir() -> str:
    """Return a unique HDFS directory for this test run."""
    return f"/tmp/afl-test-{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def hdfs():
    """Return a WebHDFS client, skipping if the cluster is unreachable."""
    client = WebHDFSClient()
    try:
        requests.get(
            f"{WEBHDFS_BASE}/?op=GETFILESTATUS&user.name={HDFS_USER}", timeout=5
        )
    except requests.ConnectionError:
        pytest.skip("HDFS namenode not reachable on localhost:9870")
    return client


@pytest.fixture()
def workdir(hdfs):
    """Create a unique working directory on HDFS; clean up after the test."""
    path = _test_dir()
    hdfs.mkdirs(path)
    yield path
    hdfs.delete(path, recursive=True)
