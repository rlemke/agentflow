"""Tests for afl.runtime.storage — StorageBackend abstraction layer."""

import os
from unittest.mock import MagicMock, patch

import pytest

from afl.runtime.storage import (
    HDFSStorageBackend,
    LocalStorageBackend,
    get_storage_backend,
)


# ---------------------------------------------------------------------------
# TestLocalStorageBackend
# ---------------------------------------------------------------------------

class TestLocalStorageBackend:
    """Tests for LocalStorageBackend (wraps os / builtins)."""

    def test_exists_true(self, tmp_path):
        backend = LocalStorageBackend()
        f = tmp_path / "hello.txt"
        f.write_text("hi")
        assert backend.exists(str(f)) is True

    def test_exists_false(self, tmp_path):
        backend = LocalStorageBackend()
        assert backend.exists(str(tmp_path / "nope.txt")) is False

    def test_open_write_and_read(self, tmp_path):
        backend = LocalStorageBackend()
        path = str(tmp_path / "data.txt")
        with backend.open(path, "w") as fh:
            fh.write("hello world")
        with backend.open(path, "r") as fh:
            assert fh.read() == "hello world"

    def test_makedirs(self, tmp_path):
        backend = LocalStorageBackend()
        nested = str(tmp_path / "a" / "b" / "c")
        backend.makedirs(nested)
        assert os.path.isdir(nested)

    def test_makedirs_exist_ok(self, tmp_path):
        backend = LocalStorageBackend()
        nested = str(tmp_path / "x")
        backend.makedirs(nested)
        backend.makedirs(nested, exist_ok=True)  # should not raise

    def test_getsize(self, tmp_path):
        backend = LocalStorageBackend()
        f = tmp_path / "size.txt"
        f.write_text("12345")
        assert backend.getsize(str(f)) == 5

    def test_getmtime(self, tmp_path):
        backend = LocalStorageBackend()
        f = tmp_path / "mtime.txt"
        f.write_text("x")
        mtime = backend.getmtime(str(f))
        assert isinstance(mtime, float)
        assert mtime > 0

    def test_isfile(self, tmp_path):
        backend = LocalStorageBackend()
        f = tmp_path / "f.txt"
        f.write_text("x")
        assert backend.isfile(str(f)) is True
        assert backend.isfile(str(tmp_path)) is False

    def test_isdir(self, tmp_path):
        backend = LocalStorageBackend()
        assert backend.isdir(str(tmp_path)) is True
        f = tmp_path / "f.txt"
        f.write_text("x")
        assert backend.isdir(str(f)) is False

    def test_listdir(self, tmp_path):
        backend = LocalStorageBackend()
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        entries = backend.listdir(str(tmp_path))
        assert sorted(entries) == ["a.txt", "b.txt"]

    def test_walk(self, tmp_path):
        backend = LocalStorageBackend()
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.txt").write_text("r")
        (sub / "child.txt").write_text("c")

        walked = list(backend.walk(str(tmp_path)))
        assert len(walked) == 2

        root_dir, root_dirs, root_files = walked[0]
        assert root_dir == str(tmp_path)
        assert "sub" in root_dirs
        assert "root.txt" in root_files

    def test_rmtree(self, tmp_path):
        backend = LocalStorageBackend()
        d = tmp_path / "todelete"
        d.mkdir()
        (d / "inside.txt").write_text("x")
        backend.rmtree(str(d))
        assert not d.exists()

    def test_join(self):
        backend = LocalStorageBackend()
        result = backend.join("/a", "b", "c.txt")
        assert result == os.path.join("/a", "b", "c.txt")

    def test_dirname(self):
        backend = LocalStorageBackend()
        assert backend.dirname("/a/b/c.txt") == "/a/b"

    def test_basename(self):
        backend = LocalStorageBackend()
        assert backend.basename("/a/b/c.txt") == "c.txt"

    def test_open_context_manager(self, tmp_path):
        backend = LocalStorageBackend()
        path = str(tmp_path / "ctx.txt")
        with backend.open(path, "w") as fh:
            fh.write("test")
        # File should be closed after context manager exits
        with backend.open(path, "r") as fh:
            assert fh.read() == "test"


# ---------------------------------------------------------------------------
# TestHDFSStorageBackend
# ---------------------------------------------------------------------------

