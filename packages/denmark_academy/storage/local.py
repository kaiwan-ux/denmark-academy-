from pathlib import Path
from shutil import copy2

from denmark_academy.config import get_settings


class LocalObjectStorage:
    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = root or settings.local_object_storage_path
        self.root.mkdir(parents=True, exist_ok=True)

    def put_file(self, source_path: Path, object_key: str) -> str:
        destination = self.root / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source_path, destination)
        return f"local://{destination.as_posix()}"

    def put_text(self, text: str, object_key: str) -> str:
        destination = self.root / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        return f"local://{destination.as_posix()}"

