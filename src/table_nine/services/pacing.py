from __future__ import annotations

import re
from dataclasses import dataclass, field

from table_nine.domain.models import Beat, EpisodeDocument, ScriptElementKind


WORD = re.compile(r"[^\W_]+(?:['\u2019-][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class PacingConfig:
    default_wpm: float = 120.0
    speaker_wpm: dict[str, float] = field(default_factory=dict)

    def wpm_for(self, speaker_id: str) -> float:
        wpm = self.speaker_wpm.get(speaker_id, self.default_wpm)
        if wpm <= 0:
            raise ValueError("speaking rates must be greater than zero")
        return wpm


@dataclass(frozen=True)
class BeatPacing:
    beat_id: str
    spoken_words: int
    speech_seconds: float
    timed_seconds: float
    total_seconds: float
    target_seconds: int

    @property
    def variance_seconds(self) -> float:
        return self.total_seconds - self.target_seconds


@dataclass(frozen=True)
class EpisodePacing:
    beats: tuple[BeatPacing, ...]

    @property
    def spoken_words(self) -> int:
        return sum(beat.spoken_words for beat in self.beats)

    @property
    def total_seconds(self) -> float:
        return sum(beat.total_seconds for beat in self.beats)


def count_words(text: str) -> int:
    return len(WORD.findall(text))


def calculate_beat_pacing(beat: Beat, config: PacingConfig) -> BeatPacing:
    spoken_words = 0
    speech_seconds = 0.0
    timed_seconds = 0.0

    for element in beat.script:
        if element.kind == ScriptElementKind.DIALOGUE:
            words = count_words(element.text)
            spoken_words += words
            speech_seconds += words / config.wpm_for(element.speaker_id or "") * 60
        elif element.kind in {
            ScriptElementKind.PAUSE,
            ScriptElementKind.VISUAL_HOLD,
            ScriptElementKind.SILENCE,
        }:
            timed_seconds += element.duration_seconds or 0.0

    return BeatPacing(
        beat_id=beat.id,
        spoken_words=spoken_words,
        speech_seconds=speech_seconds,
        timed_seconds=timed_seconds,
        total_seconds=speech_seconds + timed_seconds,
        target_seconds=beat.target_seconds,
    )


def calculate_episode_pacing(
    document: EpisodeDocument,
    config: PacingConfig,
) -> EpisodePacing:
    return EpisodePacing(
        beats=tuple(calculate_beat_pacing(beat, config) for beat in document.beat_board.beats)
    )

