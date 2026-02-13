"""Integration tests for HDFS storage against live HDFS containers.

Requires the HDFS Docker services to be running:

    docker compose --profile hdfs up -d

Run with:

    pytest tests/runtime/test_hdfs_storage.py --hdfs -v

Uses the WebHDFS REST API (port 9870) to test HDFS operations directly.
pyarrow's HadoopFileSystem requires the native libhdfs JNI library which
is typically only available in full Hadoop installations, so these tests
exercise the cluster through WebHDFS instead.
"""

import uuid
from urllib.parse import urlparse, urlunparse

import pytest
import requests

# Skip entire module unless --hdfs is passed
pytestmark = pytest.mark.skipif("not config.getoption('--hdfs')")

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


def _test_dir() -> str:
    """Return a unique HDFS directory for this test run."""
    return f"/tmp/afl-test-{uuid.uuid4().hex[:12]}"


@pytest.fixture()
def hdfs():
    """Return a WebHDFS client, skipping if the cluster is unreachable."""
    client = WebHDFSClient()
    try:
        requests.get(f"{WEBHDFS_BASE}/?op=GETFILESTATUS&user.name={HDFS_USER}", timeout=5)
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


# ---------------------------------------------------------------------------
# Cluster health
# ---------------------------------------------------------------------------


class TestHDFSClusterHealth:
    """Verify the HDFS cluster is operational before running storage tests."""

    def test_namenode_reachable(self, hdfs):
        """Namenode WebHDFS API responds."""
        s = hdfs.status("/")
        assert s is not None
        assert s["type"] == "DIRECTORY"

    def test_root_listing(self, hdfs):
        """Can list the root directory."""
        entries = hdfs.listdir("/")
        assert isinstance(entries, list)


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


class TestHDFSFileOperations:
    """Test CRUD file operations via WebHDFS."""

    def test_mkdirs(self, hdfs, workdir):
        assert hdfs.isdir(workdir) is True
        nested = f"{workdir}/a/b/c"
        hdfs.mkdirs(nested)
        assert hdfs.isdir(nested) is True

    def test_create_and_read(self, hdfs, workdir):
        path = f"{workdir}/hello.txt"
        payload = b"hello hdfs"
        hdfs.create(path, payload)
        assert hdfs.read(path) == payload

    def test_exists(self, hdfs, workdir):
        assert hdfs.exists(workdir) is True
        assert hdfs.exists(f"{workdir}/nonexistent.txt") is False

    def test_isfile(self, hdfs, workdir):
        path = f"{workdir}/file.txt"
        assert hdfs.isfile(path) is False
        hdfs.create(path, b"x")
        assert hdfs.isfile(path) is True
        assert hdfs.isfile(workdir) is False

    def test_isdir(self, hdfs, workdir):
        assert hdfs.isdir(workdir) is True
        path = f"{workdir}/file.txt"
        hdfs.create(path, b"x")
        assert hdfs.isdir(path) is False

    def test_file_size(self, hdfs, workdir):
        path = f"{workdir}/sized.txt"
        payload = b"12345"
        hdfs.create(path, payload)
        s = hdfs.status(path)
        assert s["length"] == len(payload)

    def test_modification_time(self, hdfs, workdir):
        path = f"{workdir}/mtime.txt"
        hdfs.create(path, b"x")
        s = hdfs.status(path)
        assert s["modificationTime"] > 0

    def test_overwrite(self, hdfs, workdir):
        path = f"{workdir}/overwrite.txt"
        hdfs.create(path, b"first")
        hdfs.create(path, b"second")
        assert hdfs.read(path) == b"second"


# ---------------------------------------------------------------------------
# Directory operations
# ---------------------------------------------------------------------------


class TestHDFSDirectoryOperations:
    """Test directory listing and traversal."""

    def test_listdir_files(self, hdfs, workdir):
        for name in ("a.txt", "b.txt", "c.txt"):
            hdfs.create(f"{workdir}/{name}", name.encode())
        entries = hdfs.listdir(workdir)
        names = sorted(e["pathSuffix"] for e in entries)
        assert names == ["a.txt", "b.txt", "c.txt"]

    def test_listdir_mixed(self, hdfs, workdir):
        hdfs.mkdirs(f"{workdir}/subdir")
        hdfs.create(f"{workdir}/file.txt", b"x")
        entries = hdfs.listdir(workdir)
        names = sorted(e["pathSuffix"] for e in entries)
        assert names == ["file.txt", "subdir"]
        types = {e["pathSuffix"]: e["type"] for e in entries}
        assert types["file.txt"] == "FILE"
        assert types["subdir"] == "DIRECTORY"

    def test_listdir_empty(self, hdfs, workdir):
        entries = hdfs.listdir(workdir)
        assert entries == []

    def test_nested_directories(self, hdfs, workdir):
        hdfs.mkdirs(f"{workdir}/a/b/c")
        assert hdfs.isdir(f"{workdir}/a") is True
        assert hdfs.isdir(f"{workdir}/a/b") is True
        assert hdfs.isdir(f"{workdir}/a/b/c") is True


# ---------------------------------------------------------------------------
# Delete operations
# ---------------------------------------------------------------------------


class TestHDFSDeleteOperations:
    """Test delete and recursive delete."""

    def test_delete_file(self, hdfs, workdir):
        path = f"{workdir}/to_delete.txt"
        hdfs.create(path, b"gone")
        assert hdfs.delete(path) is True
        assert hdfs.exists(path) is False

    def test_delete_nonexistent(self, hdfs, workdir):
        result = hdfs.delete(f"{workdir}/no_such_file.txt")
        assert result is False

    def test_delete_recursive(self, hdfs, workdir):
        sub = f"{workdir}/subtree"
        hdfs.mkdirs(f"{sub}/deep/nested")
        hdfs.create(f"{sub}/deep/nested/file.txt", b"data")
        hdfs.create(f"{sub}/root.txt", b"data")
        assert hdfs.delete(sub, recursive=True) is True
        assert hdfs.exists(sub) is False


# ---------------------------------------------------------------------------
# Large(r) payloads
# ---------------------------------------------------------------------------


class TestHDFSPayloads:
    """Test with non-trivial data sizes."""

    def test_medium_payload(self, hdfs, workdir):
        """Write and read back a 1 MB file."""
        path = f"{workdir}/medium.bin"
        payload = b"A" * (1024 * 1024)
        hdfs.create(path, payload)
        data = hdfs.read(path)
        assert len(data) == len(payload)
        assert data == payload

    def test_binary_payload(self, hdfs, workdir):
        """Write and read back binary data with all byte values."""
        path = f"{workdir}/binary.bin"
        payload = bytes(range(256)) * 100
        hdfs.create(path, payload)
        assert hdfs.read(path) == payload
