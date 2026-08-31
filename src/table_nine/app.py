from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path
from typing import TypeVar

import streamlit as st
from pydantic import ValidationError

from table_nine.domain.models import (
    ApprovalStatus,
    ComparatorStatus,
    ComparatorUncle,
    ConversationalTemperature,
    EditorialField,
    EpisodeDocument,
    EpisodeStatus,
    HingeCandidate,
    Provenance,
    SuggestionKind,
    SuggestionStatus,
)
from table_nine.providers import ProviderError, build_provider
from table_nine.services.assistance import (
    AssistanceError,
    apply_beat_option,
    apply_hinge_option,
    dismiss_suggestion,
    generate_beat_suggestion,
    generate_hinge_suggestion,
)
from table_nine.services.editing import LockedContentError, save_episode
from table_nine.services.audits import (
    AuditCategory,
    AuditReport,
    AuditSeverity,
    audit_document,
)
from table_nine.services.exports import build_exports
from table_nine.services.pacing import PacingConfig, calculate_episode_pacing
from table_nine.services.pilots import PilotCreationError, create_new_pilot
from table_nine.services.production import (
    PackageKind,
    ProductionGate,
    build_production_package,
    evaluate_production_readiness,
)
from table_nine.services.script_codec import ScriptParseError, parse_script_text, render_script_text
from table_nine.storage.repository import EpisodeRepository, RepositoryError


SCRIPTS_ROOT = Path(os.environ["TABLE_NINE_SCRIPTS_ROOT"]).resolve()
if not SCRIPTS_ROOT.is_dir():
    msg = (
        "TABLE_NINE_SCRIPTS_ROOT environment variable is set but path is not a "
        f"directory: {SCRIPTS_ROOT}"
    )
    raise RuntimeError(msg)

EnumType = TypeVar("EnumType", bound=Enum)


def _label(value: Enum) -> str:
    return value.value.replace("_", " ").title()


def _format_duration(seconds: float) -> str:
    rounded = max(0, round(seconds))
    minutes, remaining = divmod(rounded, 60)
    return f"{minutes}:{remaining:02d}"


def _clear_editor_state() -> None:
    prefixes = ("edit_", "hinge_", "beat_", "comparator_", "assist_", "audit_")
    for key in list(st.session_state):
        if key.startswith(prefixes):
            del st.session_state[key]


def _load_selected(repository: EpisodeRepository, filename: str, *, force: bool = False) -> None:
    if force or st.session_state.get("loaded_filename") != filename:
        document = repository.load(filename)
        st.session_state.loaded_filename = filename
        st.session_state.original_document = document.model_copy(deep=True)
        st.session_state.document = document.model_copy(deep=True)
        _clear_editor_state()


def _render_new_pilot(repository: EpisodeRepository) -> None:
    with st.sidebar.expander("New pilot", icon=":material/note_add:"):
        with st.form("new_pilot_form", clear_on_submit=True, border=False):
            episode_id = st.text_input(
                "Episode ID",
                placeholder="traffic-cone-uncle",
                key="new_pilot_episode_id",
            )
            working_title = st.text_input(
                "Pilot title",
                key="new_pilot_working_title",
            )
            featured_uncle = st.text_input(
                "Featured Uncle",
                key="new_pilot_featured_uncle",
            )
            registry_number = st.text_input(
                "Registry number (optional)",
                max_chars=5,
                key="new_pilot_registry_number",
            )
            submitted = st.form_submit_button(
                "Create pilot",
                icon=":material/add:",
                width="stretch",
            )

        if submitted:
            try:
                created = create_new_pilot(
                    repository,
                    episode_id=episode_id,
                    working_title=working_title,
                    featured_uncle=featured_uncle,
                    registry_number=registry_number,
                )
            except (PilotCreationError, RepositoryError, ValidationError, OSError) as exc:
                st.error(str(exc))
            else:
                st.session_state.selected_filename = created.filename
                st.session_state.pop("loaded_filename", None)
                st.session_state.new_pilot_notice = (
                    f"Created {created.document.episode.working_title}"
                )
                st.rerun()


