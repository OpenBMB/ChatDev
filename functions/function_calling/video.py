import ast
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from utils.code_execution import require_unsafe_code_execution

VALID_MANIM_QUALITIES = {"l", "m", "h", "p", "k"}


def _get_class_names(py_file: str) -> list[str]:
    file_path = Path(py_file)
    if not file_path.exists():
        raise FileNotFoundError(f"{py_file} does not exist.")
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        raise ValueError(f"Invalid Python syntax in {py_file}: {e}") from e
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def render_manim(
    script_path: str,
    quality: str = "h",
    preview: bool = True,
) -> Path:
    require_unsafe_code_execution("render_manim")
    script_path = Path(script_path).resolve()
    if not script_path.exists() or not script_path.is_file():
        raise FileNotFoundError(f"{script_path} does not exist or is not a file.")

    if not isinstance(quality, str) or quality.lower() not in VALID_MANIM_QUALITIES:
        raise ValueError(
            f"Invalid Manim quality '{quality}'. Expected one of: {sorted(VALID_MANIM_QUALITIES)}."
        )
    quality_flag = quality.lower()

    scene_names = _get_class_names(str(script_path))
    if not scene_names:
        raise ValueError(f"No Manim Scene class found in {script_path}.")
    scene_name = scene_names[0]

    output_dir = Path.cwd() / "media"
    print("Clearing media folder:", output_dir)
    shutil.rmtree(output_dir, ignore_errors=True)

    cmd = [
        sys.executable,
        "-m",
        "manim",
        f"-q{quality_flag}",
    ]
    if preview:
        cmd.append("-p")
    cmd.extend([str(script_path), scene_name])

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("Manim rendering failed:")
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)
        error_info = f"Error rendering {scene_name} from {script_path}: {e.stderr}"
        raise RuntimeError(error_info) from e

    # Find valid mp4 files where no parent directory contains a partial_movie_files folder
    video_file = None
    media_videos = output_dir / "videos"
    search_root = media_videos.parent if media_videos.exists() else output_dir
    if search_root.exists():
        for mp4_file in search_root.rglob("*.mp4"):
            if mp4_file.name == f"{scene_name}.mp4":
                video_file = mp4_file
                break

    if video_file is None or not video_file.exists():
        raise FileNotFoundError(
            f"Rendered video '{scene_name}.mp4' was not found under {output_dir}."
        )

    target_path = script_path.parent / video_file.name
    print(f"Copying video to {target_path}")
    shutil.copy2(video_file, target_path)
    shutil.rmtree(output_dir, ignore_errors=True)
    return target_path


def concat_videos(video_paths: Sequence[Path | str]) -> Path:
    if not video_paths:
        raise ValueError("No video files to concatenate")

    resolved_paths: list[Path] = []
    for p in video_paths:
        resolved = Path(p).resolve()
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Video file does not exist: {p}")
        resolved_paths.append(resolved)

    output_path = resolved_paths[0].parent / "combined_video.mp4"
    list_file_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for p in resolved_paths:
                f.write(f"file '{p.as_posix()}'\n")
            list_file_path = Path(f.name)

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file_path),
            "-c",
            "copy",
            str(output_path),
        ]

        subprocess.run(cmd, check=True)
        return output_path
    finally:
        if list_file_path is not None and list_file_path.exists():
            try:
                list_file_path.unlink()
            except OSError:
                pass
