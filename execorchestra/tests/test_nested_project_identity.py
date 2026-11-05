from pathlib import Path
import subprocess

import pytest

from sgar_mvp.scripts import check_model_health
from sgar_mvp.src.release_promotion import _git_paths
from sgar_mvp.src.release_source_seal import _file_hashes, _source_status


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


@pytest.fixture
def checkout(tmp_path):
    repo = tmp_path / "ChatDev"
    project = repo / "execorchestra"
    project.mkdir(parents=True)
    git(repo, "-c", "init.templateDir=", "init", "-b", "execorchestra")
    git(repo, "config", "user.name", "Layout test")
    git(repo, "config", "user.email", "layout@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "README.md").write_text("branch readme\n", encoding="utf-8")
    script = project / "sgar_mvp/scripts/check_model_health.py"
    script.parent.mkdir(parents=True)
    script.write_bytes(Path(check_model_health.__file__).read_bytes())
    (project / "build_index.py").write_text("# index\n", encoding="utf-8")
    (project / "Pool/resources").mkdir(parents=True)
    (project / "Pool/resources/catalog.json").write_text("[]\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Nested project fixture")
    return repo, project


def test_model_health_identity_reads_committed_subproject(checkout):
    repo, project = checkout
    identity = check_model_health._source_identity(project)
    assert identity["head"] == git(repo, "rev-parse", "HEAD").decode().strip()
    assert identity["tree"] == git(repo, "rev-parse", "HEAD^{tree}").decode().strip()


@pytest.mark.parametrize("staged", [False, True])
def test_nested_source_modification_is_not_missed(checkout, staged):
    _, project = checkout
    tracked = _file_hashes(project, "release")
    assert "build_index.py" in tracked
    assert "Pool/resources/catalog.json" in tracked
    assert _source_status(project, tracked)["framework_source_clean"]
    (project / "build_index.py").write_text("# changed\n", encoding="utf-8")
    if staged:
        git(project, "add", "build_index.py")
    status = _source_status(project, tracked)
    assert status["framework_source_clean"] is False
    assert status["relevant_change_count"] == 1


def test_promotion_paths_keep_outside_changes_visible(checkout):
    repo, project = checkout
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (project / "build_index.py").write_text("changed\n", encoding="utf-8")
    names = _git_paths(project, "diff", "--name-only", "-z", "--no-renames")
    assert names == {"../README.md", "build_index.py"}
