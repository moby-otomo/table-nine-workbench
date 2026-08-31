from __future__ import annotations

import re
from dataclasses import dataclass

from table_nine.domain.defaults import new_episode_document
from table_nine.domain.models import EpisodeDocument
from table_nine.storage.repository import EpisodeRepository


EPISODE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REGISTRY_NUMBER_PATTERN = re.compile(r"^1\d{4}$")


class PilotCreationError(ValueError):
    """Raised when human-supplied pilot identity fields are incomplete or invalid."""


@dataclass(frozen=True)
class CreatedPilot:
    filename: str
    document: EpisodeDocument


def pilot_filename(episode_id: str, registry_number: str | None = None) -> str:
    descriptor = "".join(part.capitalize() for part in episode_id.split("-"))
    prefix = f"TAXO_No{registry_number}" if registry_number else "PILOT"
    return f"{prefix}-{descriptor}-DispatchWorkbench_UIS_v01.md"


def create_new_pilot(
    repository: EpisodeRepository,
    *,
    episode_id: str,
    working_title: str,
    featured_uncle: str,
    registry_number: str | None = None,
) -> CreatedPilot:
    episode_id = episode_id.strip()
    working_title = working_title.strip()
    featured_uncle = featured_uncle.strip()
    registry_number = registry_number.strip() if registry_number else None

    if not EPISODE_ID_PATTERN.fullmatch(episode_id):
        raise PilotCreationError(
            "Episode ID must be a lowercase slug using letters, numbers, and single hyphens."
        )
    if not working_title:
        raise PilotCreationError("Working title is required.")
    if not featured_uncle:
        raise PilotCreationError("Featured Uncle is required.")
    if registry_number and not REGISTRY_NUMBER_PATTERN.fullmatch(registry_number):
        raise PilotCreationError("Registry number must contain five digits beginning with 1.")

    document = new_episode_document(
        episode_id,
        working_title=working_title,
        featured_uncle=featured_uncle,
        registry_number=registry_number,
    )
    filename = pilot_filename(episode_id, registry_number)
    return CreatedPilot(filename=filename, document=repository.create(filename, document))
