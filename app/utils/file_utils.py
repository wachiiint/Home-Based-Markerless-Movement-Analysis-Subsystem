from pathlib import Path


def cleanup_temp_file(path: Path, store_temp_files: bool) -> None:
    if not store_temp_files and path.exists():
        path.unlink()
