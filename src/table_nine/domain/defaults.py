from __future__ import annotations

from datetime import datetime, timezone

from table_nine.domain.models import (
    Beat,
    BeatBoard,
    Cast,
    CastMember,
    ConversationalTemperature,
    DocumentMetadata,
    EpisodeDocument,
    EpisodeDossier,
)


CORE_BEAT_SPECS = (
    (
        "cold-open",
        "Overheard cold open",
        "Create curiosity through a fragment of the case.",
        20,
        35,
        ConversationalTemperature.CURIOUS,
    ),
    (
        "compact-introductions",
        "Compact introductions",
        "Identify the rotating cast and programme.",
        30,
        60,
        ConversationalTemperature.SOCIALLY_WARM,
    ),
    (
        "observations",
        "Have you observed anything lately?",
        "Establish companionship and plant relevance.",
        120,
        220,
        ConversationalTemperature.SOCIALLY_WARM,
    ),
    (
        "file-arrival",
        "Arrival of the file",
        "Move from catch-up into formal inquiry.",
        38,
        65,
        ConversationalTemperature.PROCEDURAL,
    ),
    (
        "specimen-examination",
        "Taxonomic specimen examination",
        "Establish behaviour, evidence, and comic register.",
        195,
        330,
        ConversationalTemperature.TAXONOMICALLY_DRY,
    ),
    (
        "deeper-inquiry",
        "Deeper inquiry",
        "Develop the AI-era cognitive problem and productive detour.",
        420,
        700,
        ConversationalTemperature.ABSTRACT,
    ),
    (
        "return-and-finding",
        "Return and provisional finding",
        "State what changed without pretending finality.",
        75,
        125,
        ConversationalTemperature.QUIETLY_SINCERE,
    ),
    (
        "comparative-tolerability",
        "Comparative Tolerability Protocol",
        "Restore comic tempo and test classification boundaries.",
        120,
        200,
        ConversationalTemperature.COMIC_RELEASE,
    ),
    (
        "station-assignment",
        "Station assignment and final button",
        "Convert irregularity into function and close cleanly.",
        60,
        90,
        ConversationalTemperature.PROCEDURAL,
    ),
)


def build_standard_beat_board() -> BeatBoard:
    beats = [
        Beat(
            id=beat_id,
            title=title,
            purpose=purpose,
            core_order=index,
            target_seconds=target_seconds,
            target_words=target_words,
            temperature=temperature,
        )
        for index, (beat_id, title, purpose, target_seconds, target_words, temperature) in enumerate(
            CORE_BEAT_SPECS
        )
    ]
    return BeatBoard(beats=beats)


def new_episode_document(
    episode_id: str,
    *,
    working_title: str = "",
    featured_uncle: str = "",
    registry_number: str | None = None,
    now: datetime | None = None,
) -> EpisodeDocument:
    timestamp = now or datetime.now(timezone.utc)
    cast = Cast(
        seated_uncle_1=CastMember(
            seat_id="uncle_one",
            display_name="Uncle One (unassigned)",
            cognitive_function="Intuitive and associative role tendency.",
        ),
        seated_uncle_2=CastMember(
            seat_id="uncle_two",
            display_name="Uncle Two (unassigned)",
            cognitive_function="Skeptical and practical role tendency.",
        ),
        archivist_robot=CastMember(
            seat_id="archivist_robot",
            display_name="Archivist Robot",
            character_id="archivist-robot",
            cognitive_function="Systematizes, records, and classifies without final authority.",
        ),
    )
    return EpisodeDocument(
        document=DocumentMetadata(created_at=timestamp, updated_at=timestamp),
        episode=EpisodeDossier(
            id=episode_id,
            working_title=working_title,
            featured_uncle=featured_uncle,
            registry_number=registry_number,
        ),
        cast=cast,
        beat_board=build_standard_beat_board(),
    )