def _enum_select(
    label: str,
    current: EnumType,
    enum_type: type[EnumType],
    *,
    key: str,
    disabled: bool = False,
) -> EnumType:
    options = list(enum_type)
    return st.selectbox(
        label,
        options,
        index=options.index(current),
        format_func=_label,
        key=key,
        disabled=disabled,
    )


def _editorial_field(
    label: str,
    field: EditorialField,
    *,
    key: str,
    height: int = 96,
) -> None:
    st.markdown(f"#### {label}")
    field.value = st.text_area(
        label,
        value=field.value,
        key=f"edit_{key}_value",
        height=height,
        label_visibility="collapsed",
        disabled=field.locked,
    )
    provenance_column, approval_column, lock_column = st.columns([1.2, 1.2, 0.8])
    with provenance_column:
        field.provenance = _enum_select(
            "Provenance",
            field.provenance,
            Provenance,
            key=f"edit_{key}_provenance",
            disabled=field.locked,
        )
    with approval_column:
        field.approval = _enum_select(
            "Approval",
            field.approval,
            ApprovalStatus,
            key=f"edit_{key}_approval",
            disabled=field.locked,
        )
    with lock_column:
        field.locked = st.toggle(
            "Locked",
            value=field.locked,
            key=f"edit_{key}_locked",
        )


def _next_hinge_id(document: EpisodeDocument) -> str:
    used = {candidate.id for candidate in document.inquiry.hinge_candidates}
    index = 1
    while f"manual-hinge-{index}" in used:
        index += 1
    return f"manual-hinge-{index}"


def _render_dossier(document: EpisodeDocument) -> None:
    st.subheader("Episode dossier")
    title_column, uncle_column = st.columns(2)
    with title_column:
        document.episode.working_title = st.text_input(
            "Working title",
            value=document.episode.working_title,
            key="edit_working_title",
        )
    with uncle_column:
        document.episode.featured_uncle = st.text_input(
            "Featured Uncle",
            value=document.episode.featured_uncle,
            key="edit_featured_uncle",
        )

    registry_column, status_column = st.columns(2)
    with registry_column:
        registry_value = st.text_input(
            "Registry number",
            value=document.episode.registry_number or "",
            key="edit_registry_number",
            max_chars=5,
        )
        try:
            document.episode.registry_number = registry_value or None
        except ValidationError:
            st.error("Registry number must contain five digits beginning with 1.")
    with status_column:
        document.episode.status = _enum_select(
            "Status",
            document.episode.status,
            EpisodeStatus,
            key="edit_episode_status",
        )

    _editorial_field("Observed behaviour", document.episode.observed_behavior, key="observed")
    _editorial_field("Central artifact", document.episode.central_artifact, key="artifact")
    _editorial_field("Human stakes", document.episode.human_stakes, key="stakes")
    _editorial_field("AI-era problem", document.episode.ai_era_problem, key="ai_problem")


def _render_hinge_candidates(document: EpisodeDocument) -> None:
    st.markdown("### Hinge candidates")
    for candidate in list(document.inquiry.hinge_candidates):
        with st.container(border=True):
            heading_column, remove_column = st.columns([6, 1])
            heading_column.markdown(f"**{candidate.id}**")
            remove = remove_column.button(
                "Remove",
                key=f"hinge_remove_{candidate.id}",
                icon=":material/delete:",
                disabled=(
                    candidate.content.locked
                    or document.inquiry.selected_hinge_id == candidate.id
                ),
            )
            if remove:
                document.inquiry.hinge_candidates = [
                    item for item in document.inquiry.hinge_candidates if item.id != candidate.id
                ]
                st.rerun()
            _editorial_field(
                "Candidate",
                candidate.content,
                key=f"hinge_{candidate.id}",
                height=88,
            )

    if st.button("Add candidate", key="hinge_add", icon=":material/add:"):
        document.inquiry.hinge_candidates.append(
            HingeCandidate(
                id=_next_hinge_id(document),
                content=EditorialField(provenance=Provenance.HUMAN_OBSERVATION),
            )
        )
        st.rerun()

    candidate_ids = [candidate.id for candidate in document.inquiry.hinge_candidates]
    options = [""] + candidate_ids
    current = document.inquiry.selected_hinge_id or ""
    selected = st.radio(
        "Selected hinge",
        options,
        index=options.index(current) if current in options else 0,
        format_func=lambda value: "None selected" if not value else value,
        key="edit_selected_hinge",
        horizontal=True,
    )
    document.inquiry.selected_hinge_id = selected or None


