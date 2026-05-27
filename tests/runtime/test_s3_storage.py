"""Tests for the S3 / MinIO storage backend.

Two tiers:

* **Path helpers + dispatch** — always run (boto3 client creation is lazy and
  makes no network call), so ``s3://`` URI parsing/joining and backend
  selection are covered without any server.
* **Live round-trip** — opt-in, gated on ``AFL_S3_ENDPOINT`` pointing at a
  reachable S3/MinIO. Start one with::

      docker run -d -p 9000:9000 -e MINIO_ROOT_USER=minioadmin \\
          -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data
      export AFL_S3_ENDPOINT=http://localhost:9000 \\
          AFL_S3_ACCESS_KEY=minioadmin AFL_S3_SECRET_KEY=minioadmin
"""

from __future__ import annotations

import os
import uuid

import pytest

boto3 = pytest.importorskip("boto3")

from facetwork.runtime.storage import (  # noqa: E402
    S3StorageBackend,
    get_storage_backend,
    localize,
)

_LIVE = bool(os.environ.get("AFL_S3_ENDPOINT"))
_live_only = pytest.mark.skipif(not _LIVE, reason="set AFL_S3_ENDPOINT to run live S3/MinIO tests")
_BUCKET = os.environ.get("AFL_S3_TEST_BUCKET", "afl-cache")


# --- path helpers + dispatch (no network) -------------------------------------


def test_dispatch_returns_s3_backend():
    assert isinstance(get_storage_backend("s3://bucket/key"), S3StorageBackend)


def test_path_helpers():
    b = S3StorageBackend()
    assert b._split("s3://bkt/a/b/c.json") == ("bkt", "a/b/c.json")
    assert b.join("s3://bkt/a", "b", "c.json") == "s3://bkt/a/b/c.json"
    assert b.join("s3://bkt/a/", "/b/", "c") == "s3://bkt/a/b/c"
    assert b.dirname("s3://bkt/a/b/c.json") == "s3://bkt/a/b"
    assert b.dirname("s3://bkt/top") == "s3://bkt"
    assert b.basename("s3://bkt/a/b/c.json") == "c.json"


# --- live round-trip (MinIO) --------------------------------------------------


@_live_only
def test_live_roundtrip(tmp_path):
    b = get_storage_backend("s3://x")
    prefix = f"s3://{_BUCKET}/_pytest/{uuid.uuid4().hex}"
    try:
        with b.open(f"{prefix}/dir/a.txt", "w") as f:
            f.write("hello-s3")
        with b.open(f"{prefix}/dir/sub/b.txt", "w") as f:
            f.write("nested")

        assert b.exists(f"{prefix}/dir/a.txt") is True
        assert b.isfile(f"{prefix}/dir/a.txt") is True
        assert b.isdir(f"{prefix}/dir") is True
        assert b.isfile(f"{prefix}/dir") is False
        assert b.open(f"{prefix}/dir/a.txt").read() == "hello-s3"
        assert b.getsize(f"{prefix}/dir/a.txt") == len("hello-s3")
        assert set(b.listdir(f"{prefix}/dir")) == {"a.txt", "sub"}

        local = localize(f"{prefix}/dir/a.txt", target_dir=str(tmp_path))
        assert open(local).read() == "hello-s3"
    finally:
        b.rmtree(prefix)
        assert b.isdir(prefix) is False
