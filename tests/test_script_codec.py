from table_nine.domain.models import ContentDisposition, ScriptElementKind
from table_nine.services.script_codec import parse_script_text, render_script_text


def test_script_text_preserves_typed_performance_elements():
    script = """UNCLE_ONE: Four ordinary spoken words.
[pause 1.2]
[robot processing 1.5]
[hold on classification card 2.0]
[silence 3.0]
[performance-flexible] UNCLE_TWO: This may move during performance.
[optional] [Uncle looks toward robot]"""

    elements = parse_script_text(script, beat_id="specimen-examination")

    assert [element.kind for element in elements] == [
        ScriptElementKind.DIALOGUE,
        ScriptElementKind.PAUSE,
        ScriptElementKind.VISUAL_HOLD,
        ScriptElementKind.VISUAL_HOLD,
        ScriptElementKind.SILENCE,
        ScriptElementKind.DIALOGUE,
        ScriptElementKind.STAGE_DIRECTION,
    ]
    assert elements[4].disposition == ContentDisposition.SILENCE
    assert elements[5].disposition == ContentDisposition.PERFORMANCE_FLEXIBLE
    assert elements[6].disposition == ContentDisposition.OPTIONAL


def test_rendered_script_can_be_parsed_without_losing_meaning():
    original = parse_script_text(
        "UNCLE_ONE: A short line.\n[pause 1.2]\n[silence 2]",
        beat_id="cold-open",
    )

    reparsed = parse_script_text(render_script_text(original), beat_id="cold-open")

    assert reparsed == original