def _render_comparators(document: EpisodeDocument) -> None:
    st.markdown("### Comparator sightings")
    for index, comparator in enumerate(list(document.closure.comparator_uncles)):
        with st.container(border=True):
            name_column, status_column, remove_column = st.columns([2, 2, 0.7])
            with name_column:
                comparator.name = st.text_input(
                    "Name",
                    value=comparator.name,
                    key=f"comparator_{index}_name",
                )
            with status_column:
                comparator.status = _enum_select(
                    "Status",
                    comparator.status,
                    ComparatorStatus,
                    key=f"comparator_{index}_status",
                )
            remove = remove_column.button(
                "Remove",
                key=f"comparator_{index}_remove",
                icon=":material/delete:",
            )
            comparator.observation = st.text_area(
                "Observation",
                value=comparator.observation,
                key=f"comparator_{index}_observation",
                height=76,
            )
            if remove:
                document.closure.comparator_uncles.pop(index)
                st.rerun()

    if st.button("Add comparator", key="comparator_add", icon=":material/add:"):
        document.closure.comparator_uncles.append(ComparatorUncle(name="New comparator"))
        st.rerun()


def _render_inquiry(document: EpisodeDocument) -> None:
    st.subheader("Inquiry architecture")
    _editorial_field("Opening question", document.inquiry.opening_question, key="opening_question")
    _render_hinge_candidates(document)

    _editorial_field("Productive detour", document.inquiry.productive_detour, key="detour")
    _editorial_field("Return from detour", document.inquiry.return_from_detour, key="return")
    _editorial_field(
        "Provisional finding",
        document.inquiry.provisional_finding,
        key="finding",
    )

    _render_comparators(document)
    _editorial_field(
        "Station assignment",
        document.closure.station_assignment,
        key="station_assignment",
    )
    _editorial_field("Final button", document.closure.final_button, key="final_button")
    _editorial_field(
        "Permanent archive addition",
        document.closure.permanent_archive_addition,
        key="archive_addition",
    )


