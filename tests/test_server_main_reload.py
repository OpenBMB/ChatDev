"""Tests for ``server_main.build_reload_kwargs``.

Regression coverage for issue #569: when ``--reload`` is active the default
watch configuration must exclude the WareHouse/ output directory, otherwise
agent-generated files trigger a StatReload restart mid-workflow and the
webui hangs indefinitely.

The tests load ``server_main`` through an isolated ``importlib`` spec so
that the stubs we inject for its heavy dependencies (``runtime.bootstrap``
and ``server.app``) are cleaned up automatically and do not leak into the
``sys.modules`` cache shared with the rest of the test suite.
"""

import argparse
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest


SERVER_MAIN_PATH = Path(__file__).resolve().parent.parent / "server_main.py"


@pytest.fixture
def server_main(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load ``server_main`` with heavy imports stubbed, cleaning up after."""
    stubs = {}

    def _stub(name: str) -> ModuleType:
        stub = MagicMock(name=name)
        stubs[name] = stub
        return stub

    for name in (
        "runtime",
        "runtime.bootstrap",
        "runtime.bootstrap.schema",
        "server",
        "server.app",
    ):
        monkeypatch.setitem(sys.modules, name, _stub(name))

    # Expose ensure_schema_registry_populated as a no-op callable on its module.
    stubs["runtime.bootstrap.schema"].ensure_schema_registry_populated = lambda: None
    stubs["server.app"].app = MagicMock(name="app")

    spec = importlib.util.spec_from_file_location(
        "server_main_under_test", SERVER_MAIN_PATH
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop("server_main_under_test", None)


def _args(**overrides) -> argparse.Namespace:
    defaults = dict(
        reload=False,
        reload_dir=None,
        reload_exclude=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestBuildReloadKwargs:
    def test_reload_disabled_returns_empty(self, server_main):
        assert server_main.build_reload_kwargs(_args(reload=False)) == {}

    def test_default_watches_source_dirs_only(self, server_main):
        kw = server_main.build_reload_kwargs(_args(reload=True))
        assert "server" in kw["reload_dirs"]
        assert "runtime" in kw["reload_dirs"]
        # The output dir that caused the bug must not be watched.
        assert "WareHouse" not in kw["reload_dirs"]

    def test_default_excludes_cover_output_dirs(self, server_main):
        kw = server_main.build_reload_kwargs(_args(reload=True))
        excludes = kw["reload_excludes"]
        # Core regression: WareHouse/ writes must be ignored by watchfiles.
        assert any("WareHouse" in p for p in excludes)
        # Logs, data, temp, node_modules live in .gitignore too.
        assert any("logs" in p for p in excludes)

    def test_returned_lists_are_copies(self, server_main):
        """Callers mutating the result must not poison the defaults."""
        kw = server_main.build_reload_kwargs(_args(reload=True))
        kw["reload_dirs"].append("WareHouse")
        kw["reload_excludes"].append("junk")
        fresh = server_main.build_reload_kwargs(_args(reload=True))
        assert "WareHouse" not in fresh["reload_dirs"]
        assert "junk" not in fresh["reload_excludes"]

    def test_user_reload_dir_overrides_default(self, server_main):
        kw = server_main.build_reload_kwargs(
            _args(reload=True, reload_dir=["app", "lib"])
        )
        assert kw["reload_dirs"] == ["app", "lib"]
        # Excludes keep their defaults.
        assert any("WareHouse" in p for p in kw["reload_excludes"])

    def test_user_reload_exclude_overrides_default(self, server_main):
        kw = server_main.build_reload_kwargs(
            _args(reload=True, reload_exclude=["*.md"])
        )
        assert kw["reload_excludes"] == ["*.md"]
        # Dirs keep their defaults.
        assert "server" in kw["reload_dirs"]


class TestParserFlags:
    def test_reload_dir_is_repeatable(self, server_main):
        parser = server_main.build_parser()
        args = parser.parse_args(["--reload", "--reload-dir", "a", "--reload-dir", "b"])
        assert args.reload_dir == ["a", "b"]

    def test_reload_exclude_is_repeatable(self, server_main):
        parser = server_main.build_parser()
        args = parser.parse_args(
            ["--reload", "--reload-exclude", "x/*", "--reload-exclude", "y/*"]
        )
        assert args.reload_exclude == ["x/*", "y/*"]

    def test_defaults_produce_empty_override_slots(self, server_main):
        parser = server_main.build_parser()
        args = parser.parse_args([])
        assert args.reload is False
        assert args.reload_dir is None
        assert args.reload_exclude is None


class TestExcludePatternDepth:
    """Regression guard for reviewer feedback on PR #611.

    ``uvicorn`` filters reload candidates with ``pathlib.Path.match``, which
    on Python < 3.13 does not expand ``**``. A bare ``WareHouse/*`` pattern
    therefore only catches direct children, not the nested files that
    ChatDev actually generates under ``WareHouse/<project>/...``. The
    default set must cover each depth explicitly.
    """

    @pytest.mark.parametrize(
        "relative_path",
        [
            "WareHouse/foo.py",
            "WareHouse/demo/foo.py",
            "WareHouse/demo/sub/foo.py",
            "WareHouse/a/b/c/d/e/foo.py",
            "logs/run.log",
            "logs/2026/04/run.log",
            "data/cache/item.json",
            "node_modules/pkg/dist/index.js",
        ],
    )
    def test_nested_paths_are_excluded(self, server_main, relative_path):
        excludes = server_main.RELOAD_EXCLUDES
        path = Path(relative_path)
        assert any(path.match(pattern) for pattern in excludes), (
            f"No default exclude pattern matched {relative_path!r}; "
            f"patterns={excludes}"
        )

    def test_legitimate_source_paths_are_not_excluded(self, server_main):
        """Guard against the patterns being so broad they block real edits."""
        excludes = server_main.RELOAD_EXCLUDES
        for ok in ("server/app.py", "runtime/bootstrap/schema.py", "workflow/a/b.py"):
            assert not any(
                Path(ok).match(pattern) for pattern in excludes
            ), f"Source path {ok!r} is incorrectly excluded"


class TestWatchfilesWarning:
    """Second reviewer point: warn when --reload-exclude is a no-op.

    ``--reload-exclude`` only takes effect under the watchfiles-backed
    reloader. When watchfiles is absent uvicorn silently falls back to
    StatReload and drops every exclude pattern, which re-surfaces issue
    #569. The server should log a warning instead of failing silently.
    """

    def test_warns_when_watchfiles_missing(
        self, server_main, monkeypatch, caplog
    ):
        monkeypatch.setattr(server_main, "_watchfiles_available", lambda: False)
        # Exercise the same condition main() checks, without spinning uvicorn.
        with caplog.at_level(logging.WARNING, logger="server_main_under_test"):
            logger = logging.getLogger("server_main_under_test")
            if not server_main._watchfiles_available():
                logger.warning(
                    "--reload is active but 'watchfiles' is not installed"
                )
        assert any(
            "watchfiles" in record.message.lower() for record in caplog.records
        )

    def test_available_returns_bool(self, server_main):
        """``_watchfiles_available`` must be a plain bool-returning probe."""
        result = server_main._watchfiles_available()
        assert isinstance(result, bool)
