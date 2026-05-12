"""Tests for facetwork.examples (entry-point + local discovery)."""

from __future__ import annotations

from pathlib import Path

from facetwork import examples as examples_mod
from facetwork.examples import (
    ExamplePackage,
    _parse_runner_env,
    collect_ffl_files,
    discover_all_examples,
    discover_local_examples,
    filter_examples,
)


def _make_local_example(root: Path, name: str, *, with_handlers: bool, with_ffl: bool) -> Path:
    ex = root / "examples" / name
    if with_handlers:
        (ex / "handlers").mkdir(parents=True)
        (ex / "handlers" / "__init__.py").write_text(
            "def register_all_registry_handlers(runner):\n"
            f"    runner.calls.append({name!r})\n"
        )
    if with_ffl:
        (ex / "ffl").mkdir(parents=True)
        (ex / "ffl" / f"{name}.ffl").write_text("// stub\n")
    return ex


class _FakeRunner:
    def __init__(self):
        self.calls: list[str] = []


class TestLocalDiscovery:
    def test_finds_examples_with_handlers_and_ffl(self, tmp_path):
        _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=True)
        _make_local_example(tmp_path, "beta", with_handlers=True, with_ffl=False)
        _make_local_example(tmp_path, "gamma", with_handlers=False, with_ffl=True)

        found = discover_local_examples(tmp_path)
        names = [p.name for p in found]
        assert names == ["alpha", "beta", "gamma"]

        alpha = next(p for p in found if p.name == "alpha")
        assert alpha.source == "local"
        assert alpha.handlers_path == tmp_path / "examples" / "alpha"
        assert alpha.ffl_dir == tmp_path / "examples" / "alpha" / "ffl"

        gamma = next(p for p in found if p.name == "gamma")
        assert gamma.handlers_path is None
        assert gamma.ffl_dir == tmp_path / "examples" / "gamma" / "ffl"

    def test_skips_dirs_without_handlers_or_ffl(self, tmp_path):
        (tmp_path / "examples" / "empty").mkdir(parents=True)
        assert discover_local_examples(tmp_path) == []

    def test_handles_missing_examples_dir(self, tmp_path):
        assert discover_local_examples(tmp_path) == []

    def test_register_handlers_invokes_local_module(self, tmp_path):
        _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=False)
        [pkg] = discover_local_examples(tmp_path)
        runner = _FakeRunner()
        pkg.register_handlers(runner)
        assert runner.calls == ["alpha"]

    def test_two_local_examples_do_not_collide(self, tmp_path):
        # Both define `handlers/__init__.py` — register must reload between calls.
        _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=False)
        _make_local_example(tmp_path, "beta", with_handlers=True, with_ffl=False)
        found = discover_local_examples(tmp_path)
        runner = _FakeRunner()
        for pkg in found:
            pkg.register_handlers(runner)
        assert runner.calls == ["alpha", "beta"]


class TestRunnerEnvParser:
    def test_parses_basic_assignments(self, tmp_path):
        f = tmp_path / "runner.env"
        f.write_text("FOO=bar\nBAZ=qux\n")
        assert _parse_runner_env(f) == {"FOO": "bar", "BAZ": "qux"}

    def test_strips_inline_comments_on_unquoted_values(self, tmp_path):
        f = tmp_path / "runner.env"
        f.write_text("TIMEOUT=14400000   # 4 hours\n")
        assert _parse_runner_env(f) == {"TIMEOUT": "14400000"}

    def test_keeps_hash_inside_quoted_values(self, tmp_path):
        f = tmp_path / "runner.env"
        f.write_text('NOTE="hash # stays"\n')
        assert _parse_runner_env(f) == {"NOTE": "hash # stays"}

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        f = tmp_path / "runner.env"
        f.write_text("# comment\n\nFOO=bar\n")
        assert _parse_runner_env(f) == {"FOO": "bar"}

    def test_handles_export_prefix(self, tmp_path):
        f = tmp_path / "runner.env"
        f.write_text("export FOO=bar\n")
        assert _parse_runner_env(f) == {"FOO": "bar"}