def _render_beat_board(document: EpisodeDocument, pacing_config: PacingConfig) -> None:
    st.subheader("Timed beat board")
    metric_columns = st.columns(4)

    beat_ids = [beat.id for beat in document.beat_board.beats]
    selected_beat_id = st.selectbox(
        "Selected beat",
        beat_ids,
        format_func=lambda beat_id: next(
            f"{beat.core_order}. {beat.title}"
            for beat in document.beat_board.beats
            if beat.id == beat_id
        ),
        key="beat_selected",
    )
    beat = next(item for item in document.beat_board.beats if item.id == selected_beat_id)

    st.markdown(f"### {beat.core_order}. {beat.title}")
    beat.purpose = st.text_input(
        "Purpose",
        value=beat.purpose,
        key=f"beat_{beat.id}_purpose",
        disabled=beat.locked,
    )

    status_column, lock_column, words_column, seconds_column = st.columns(4)
    with status_column:
        from table_nine.domain.models import BeatStatus

        beat.status = _enum_select(
            "Status",
            beat.status,
            BeatStatus,
            key=f"beat_{beat.id}_status",
            disabled=beat.locked,
        )
    with lock_column:
        beat.locked = st.toggle(
            "Locked",
            value=beat.locked,
            key=f"beat_{beat.id}_locked",
        )
    with words_column:
        beat.target_words = int(
            st.number_input(
                "Target words",
                min_value=0,
                value=beat.target_words,
                step=10,
                key=f"beat_{beat.id}_target_words",
                disabled=beat.locked,
            )
        )
    with seconds_column:
        beat.target_seconds = int(
            st.number_input(
                "Target seconds",
                min_value=1,
                value=beat.target_seconds,
                step=5,
                key=f"beat_{beat.id}_target_seconds",
                disabled=beat.locked,
            )
        )

    speaker_column, temperature_column = st.columns(2)
    with speaker_column:
        beat.leading_speaker = st.text_input(
            "Leading speaker",
            value=beat.leading_speaker,
            key=f"beat_{beat.id}_speaker",
            disabled=beat.locked,
        )
    with temperature_column:
        temperatures = [None] + list(ConversationalTemperature)
        beat.temperature = st.selectbox(
            "Temperature",
            temperatures,
            index=temperatures.index(beat.temperature),
            format_func=lambda value: "Not set" if value is None else _label(value),
            key=f"beat_{beat.id}_temperature",
            disabled=beat.locked,
        )

    must_land_text = st.text_area(
        "Must land",
        value="\n".join(beat.must_land),
        key=f"beat_{beat.id}_must_land",
        height=80,
        disabled=beat.locked,
    )
    beat.must_land = [line.strip() for line in must_land_text.splitlines() if line.strip()]
    beat.artifact_or_visual = st.text_input(
        "Artifact or visual",
        value=beat.artifact_or_visual,
        key=f"beat_{beat.id}_artifact",
        disabled=beat.locked,
    )

    current_script_text = render_script_text(beat.script)
    script_contains_locks = any(element.locked for element in beat.script)
    script_text = st.text_area(
        "Script elements",
        value=current_script_text,
        key=f"beat_{beat.id}_script",
        height=280,
        placeholder="UNCLE_ONE: Dialogue\n[pause 1.2]\n[silence 2.0]",
        disabled=beat.locked or script_contains_locks,
    )
    if script_contains_locks and not beat.locked:
        st.warning("This script contains locked elements and cannot be replaced as a block.")
    if not beat.locked and not script_contains_locks and script_text != current_script_text:
        try:
            beat.script = parse_script_text(script_text, beat_id=beat.id)
        except (ScriptParseError, ValidationError) as exc:
            st.error(str(exc))

    pacing = calculate_episode_pacing(document, pacing_config)
    target_seconds = sum(item.target_seconds for item in document.beat_board.beats)
    target_words = sum(item.target_words for item in document.beat_board.beats)
    beat_pacing = next(item for item in pacing.beats if item.beat_id == selected_beat_id)

    metric_columns[0].metric("Spoken words", pacing.spoken_words)
    metric_columns[1].metric("Estimated runtime", _format_duration(pacing.total_seconds))
    metric_columns[2].metric("Target words", target_words)
    metric_columns[3].metric("Target runtime", _format_duration(target_seconds))

    beat_metrics = st.columns(3)
    beat_metrics[0].metric("Beat words", beat_pacing.spoken_words)
    beat_metrics[1].metric("Beat estimate", _format_duration(beat_pacing.total_seconds))
    beat_metrics[2].metric("Beat target", _format_duration(beat.target_seconds))


def _assistance_provider(provider_name: str, model_name: str):
    return build_provider(provider_name, model=model_name)


