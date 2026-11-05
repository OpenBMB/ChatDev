import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts import download_embedding, prepare_release


def test_all_stops_before_index_when_a_probe_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_release, "ROOT", tmp_path)
    stages = []

    def run(module, stage, *options):
        stages.append(stage)
        if stage == "tools":
            raise subprocess.CalledProcessError(1, [module, stage])

    monkeypatch.setattr(prepare_release, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        prepare_release.prepare_all(allow_unavailable=True)
    assert stages == ["health", "control", "tools"]


def test_all_preserves_existing_index_before_any_provider_requests(tmp_path, monkeypatch):
    index = tmp_path / "Pool/index_meta"
    index.mkdir(parents=True)
    (index / "existing.index").write_bytes(b"preserve")
    monkeypatch.setattr(prepare_release, "ROOT", tmp_path)
    calls = []
    monkeypatch.setattr(prepare_release, "run", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="already exists"):
        prepare_release.prepare_all()
    assert calls == []
    assert (index / "existing.index").read_bytes() == b"preserve"


@pytest.mark.parametrize("reduced", [False, True])
def test_all_keeps_readiness_policy_explicit(tmp_path, monkeypatch, reduced):
    monkeypatch.setattr(prepare_release, "ROOT", tmp_path)
    calls = []
    monkeypatch.setattr(prepare_release, "run", lambda *args: calls.append(args))
    prepare_release.prepare_all(allow_unavailable=reduced, runtime_backend="apptainer")
    assert [c[1] for c in calls] == ["health", "control", "tools", "agents", "readiness", "index", "check"]
    readiness = calls[4]
    assert readiness[2:4] == ("--runtime-backend", "apptainer")
    assert ("--allow-unavailable" in readiness) == reduced
    assert all(len(c) == 2 for i, c in enumerate(calls) if i != 4)


@pytest.mark.parametrize("tokenizer_only", [False, True])
def test_embedding_download_uses_pinned_assets_without_service_start(tmp_path, monkeypatch, tokenizer_only):
    config = download_embedding.ROOT / "configs/embedding_release.example.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    target = tmp_path / "configs/embedding_release.example.json"
    target.parent.mkdir()
    target.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(download_embedding, "ROOT", tmp_path)
    weights, tokens, saved = [], [], []

    def from_pretrained(*args, **kwargs):
        tokens.append((args, kwargs))
        return SimpleNamespace(save_pretrained=lambda path: saved.append(path))

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(
        snapshot_download=lambda *a, **kw: weights.append((a, kw))))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=from_pretrained)))
    download_embedding.download(tokenizer_only=tokenizer_only)
    assert saved == [str(tmp_path / ".cache/embedding-tokenizer")]
    runtime = data["runtime"]
    if tokenizer_only:
        assert weights == []
        assert tokens == [((runtime["model_id"],), {"revision": runtime["revision"]})]
    else:
        assert weights == [((runtime["model_id"],), {
            "revision": runtime["revision"], "local_dir": str(tmp_path / ".cache/embedding-model")})]
        assert tokens == [((str(tmp_path / ".cache/embedding-model"),), {"local_files_only": True})]
