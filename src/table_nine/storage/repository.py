from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from table_nine.domain.models import DocumentMetadata, EpisodeDocument
from table_nine.storage.markdown import deserialize_episode, serialize_episode


class RepositoryError(RuntimeError):
    """Base error for safe episode file operations."""


class UnsafePathError(RepositoryError):
    """Raised when a requested file escapes the configured repository root."""


class RevisionRequiredError(RepositoryError):
    """Raised when replacement is attempted without an expected revision."""


class ConcurrentModificationError(RepositoryError):
    """Raised when the saved revision differs from the caller's expectation."""


class EpisodeIdentityError(RepositoryError):
    """Raised when replacement would change the episode identity of a file."""


class EpisodeConflictError(RepositoryError):
    """Raised when a new episode conflicts with material already on disk."""


class EpisodeRepository:
    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _resolve_markdown_path(self, relative_path: str | Path) -> Path:
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise UnsafePathError("episode path must stay inside the configured root") from exc
        if candidate.suffix.lower() != ".md":
            raise UnsafePathError("episode files must use the .md extension")
        return candidate

    def load(self, relative_path: str | Path) -> EpisodeDocument:
        path = self._resolve_markdown_path(relative_path)
        return deserialize_episode(path.read_text(encoding="utf-8"))

    def list_episode_files(self) -> list[str]:
        return sorted(
            path.name
            for path in self.root.glob("*DispatchWorkbench*.md")
            if path.is_file()
        )

    def create(
        self,
        relative_path: str | Path,
        document: EpisodeDocument,
    ) -> EpisodeDocument:
        path = self._resolve_markdown_path(relative_path)
        if path.exists():
            raise EpisodeConflictError(f"episode file already exists: {path.name}")

        for filename in self.list_episode_files():
            existing = self.load(filename)
            if existing.episode.id == document.episode.id:
                raise EpisodeConflictError(
                    f"episode ID already exists in {filename}: {document.episode.id}"
                )
            if (
                document.episode.registry_number
                and existing.episode.registry_number == document.episode.registry_number
            ):
                raise EpisodeConflictError(
                    "registry number already exists in "
                    f"{filename}: {document.episode.registry_number}"
                )

        now = self.clock()
        created = document.model_copy(
            update={
                "document": DocumentMetadata(
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            },
            deep=True,
        )
        try:
            self._atomic_create(path, serialize_episode(created))
        except FileExistsError as exc:
            raise EpisodeConflictError(f"episode file already exists: {path.name}") from exc
        return created

    def save(
        self,
        relative_path: str | Path,
        document: EpisodeDocument,
        *,
        expected_revision: int | None = None,
    ) -> EpisodeDocument:
        path = self._resolve_markdown_path(relative_path)
        now = self.clock()
        existing_text: str | None = None
        history_path: Path | None = None

        if path.exists():
            if expected_revision is None:
                raise RevisionRequiredError(
                    "expected_revision is required when replacing an episode"
                )
            existing_text = path.read_text(encoding="utf-8")
            existing = deserialize_episode(existing_text)
            if existing.document.revision != expected_revision:
                raise ConcurrentModificationError(
                    f"expected revision {expected_revision}, found {existing.document.revision}"
                )
            if existing.episode.id != document.episode.id:
                raise EpisodeIdentityError("an episode file cannot change episode id during save")

            history_path = (
                self.root
                / ".table-nine-history"
                / path.stem
                / f"revision-{existing.document.revision:04d}.md"
            )
            revision = existing.document.revision + 1
            created_at = existing.document.created_at
        else:
            if expected_revision is not None:
                raise ConcurrentModificationError("cannot expect a revision for a new episode")
            revision = 1
            created_at = document.document.created_at

        saved = document.model_copy(
            update={
                "document": DocumentMetadata(
                    revision=revision,
                    created_at=created_at,
                    updated_at=now,
                )
            },
            deep=True,
        )

        if history_path is not None and existing_text is not None:
            if history_path.exists():
                if history_path.read_text(encoding="utf-8") != existing_text:
                    raise RepositoryError(f"history revision conflicts with source: {history_path}")
            else:
                self._atomic_write(history_path, existing_text)
        self._atomic_write(path, serialize_episode(saved))
        return saved

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def _atomic_create(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            temporary_path.chmod(0o644)
            os.link(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