def _render_audits(document: EpisodeDocument, pacing_config: PacingConfig) -> AuditReport:
    st.subheader("Editorial audits")
    report = audit_document(document, pacing_config)
    scripted_beats = sum(bool(beat.script) for beat in document.beat_board.beats)

    metrics = st.columns(4)
    metrics[0].metric("Audit errors", report.count(AuditSeverity.ERROR))
    metrics[1].metric("Warnings", report.count(AuditSeverity.WARNING))
    metrics[2].metric("Notes", report.count(AuditSeverity.NOTE))
    metrics[3].metric("Scripted beats", f"{scripted_beats} / 9")

    severity_filter, category_filter, beat_filter = st.columns([1, 1.2, 1.4])
    with severity_filter:
        severity_options = [None] + list(AuditSeverity)
        selected_severity = st.selectbox(
            "Severity",
            severity_options,
            format_func=lambda value: "All severities" if value is None else _label(value),
            key="audit_severity",
        )
    with category_filter:
        category_options = [None] + list(AuditCategory)
        selected_category = st.selectbox(
            "Category",
            category_options,
            format_func=lambda value: "All categories" if value is None else _label(value),
            key="audit_category",
        )
    with beat_filter:
        beat_options = [""] + [beat.id for beat in document.beat_board.beats]
        selected_beat = st.selectbox(
            "Location",
            beat_options,
            format_func=lambda beat_id: "All locations"
            if not beat_id
            else next(
                f"{beat.core_order}. {beat.title}"
                for beat in document.beat_board.beats
                if beat.id == beat_id
            ),
            key="audit_beat",
        )

    findings = [
        finding
        for finding in report.findings
        if (selected_severity is None or finding.severity == selected_severity)
        and (selected_category is None or finding.category == selected_category)
        and (not selected_beat or finding.beat_id == selected_beat)
    ]
    st.caption(f"Showing {len(findings)} of {len(report.findings)} findings")
    if not findings:
        st.success("No deterministic findings match the current filters.")
        return report

    beat_titles = {beat.id: beat.title for beat in document.beat_board.beats}
    rows = [
        {
            "Severity": finding.severity.value.upper(),
            "Category": finding.category.value.title(),
            "Location": beat_titles.get(finding.beat_id or "", "Episode"),
            "Finding": finding.title,
            "Diagnostic": (
                f"{finding.detail} Evidence: {finding.evidence}"
                if finding.evidence
                else finding.detail
            ),
        }
        for finding in findings
    ]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_order=[
            "Severity",
            "Category",
            "Location",
            "Finding",
            "Diagnostic",
        ],
        height=min(680, 38 + 35 * len(rows)),
    )
    return report


def _render_revision_diagnostics(report: AuditReport, beat_id: str) -> None:
    st.markdown("### Selected-beat diagnostics")
    findings = report.for_beat(beat_id)
    if not findings:
        st.success("No deterministic findings for this beat.")
        return

    for finding in findings[:5]:
        message = f"**{finding.title}.** {finding.detail}"
        if finding.evidence:
            message = f"{message} {finding.evidence}"
        if finding.severity == AuditSeverity.ERROR:
            st.error(message)
        elif finding.severity == AuditSeverity.WARNING:
            st.warning(message)
        else:
            st.info(message)
    if len(findings) > 5:
        st.caption(f"{len(findings) - 5} additional findings are available in Audits.")