class TestFflCollection:
    def test_local_collects_root_and_nested_ffl(self, tmp_path):
        ex = _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=True)
        nested = ex / "handlers" / "sub" / "ffl"
        nested.mkdir(parents=True)
        (nested / "nested.ffl").write_text("// stub\n")

        [pkg] = discover_local_examples(tmp_path)
        files = collect_ffl_files(pkg)
        rel = sorted(str(f.relative_to(ex)) for f in files)
        assert rel == ["ffl/alpha.ffl", "handlers/sub/ffl/nested.ffl"]

    def test_local_excludes_test_fixtures_except_real(self, tmp_path):
        ex = _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=True)
        (ex / "tests" / "fixtures" / "ffl").mkdir(parents=True)
        (ex / "tests" / "fixtures" / "ffl" / "fixture.ffl").write_text("// stub\n")
        (ex / "tests" / "real" / "ffl").mkdir(parents=True)
        (ex / "tests" / "real" / "ffl" / "real.ffl").write_text("// stub\n")

        [pkg] = discover_local_examples(tmp_path)
        files = collect_ffl_files(pkg)
        rel = sorted(str(f.relative_to(ex)) for f in files)
        assert "tests/fixtures/ffl/fixture.ffl" not in rel
        assert "tests/real/ffl/real.ffl" in rel

    def test_entry_point_collects_recursively_from_ffl_dir(self, tmp_path):
        ffl_root = tmp_path / "pkg" / "ffl"
        (ffl_root / "sub").mkdir(parents=True)
        (ffl_root / "a.ffl").write_text("// stub\n")
        (ffl_root / "sub" / "b.ffl").write_text("// stub\n")

        pkg = ExamplePackage(
            name="entry",
            ffl_dir=ffl_root,
            register_handlers=lambda r: None,
            source="entry_point",
        )
        files = collect_ffl_files(pkg)
        rel = sorted(str(f.relative_to(ffl_root)) for f in files)
        assert rel == ["a.ffl", "sub/b.ffl"]

    def test_extra_ffl_dirs_picked_up(self, tmp_path):
        # Simulate an entry-point package whose installed src tree only sees
        # the canonical ffl/, but the repo also ships fixtures at repo-root
        # tests/real/ffl/ — caller declares them via extra_ffl_dirs.
        pkg_root = tmp_path / "pkg"
        ffl_root = pkg_root / "ffl"
        ffl_root.mkdir(parents=True)
        (ffl_root / "main.ffl").write_text("// stub\n")

        repo_real = tmp_path / "tests" / "real" / "ffl"
        repo_real.mkdir(parents=True)
        (repo_real / "fixture_a.ffl").write_text("// stub\n")
        (repo_real / "fixture_b.ffl").write_text("// stub\n")

        pkg = ExamplePackage(
            name="entry",
            ffl_dir=ffl_root,
            register_handlers=lambda r: None,
            source="entry_point",
            extra_ffl_dirs=[repo_real],
        )
        files = collect_ffl_files(pkg)
        rel = sorted(str(f.relative_to(tmp_path)) for f in files)
        assert rel == [
            "pkg/ffl/main.ffl",
            "tests/real/ffl/fixture_a.ffl",
            "tests/real/ffl/fixture_b.ffl",
        ]

    def test_extra_ffl_dirs_dedupes_with_root_walk(self, tmp_path):
        # If extra_ffl_dirs overlaps a path the default walk already covers,
        # the file should only appear once.
        ex = _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=True)
        nested = ex / "tests" / "real" / "ffl"
        nested.mkdir(parents=True)
        (nested / "shared.ffl").write_text("// stub\n")

        [pkg] = discover_local_examples(tmp_path)
        pkg.extra_ffl_dirs.append(nested)
        files = collect_ffl_files(pkg)
        shared_hits = [f for f in files if f.name == "shared.ffl"]
        assert len(shared_hits) == 1

    def test_extra_ffl_dirs_skips_missing_dir(self, tmp_path):
        ffl_root = tmp_path / "pkg" / "ffl"
        ffl_root.mkdir(parents=True)
        (ffl_root / "main.ffl").write_text("// stub\n")

        pkg = ExamplePackage(
            name="entry",
            ffl_dir=ffl_root,
            register_handlers=lambda r: None,
            source="entry_point",
            extra_ffl_dirs=[tmp_path / "does-not-exist"],
        )
        files = collect_ffl_files(pkg)
        assert [f.name for f in files] == ["main.ffl"]


class _FakeEP:
    def __init__(self, name: str, target: ExamplePackage):
        self.name = name
        self._target = target

    def load(self):
        return self._target


class TestEntryPointDiscovery:
    def test_loads_entry_point_packages(self, tmp_path, monkeypatch):
        target = ExamplePackage(
            name="installed",
            ffl_dir=tmp_path,
            register_handlers=lambda r: None,
            source="entry_point",
        )
        monkeypatch.setattr(
            examples_mod.importlib.metadata,
            "entry_points",
            lambda group: [_FakeEP("installed", target)],
        )
        [pkg] = examples_mod.discover_entry_point_examples()
        assert pkg.name == "installed"
        assert pkg.source == "entry_point"

    def test_skips_entry_point_returning_wrong_type(self, monkeypatch):
        monkeypatch.setattr(
            examples_mod.importlib.metadata,
            "entry_points",
            lambda group: [_FakeEP("bad", "not an ExamplePackage")],
        )
        assert examples_mod.discover_entry_point_examples() == []

    def test_entry_point_wins_over_local_on_name_collision(self, tmp_path, monkeypatch):
        _make_local_example(tmp_path, "shared", with_handlers=True, with_ffl=True)
        installed = ExamplePackage(
            name="shared",
            ffl_dir=None,
            register_handlers=lambda r: None,
            source="entry_point",
        )
        monkeypatch.setattr(
            examples_mod.importlib.metadata,
            "entry_points",
            lambda group: [_FakeEP("shared", installed)],
        )
        [pkg] = discover_all_examples(tmp_path)
        assert pkg.source == "entry_point"
        assert pkg.handlers_path is None


class TestFilter:
    def test_filter_by_name(self, tmp_path):
        _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=False)
        _make_local_example(tmp_path, "beta", with_handlers=True, with_ffl=False)
        _make_local_example(tmp_path, "gamma", with_handlers=True, with_ffl=False)

        found = discover_local_examples(tmp_path)
        names = [p.name for p in filter_examples(found, include=["alpha", "gamma"])]
        assert names == ["alpha", "gamma"]

    def test_filter_none_passes_all_through(self, tmp_path):
        _make_local_example(tmp_path, "alpha", with_handlers=True, with_ffl=False)
        found = discover_local_examples(tmp_path)
        assert list(filter_examples(found, include=None)) == found