class TestHDFSStorageBackend:
    """Tests for HDFSStorageBackend (mocked pyarrow)."""

    def _make_backend(self, mock_hdfs_cls, **kwargs):
        """Create an HDFSStorageBackend with mocked pyarrow."""
        import afl.runtime.storage as mod
        orig = mod.HAS_PYARROW
        mod.HAS_PYARROW = True
        try:
            backend = HDFSStorageBackend(**kwargs)
        finally:
            mod.HAS_PYARROW = orig
        return backend

    def test_missing_pyarrow_raises(self):
        with patch("afl.runtime.storage.HAS_PYARROW", False):
            with pytest.raises(RuntimeError, match="pyarrow is required"):
                HDFSStorageBackend()

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_init(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls, host="namenode", port=8020, user="hdfs")
        mock_hdfs_cls.assert_called_once_with(host="namenode", port=8020, user="hdfs")

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_strip_uri(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        assert backend._strip_uri("hdfs://namenode:8020/data/file.txt") == "/data/file.txt"
        assert backend._strip_uri("/local/path") == "/local/path"

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_exists(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        backend._fs.get_file_info.return_value = MagicMock()
        assert backend.exists("hdfs://host:8020/data/file.txt") is True

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_exists_not_found(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        backend._fs.get_file_info.side_effect = FileNotFoundError
        assert backend.exists("hdfs://host:8020/missing.txt") is False

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_open_read(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        mock_stream = MagicMock()
        backend._fs.open_input_stream.return_value = mock_stream
        result = backend.open("hdfs://host:8020/data/file.txt", "r")
        backend._fs.open_input_stream.assert_called_once_with("/data/file.txt")
        assert result is mock_stream

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_open_write(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        mock_stream = MagicMock()
        backend._fs.open_output_stream.return_value = mock_stream
        result = backend.open("hdfs://host:8020/data/file.txt", "w")
        backend._fs.open_output_stream.assert_called_once_with("/data/file.txt")
        assert result is mock_stream

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_makedirs(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        backend.makedirs("hdfs://host:8020/data/newdir")
        backend._fs.create_dir.assert_called_once_with("/data/newdir", recursive=True)

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_getsize(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        mock_info = MagicMock()
        mock_info.size = 42
        backend._fs.get_file_info.return_value = mock_info
        assert backend.getsize("/data/file.txt") == 42

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_rmtree(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        backend.rmtree("hdfs://host:8020/data/dir")
        backend._fs.delete_dir.assert_called_once_with("/data/dir")

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_join(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        assert backend.join("/data", "sub", "file.txt") == "/data/sub/file.txt"

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_dirname(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        assert backend.dirname("/data/sub/file.txt") == "/data/sub"

    @patch("afl.runtime.storage.HadoopFileSystem", create=True)
    def test_basename(self, mock_hdfs_cls):
        backend = self._make_backend(mock_hdfs_cls)
        assert backend.basename("/data/sub/file.txt") == "file.txt"


# ---------------------------------------------------------------------------
# TestGetStorageBackend
# ---------------------------------------------------------------------------

class TestGetStorageBackend:
    """Tests for the get_storage_backend factory function."""

    def setup_method(self):
        """Reset cached backends between tests."""
        import afl.runtime.storage as mod
        mod._local_backend = None
        mod._hdfs_backends.clear()

    def test_local_default(self):
        backend = get_storage_backend()
        assert isinstance(backend, LocalStorageBackend)

    def test_local_path(self):
        backend = get_storage_backend("/tmp/somepath")
        assert isinstance(backend, LocalStorageBackend)

    def test_local_singleton(self):
        b1 = get_storage_backend()
        b2 = get_storage_backend("/tmp/other")
        assert b1 is b2

    @patch("afl.runtime.storage.HAS_PYARROW", True)
    @patch("afl.runtime.storage.HDFSStorageBackend")
    def test_hdfs_uri(self, mock_hdfs_cls):
        mock_instance = MagicMock()
        mock_hdfs_cls.return_value = mock_instance
        backend = get_storage_backend("hdfs://namenode:8020/data")
        mock_hdfs_cls.assert_called_once_with(host="namenode", port=8020)
        assert backend is mock_instance

    @patch("afl.runtime.storage.HAS_PYARROW", True)
    @patch("afl.runtime.storage.HDFSStorageBackend")
    def test_hdfs_caching(self, mock_hdfs_cls):
        mock_instance = MagicMock()
        mock_hdfs_cls.return_value = mock_instance
        b1 = get_storage_backend("hdfs://namenode:8020/data/a")
        b2 = get_storage_backend("hdfs://namenode:8020/data/b")
        assert b1 is b2
        assert mock_hdfs_cls.call_count == 1