def _render_suggestion(document: EpisodeDocument, suggestion) -> None:
    kind_label = _label(suggestion.kind)
    with st.container(border=True):
        heading, status = st.columns([4, 1])
        heading.markdown(f"**{kind_label}**")
        status.caption(_label(suggestion.status))
        target = f" | Beat: {suggestion.target_beat_id}" if suggestion.target_beat_id else ""
        st.caption(
            f"Machine suggestion | {suggestion.provider} | {suggestion.model}{target}"
        )
        if suggestion.instruction:
            st.markdown(f"Instruction: {suggestion.instruction}")

        for index, option in enumerate(suggestion.options):
            if index:
                st.divider()
            st.markdown(f"**{option.title}**")
            if suggestion.kind == SuggestionKind.HINGE_CANDIDATES:
                st.write(option.content)
                if option.rationale:
                    st.caption(f"Causal chain: {option.rationale}")
                action_label = "Add as candidate"
            else:
                st.code(option.content, language="text")
                if option.rationale:
                    st.caption(option.rationale)
                action_label = "Apply as draft"

            already_applied = option.id in suggestion.applied_option_ids
            apply_disabled = already_applied or suggestion.status == SuggestionStatus.DISMISSED
            if suggestion.kind != SuggestionKind.HINGE_CANDIDATES:
                apply_disabled = apply_disabled or suggestion.status != SuggestionStatus.PENDING
                if suggestion.target_beat_id:
                    beat = next(
                        item
                        for item in document.beat_board.beats
                        if item.id == suggestion.target_beat_id
                    )
                    apply_disabled = apply_disabled or beat.locked or any(
                        element.locked for element in beat.script
                    )

            if st.button(
                action_label,
                key=f"assist_apply_{suggestion.id}_{option.id}",
                icon=":material/add:",
                disabled=apply_disabled,
            ):
                try:
                    if suggestion.kind == SuggestionKind.HINGE_CANDIDATES:
                        apply_hinge_option(
                            document,
                            suggestion_id=suggestion.id,
                            option_id=option.id,
                        )
                        notice = "Candidate added without selecting it."
                    else:
                        apply_beat_option(
                            document,
                            suggestion_id=suggestion.id,
                            option_id=option.id,
                        )
                        st.session_state.pop(
                            f"beat_{suggestion.target_beat_id}_script",
                            None,
                        )
                        notice = "Suggestion applied as an unapproved machine draft."
                except (AssistanceError, LockedContentError, ScriptParseError, ValidationError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state.assist_notice = notice
                    st.rerun()

        if st.button(
            "Dismiss suggestion",
            key=f"assist_dismiss_{suggestion.id}",
            icon=":material/close:",
            disabled=suggestion.status in {
                SuggestionStatus.APPLIED,
                SuggestionStatus.DISMISSED,
            },
        ):
            try:
                dismiss_suggestion(document, suggestion_id=suggestion.id)
            except AssistanceError as exc:
                st.error(str(exc))
            else:
                st.session_state.assist_notice = "Suggestion dismissed."
                st.rerun()


def _render_assistance(
    document: EpisodeDocument,
    *,
    provider_name: str,
    model_name: str,
    pacing_config: PacingConfig,
) -> None:
    st.subheader("Assisted writing")
    notice = st.session_state.pop("assist_notice", None)
    if notice:
        st.success(notice)

    operation = st.radio(
        "Operation",
        ["Hinge candidates", "Draft selected beat", "Revise selected beat"],
        key="assist_operation",
        horizontal=True,
    )
    beat_id = None
    if operation != "Hinge candidates":
        beat_ids = [beat.id for beat in document.beat_board.beats]
        beat_id = st.selectbox(
            "Selected beat",
            beat_ids,
            format_func=lambda selected_id: next(
                f"{beat.core_order}. {beat.title}"
                for beat in document.beat_board.beats
                if beat.id == selected_id
            ),
            key="assist_selected_beat",
        )
        selected_beat = next(beat for beat in document.beat_board.beats if beat.id == beat_id)
        if selected_beat.locked or any(element.locked for element in selected_beat.script):
            st.warning("The selected beat contains locked content.")
        if operation == "Revise selected beat":
            _render_revision_diagnostics(
                audit_document(document, pacing_config),
                selected_beat.id,
            )

    instruction = st.text_area(
        "Editorial instruction",
        key="assist_instruction",
        height=92,
    )
    generate_disabled = False
    if beat_id:
        selected_beat = next(beat for beat in document.beat_board.beats if beat.id == beat_id)
        generate_disabled = selected_beat.locked or any(
            element.locked for element in selected_beat.script
        )
        if operation == "Revise selected beat" and not selected_beat.script:
            generate_disabled = True

    if st.button(
        "Generate suggestions",
        key="assist_generate",
        type="primary",
        icon=":material/auto_awesome:",
        disabled=generate_disabled,
    ):
        try:
            provider = _assistance_provider(provider_name, model_name)
            with st.spinner("Generating bounded alternatives..."):
                if operation == "Hinge candidates":
                    generate_hinge_suggestion(
                        document,
                        provider,
                        instruction=instruction,
                    )
                else:
                    generate_beat_suggestion(
                        document,
                        provider,
                        beat_id=beat_id or "",
                        instruction=instruction,
                        revision=operation == "Revise selected beat",
                    )
        except (
            AssistanceError,
            LockedContentError,
            ProviderError,
            ScriptParseError,
            ValidationError,
        ) as exc:
            st.error(str(exc))
        else:
            st.session_state.assist_notice = "Machine suggestions are ready for review."
            st.rerun()

    st.markdown("### Suggestion ledger")
    if not document.suggestions:
        st.caption("No suggestions in this working revision.")
    for suggestion in reversed(document.suggestions):
        _render_suggestion(document, suggestion)


def _render_exports(document: EpisodeDocument, source_filename: str) -> None:
    st.subheader("Markdown exports")
    bundle = build_exports(document, source_filename)
    files = (
        ("Dossier", bundle.dossier),
        ("Beat board", bundle.beat_board),
        ("Performance script", bundle.performance_script),
        ("Archive stub", bundle.archive_stub),
    )
    columns = st.columns(2)
    for index, (label, export_file) in enumerate(files):
        with columns[index % 2]:
            st.download_button(
                label,
                data=export_file.content,
                file_name=export_file.filename,
                mime="text/markdown",
                key=f"export_{index}",
                icon=":material/download:",
                width="stretch",
            )

    with st.expander("Performance script preview"):
        st.code(bundle.performance_script.content, language="markdown")


def _render_gate(gate: ProductionGate) -> None:
    st.markdown(f"### {gate.name} gate")
    rows = [
        {
            "Status": "PASS" if check.passed else "BLOCKED",
            "Check": check.label,
            "Detail": check.detail,
        }
        for check in gate.checks
    ]
    st.dataframe(
        rows,
        hide_index=True,
        width="stretch",
        column_order=["Status", "Check", "Detail"],
        height=38 + 35 * len(rows),
    )


def _render_production(
    document: EpisodeDocument,
    source_filename: str,
    pacing_config: PacingConfig,
    *,
    has_unsaved_changes: bool,
) -> None:
    st.subheader("Production handoff")
    report = audit_document(document, pacing_config)
    readiness = evaluate_production_readiness(
        document,
        report,
        has_unsaved_changes=has_unsaved_changes,
    )

    metrics = st.columns(4)
    metrics[0].metric(
        "Table-read gate",
        "READY" if readiness.table_read.ready else "BLOCKED",
    )
    metrics[1].metric(
        "Release gate",
        "READY" if readiness.release.ready else "BLOCKED",
    )
    metrics[2].metric("Working state", "UNSAVED" if has_unsaved_changes else "SAVED")
    metrics[3].metric("Audit errors", report.count(AuditSeverity.ERROR))
    st.caption(f"Source revision {document.document.revision}")

    table_gate, release_gate = st.columns(2)
    with table_gate:
        _render_gate(readiness.table_read)
    with release_gate:
        _render_gate(readiness.release)

    development_package = build_production_package(
        document,
        source_filename,
        kind=PackageKind.DEVELOPMENT,
        pacing_config=pacing_config,
        has_unsaved_changes=has_unsaved_changes,
    )
    table_read_package = (
        build_production_package(
            document,
            source_filename,
            kind=PackageKind.TABLE_READ,
            pacing_config=pacing_config,
            has_unsaved_changes=has_unsaved_changes,
        )
        if readiness.table_read.ready
        else None
    )
    release_package = (
        build_production_package(
            document,
            source_filename,
            kind=PackageKind.RELEASE,
            pacing_config=pacing_config,
            has_unsaved_changes=has_unsaved_changes,
        )
        if readiness.release.ready
        else None
    )

    st.markdown("### Packages")
    package_columns = st.columns(3)
    with package_columns[0]:
        st.download_button(
            "Development package",
            data=development_package.content,
            file_name=development_package.filename,
            mime="application/zip",
            icon=":material/folder_zip:",
            width="stretch",
        )
    with package_columns[1]:
        st.download_button(
            "Table-read package",
            data=table_read_package.content if table_read_package else b"",
            file_name=(
                table_read_package.filename
                if table_read_package
                else "TableNine-TableReadPackage.zip"
            ),
            mime="application/zip",
            icon=":material/folder_zip:",
            width="stretch",
            disabled=table_read_package is None,
        )
    with package_columns[2]:
        st.download_button(
            "Release package",
            data=release_package.content if release_package else b"",
            file_name=(
                release_package.filename
                if release_package
                else "TableNine-ReleasePackage.zip"
            ),
            mime="application/zip",
            icon=":material/folder_zip:",
            width="stretch",
            disabled=release_package is None,
        )

    st.divider()
    _render_exports(document, source_filename)


def main() -> None:
    st.set_page_config(
        page_title="Table Nine Script Workbench",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {max-width: 1440px; padding-top: 1.4rem; padding-bottom: 3rem;}
        h1, h2, h3, h4 {letter-spacing: 0 !important;}
        [data-testid="stMetric"] {border-top: 2px solid #8aa4a1; padding-top: .65rem;}
        [data-testid="stSidebar"] {border-right: 1px solid #c8d0ce;}
        [data-testid="stDownloadButton"] button {min-height: 2.7rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    repository = EpisodeRepository(SCRIPTS_ROOT)
    filenames = repository.list_episode_files()

    st.sidebar.title("Table Nine")
    st.sidebar.caption("Script Workbench")
    _render_new_pilot(repository)

    notice = st.session_state.pop("new_pilot_notice", None)
    if notice:
        st.sidebar.success(notice)

    if not filenames:
        st.title("Table Nine Script Workbench")
        st.info("No pilot documents found.")
        st.stop()

    selected_filename = st.sidebar.selectbox(
        "Episode document",
        filenames,
        key="selected_filename",
    )
    _load_selected(repository, selected_filename)

    document: EpisodeDocument = st.session_state.document
    original: EpisodeDocument = st.session_state.original_document
    save_slot = st.sidebar.empty()

    if st.sidebar.button(
        "Reload from disk",
        icon=":material/refresh:",
        width="stretch",
    ):
        _load_selected(repository, selected_filename, force=True)
        st.rerun()

    default_wpm = st.sidebar.slider(
        "Provisional speaking rate",
        min_value=80,
        max_value=180,
        value=120,
        step=5,
        format="%d WPM",
    )
    pacing_config = PacingConfig(default_wpm=float(default_wpm))

    st.sidebar.divider()
    st.sidebar.subheader("Assistance")
    provider_name = st.sidebar.selectbox(
        "Provider",
        ["mock", "openai"],
        format_func=lambda value: "Deterministic mock" if value == "mock" else "OpenAI",
        key="assist_provider",
    )
    model_name = ""
    if provider_name == "openai":
        model_name = st.sidebar.text_input(
            "Model",
            value=os.environ.get("TABLE_NINE_OPENAI_MODEL", ""),
            key="assist_model",
        )
        key_status = "API key configured" if os.environ.get("OPENAI_API_KEY") else "API key not configured"
        st.sidebar.caption(key_status)

    st.title("Table Nine Script Workbench")
    st.caption(
        f"{document.episode.featured_uncle or 'Untitled episode'}  |  "
        f"Revision {original.document.revision}  |  {selected_filename}"
    )

    dossier_tab, inquiry_tab, board_tab, audits_tab, assist_tab, production_tab = st.tabs(
        ["Dossier", "Inquiry", "Beats", "Audits", "Assist", "Handoff"]
    )
    with dossier_tab:
        _render_dossier(document)
    with inquiry_tab:
        _render_inquiry(document)
    with board_tab:
        _render_beat_board(document, pacing_config)
    with audits_tab:
        _render_audits(document, pacing_config)
    with assist_tab:
        _render_assistance(
            document,
            provider_name=provider_name,
            model_name=model_name,
            pacing_config=pacing_config,
        )
    with production_tab:
        _render_production(
            document,
            selected_filename,
            pacing_config,
            has_unsaved_changes=(
                document.model_dump(mode="json") != original.model_dump(mode="json")
            ),
        )

    has_changes = document.model_dump(mode="json") != original.model_dump(mode="json")
    st.sidebar.caption("Unsaved changes" if has_changes else "Saved")

    with save_slot.container():
        if st.button(
            "Save episode",
            type="primary",
            icon=":material/save:",
            width="stretch",
            disabled=not has_changes,
        ):
            try:
                saved = save_episode(
                    repository,
                    selected_filename,
                    original,
                    document,
                )
            except (LockedContentError, RepositoryError, ValidationError, OSError) as exc:
                st.sidebar.error(str(exc))
            else:
                st.session_state.document = saved.model_copy(deep=True)
                st.session_state.original_document = saved.model_copy(deep=True)
                _clear_editor_state()
                st.sidebar.success(f"Saved revision {saved.document.revision}")
                st.rerun()


if __name__ == "__main__":
    main()
