import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from functions.function_calling import video
from utils.code_execution import UNSAFE_CODE_EXECUTION_ENV, SecurityError


def test_get_class_names_success(tmp_path):
    py_file = tmp_path / "scene.py"
    py_file.write_text("class MyScene:\n    pass\nclass AnotherScene:\n    pass\n", encoding="utf-8")
    classes = video._get_class_names(str(py_file))
    assert classes == ["MyScene", "AnotherScene"]


def test_get_class_names_nonexistent(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        video._get_class_names(str(tmp_path / "missing.py"))


def test_get_class_names_syntax_error(tmp_path):
    py_file = tmp_path / "broken.py"
    py_file.write_text("class MyScene:\ndef broken(\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid Python syntax"):
        video._get_class_names(str(py_file))


def test_render_manim_security_check(tmp_path, monkeypatch):
    monkeypatch.delenv(UNSAFE_CODE_EXECUTION_ENV, raising=False)
    with pytest.raises(SecurityError, match=UNSAFE_CODE_EXECUTION_ENV):
        video.render_manim("some_script.py")


def test_render_manim_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    with pytest.raises(FileNotFoundError, match="does not exist or is not a file"):
        video.render_manim(str(tmp_path / "missing.py"))


def test_render_manim_invalid_quality(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    py_file = tmp_path / "scene.py"
    py_file.write_text("class SceneA:\n    pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid Manim quality 'ultra'"):
        video.render_manim(str(py_file), quality="ultra")


def test_render_manim_no_scene_class(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    py_file = tmp_path / "no_scene.py"
    py_file.write_text("def helper():\n    return 42\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No Manim Scene class found"):
        video.render_manim(str(py_file))


def test_render_manim_command_flags_and_success(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.chdir(tmp_path)
    py_file = tmp_path / "scene.py"
    py_file.write_text("class TestScene:\n    pass\n", encoding="utf-8")

    captured_cmds = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        media_videos = tmp_path / "media" / "videos" / "scene" / "1080p60"
        media_videos.mkdir(parents=True, exist_ok=True)
        (media_videos / "TestScene.mp4").write_text("dummy video content", encoding="utf-8")
        return Mock(return_value=0)

    with patch.object(video.subprocess, "run", side_effect=mock_subprocess_run):
        # Test preview=True
        target = video.render_manim(str(py_file), quality="h", preview=True)
        assert target.name == "TestScene.mp4"
        assert target.read_text(encoding="utf-8") == "dummy video content"
        assert "-qh" in captured_cmds[0]
        assert "-p" in captured_cmds[0]

        # Test preview=False does not include -p
        target2 = video.render_manim(str(py_file), quality="l", preview=False)
        assert target2.name == "TestScene.mp4"
        assert "-ql" in captured_cmds[1]
        assert "-p" not in captured_cmds[1]


def test_render_manim_missing_output_video_error(tmp_path, monkeypatch):
    monkeypatch.setenv(UNSAFE_CODE_EXECUTION_ENV, "1")
    monkeypatch.chdir(tmp_path)
    py_file = tmp_path / "scene.py"
    py_file.write_text("class TestScene:\n    pass\n", encoding="utf-8")

    with (
        patch.object(video.subprocess, "run", return_value=Mock(return_value=0)),
        pytest.raises(FileNotFoundError, match="Rendered video 'TestScene.mp4' was not found"),
    ):
        video.render_manim(str(py_file))


def test_concat_videos_empty_list():
    with pytest.raises(ValueError, match="No video files to concatenate"):
        video.concat_videos([])


def test_concat_videos_missing_file(tmp_path):
    existing = tmp_path / "v1.mp4"
    existing.write_text("content", encoding="utf-8")
    missing = tmp_path / "v2.mp4"
    with pytest.raises(FileNotFoundError, match="Video file does not exist"):
        video.concat_videos([existing, missing])


def test_concat_videos_cleans_up_temp_list_file(tmp_path):
    v1 = tmp_path / "v1.mp4"
    v2 = tmp_path / "v2.mp4"
    v1.write_text("v1", encoding="utf-8")
    v2.write_text("v2", encoding="utf-8")

    list_file_seen = []

    def mock_run(cmd, *args, **kwargs):
        list_file = cmd[7]
        list_file_seen.append(Path(list_file))
        assert Path(list_file).exists()
        (tmp_path / "combined_video.mp4").write_text("combined", encoding="utf-8")
        return Mock(return_value=0)

    with patch.object(video.subprocess, "run", side_effect=mock_run):
        output = video.concat_videos([v1, v2])
        assert output == tmp_path / "combined_video.mp4"
        assert len(list_file_seen) == 1
        # Check that temp list file was deleted
        assert not list_file_seen[0].exists()


def test_concat_videos_cleans_up_temp_on_subprocess_error(tmp_path):
    v1 = tmp_path / "v1.mp4"
    v1.write_text("v1", encoding="utf-8")

    list_file_seen = []

    def mock_run_fail(cmd, *args, **kwargs):
        list_file = cmd[7]
        list_file_seen.append(Path(list_file))
        raise subprocess.CalledProcessError(1, cmd, stderr="ffmpeg error")

    with patch.object(video.subprocess, "run", side_effect=mock_run_fail):
        with pytest.raises(subprocess.CalledProcessError):
            video.concat_videos([v1])
        assert len(list_file_seen) == 1
        assert not list_file_seen[0].exists()
