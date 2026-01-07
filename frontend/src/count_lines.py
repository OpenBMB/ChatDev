import os


def count_lines(root: str, extensions=None) -> int:
    """
    Count total number of lines in files under `root` whose extension is in `extensions`.

    :param root: Root directory to walk (e.g., ".").
    :param extensions: Iterable of file extensions (including the dot), e.g. [".py", ".js"].
    :return: Total number of lines across all matching files.
    """
    if extensions is None:
        # Common source-code extensions used in this project
        extensions = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".css", ".scss", ".md"}

    total_lines = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip typical build/output folders if present under src
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "dist", "__pycache__"}]

        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() not in extensions:
                continue

            file_path = os.path.join(dirpath, filename)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for _ in f:
                        total_lines += 1
            except (IOError, OSError):
                # If a file can't be read, skip it but continue counting others
                continue

    return total_lines


def main():
    root = "."
    total = count_lines(root)
    print(f"Total lines of code under '{os.path.abspath(root)}': {total}")


if __name__ == "__main__":
    main()


