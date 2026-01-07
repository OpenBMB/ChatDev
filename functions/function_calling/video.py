import shutil
import sys
from pathlib import Path
import ast
import subprocess
import tempfile

def _get_class_names(py_file: str) -> list[str]:
    file_path = Path(py_file)
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

def render_manim(
    script_path: str,
    quality: str = "h",
    preview: bool = True,
) -> Path:
    output_dir = Path.cwd() / "media" 
    print("Clearing media folder:", output_dir)
    shutil.rmtree(output_dir, ignore_errors=True)
    script_path = Path(script_path).resolve()
    if not script_path.exists():
        raise FileNotFoundError(script_path, " does not exist.")
    scene_name = _get_class_names(str(script_path))[0] 
    cmd = [
        sys.executable, "-m", "manim",
        f"-pq{quality}",
    ]

    if preview:
        cmd.insert(3, "-p")

    cmd.extend([str(script_path), scene_name])

    print("Running:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("Manim rendering failed:")
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)
        error_info = f"Error rendering {scene_name} from {script_path}: {e.stderr}"
        # shutil.rmtree(output_dir, ignore_errors=True)
        raise RuntimeError(error_info)

    # Find valid mp4 files where no parent directory contains a partial_movie_files folder
    video_file = None
    for mp4_file in (Path.cwd() / "media" / "videos").parent.rglob("*.mp4"):
        if mp4_file.name == f"{scene_name}.mp4":
            video_file = mp4_file
            break

    target_path = script_path.parent / video_file.name
    print(f"Copying video to {target_path}")
    shutil.copy2(video_file, target_path)
    shutil.rmtree(output_dir, ignore_errors=True)
    return target_path

def concat_videos(video_paths: list[Path]) -> Path:
    if not video_paths:
        raise ValueError("No video files to concatenate")

    video_paths = [Path(p).resolve() for p in video_paths]
    output_path = video_paths[0].parent / "combined_video.mp4"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in video_paths:
            f.write(f"file '{p.as_posix()}'\n")
        list_file = f.name

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        str(output_path)
    ]

    subprocess.run(cmd, check=True)
    return output_path

