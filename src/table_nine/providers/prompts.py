from __future__ import annotations

from table_nine.providers.contracts import BeatSuggestionRequest, HingeSuggestionRequest


SYSTEM_PROMPT = """You are an editorial assistant inside the Table Nine Script Workbench.
The workbench develops one Uncles in Space Three-Seat Inquiry episode at a time.
Offer bounded alternatives; never claim final creative authority. Do not select an intellectual
hinge, decide the provisional finding, assign a station, or write a permanent archive addition.
Preserve the nine-beat format, recurring rituals, intentional silence, and performance-flexible
lines. Write specifically from the supplied episode evidence. Return only the requested schema."""


def hinge_messages(request: HingeSuggestionRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Propose exactly three materially distinct intellectual hinge candidates. Each "
                "candidate must connect the observed behaviour to the AI-era problem through an "
                "explicit causal chain. Do not select a candidate.\n\nEpisode context:\n"
                f"{request.model_dump_json(indent=2)}"
            ),
        },
    ]


def beat_draft_messages(request: BeatSuggestionRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Draft only the selected beat. Return exactly two alternatives: one conservative "
                "and one stranger but still usable. Script syntax must be line-oriented: "
                "SPEAKER_ID: dialogue, or bracketed directions such as [pause 1.2], "
                "[silence 2.0], [hold on object 1.5], and [transition: text]. Do not draft or "
                "revise any other beat.\n\nSelected context:\n"
                f"{request.model_dump_json(indent=2)}"
            ),
        },
    ]


def beat_revision_messages(request: BeatSuggestionRequest) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Revise only the selected beat according to the instruction. Return exactly two "
                "alternatives: one conservative and one stranger but still usable. Preserve "
                "intentional timing and performance directions unless the instruction addresses "
                "them. Use line-oriented Table Nine script syntax. Do not touch any other beat."
                "\n\nSelected context:\n"
                f"{request.model_dump_json(indent=2)}"
            ),
        },
    ]
