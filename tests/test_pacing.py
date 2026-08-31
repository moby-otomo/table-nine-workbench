import pytest

from table_nine.services.pacing import PacingConfig, calculate_beat_pacing, count_words
from table_nine.services.script_codec import parse_script_text


def test_pacing_combines_spoken_words_and_explicit_time(traffic_cone_document):
    beat = traffic_cone_document.beat_board.beats[0]
    beat.script = parse_script_text(
        "UNCLE_ONE: One two three four.\n[pause 1.5]\n[silence 2.5]",
        beat_id=beat.id,
    )

    pacing = calculate_beat_pacing(beat, PacingConfig(default_wpm=120))

    assert pacing.spoken_words == 4
    assert pacing.speech_seconds == pytest.approx(2.0)
    assert pacing.timed_seconds == pytest.approx(4.0)
    assert pacing.total_seconds == pytest.approx(6.0)


def test_speaker_rate_override_is_used(traffic_cone_document):
    beat = traffic_cone_document.beat_board.beats[0]
    beat.script = parse_script_text(
        "ARCHIVIST_ROBOT: One two three four.",
        beat_id=beat.id,
    )

    pacing = calculate_beat_pacing(
        beat,
        PacingConfig(default_wpm=120, speaker_wpm={"archivist_robot": 240}),
    )

    assert pacing.speech_seconds == pytest.approx(1.0)


def test_word_count_handles_contractions_and_hyphens():
    assert count_words("don't over-explain the AI-era problem") == 5
