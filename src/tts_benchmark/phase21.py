"""Phase 2.1 blind-review aggregation helpers."""

from __future__ import annotations

import csv
import json
import math
import posixpath
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

UNASSESSED_REVIEW_FIELDS = (
    "instruction_match",
    "pronunciation_quality",
    "would_use",
    "reading_issue",
    "note",
)

_UNASSESSED_MEANS = {
    "instruction_match_mean": None,
    "pronunciation_quality_mean": None,
    "would_use_mean": None,
    "reading_issue_count": None,
    "note": None,
}

_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XLSX_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_REVIEW_COLUMNS = (
    "sample_id",
    "category",
    "case_id",
    "text",
    "instruction",
    "naturalness",
    "instruction_match",
    "pronunciation_quality",
    "would_use",
    "reading_issue",
    "note",
    "completed",
)

PUBLIC_ENGINE_IDS = frozenset(
    {
        "irodori_tts",
        "qwen3_tts",
        "style_bert_vits2",
        "voicevox",
    }
)
PUBLIC_CASE_IDS = frozenset({"p03", "p05", "p13", "x01", "x02", "x03"})
PUBLIC_CATEGORIES = frozenset({"expression", "pronunciation"})
_SAMPLE_ID_PATTERN = re.compile(r"S\d{2}\Z")
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")


def _column_number(cell_reference: str) -> int:
    letters = "".join(character for character in cell_reference if character.isalpha())
    value = 0
    for character in letters.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    if cell.find(f"{{{_XLSX_MAIN_NS}}}f") is not None:
        raise ValueError("review workbook must not contain formulas")
    inline = cell.find(f"{{{_XLSX_MAIN_NS}}}is")
    if inline is not None:
        return "".join(text.text or "" for text in inline.iter(f"{{{_XLSX_MAIN_NS}}}t"))
    value = cell.find(f"{{{_XLSX_MAIN_NS}}}v")
    if value is None:
        return None
    if cell.get("t") == "s":
        try:
            return shared_strings[int(value.text or "0")]
        except (IndexError, ValueError) as exc:
            raise ValueError("review workbook has an invalid shared string") from exc
    if cell.get("t") == "b":
        return value.text == "1"
    return value.text


def load_review_workbook(path: str | Path) -> list[dict[str, Any]]:
    """Read the first worksheet's review rows without evaluating formulas."""
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(text.text or "" for text in item.iter(f"{{{_XLSX_MAIN_NS}}}t"))
                for item in shared_root
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation_targets = {
            relation.get("Id"): relation.get("Target")
            for relation in relationships.findall(
                f"{{{_XLSX_PACKAGE_REL_NS}}}Relationship"
            )
        }
        sheet = workbook.find(f"{{{_XLSX_MAIN_NS}}}sheets/{{{_XLSX_MAIN_NS}}}sheet")
        if sheet is None:
            raise ValueError("review workbook has no worksheet")
        relation_id = sheet.get(f"{{{_XLSX_REL_NS}}}id")
        target = relation_targets.get(relation_id)
        if not target:
            raise ValueError("review workbook worksheet relationship is missing")
        sheet_path = posixpath.normpath(posixpath.join("xl", target.lstrip("/")))
        if sheet_path not in names:
            raise ValueError(f"review workbook worksheet is missing: {sheet_path}")
        worksheet = ET.fromstring(archive.read(sheet_path))
        rows: list[dict[int, Any]] = []
        for row in worksheet.findall(
            f"{{{_XLSX_MAIN_NS}}}sheetData/{{{_XLSX_MAIN_NS}}}row"
        ):
            values: dict[int, Any] = {}
            for cell in row.findall(f"{{{_XLSX_MAIN_NS}}}c"):
                reference = cell.get("r")
                if reference:
                    values[_column_number(reference)] = _xlsx_cell_value(
                        cell, shared_strings
                    )
            rows.append(values)

    header_index = next(
        (index for index, values in enumerate(rows) if values.get(1) == "sample_id"),
        None,
    )
    if header_index is None:
        raise ValueError("review workbook is missing the sample_id header")
    header = rows[header_index]
    if (
        tuple(header.get(index) for index in range(1, len(_REVIEW_COLUMNS) + 1))
        != _REVIEW_COLUMNS
    ):
        raise ValueError("review workbook headers do not match the Phase 2.1 schema")

    review_rows: list[dict[str, Any]] = []
    for values in rows[header_index + 1 :]:
        if not any(
            value is not None and str(value).strip() for value in values.values()
        ):
            continue
        row = {
            column: values.get(index) or None
            for index, column in enumerate(_REVIEW_COLUMNS, 1)
        }
        if row["naturalness"] is not None:
            try:
                row["naturalness"] = float(row["naturalness"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{row.get('sample_id')} naturalness must be numeric"
                ) from exc
        review_rows.append(row)
    return review_rows


def validate_naturalness_only(
    rows: list[dict[str, Any]], blind_items: list[dict[str, Any]]
) -> None:
    """Validate a completed sheet where naturalness is the only scored field."""
    by_sample: dict[str, dict[str, Any]] = {}
    for item in blind_items:
        sample_id = item.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError("blind map sample_id must be a non-empty string")
        if sample_id in by_sample:
            raise ValueError(f"duplicate blind map sample_id: {sample_id}")
        by_sample[sample_id] = item
    if len(rows) != len(by_sample):
        raise ValueError("review row count does not match blind map")

    seen: set[str] = set()
    for row in rows:
        sample_id = row.get("sample_id")
        if sample_id not in by_sample:
            raise ValueError(f"review sample_id is not in blind map: {sample_id}")
        if sample_id in seen:
            raise ValueError(f"duplicate review sample_id: {sample_id}")
        seen.add(sample_id)
        mapped = by_sample[sample_id]
        for field in ("case_id", "category"):
            if row.get(field) != mapped.get(field):
                raise ValueError(f"{sample_id} {field} does not match blind map")
        try:
            score = float(row.get("naturalness"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{sample_id} naturalness must be numeric") from exc
        if not math.isfinite(score) or not 1.0 <= score <= 5.0:
            raise ValueError(f"{sample_id} naturalness must be between 1 and 5")
        for field in UNASSESSED_REVIEW_FIELDS:
            value = row.get(field)
            if value is not None and str(value).strip():
                raise ValueError(f"{sample_id} {field} must remain null")
        if row.get("completed") != "完了":
            raise ValueError(f"{sample_id} completed status must be 完了")


def validate_phase21_identifiers(
    blind_items: list[dict[str, Any]], *, expected_sample_count: int | None = None
) -> None:
    """Allow only the fixed public identifiers before map-derived aggregation."""
    if not isinstance(blind_items, list):
        raise TypeError("Phase 2.1 blind map items must be a list")
    if expected_sample_count is not None and len(blind_items) != expected_sample_count:
        raise ValueError(
            "Phase 2.1 blind map count does not match the fixed review set"
        )
    sample_ids: set[str] = set()
    for item in blind_items:
        if not isinstance(item, dict):
            raise TypeError("Phase 2.1 blind map item must be an object")
        sample_id = item.get("sample_id")
        if not isinstance(sample_id, str) or not _SAMPLE_ID_PATTERN.fullmatch(
            sample_id
        ):
            raise ValueError("Phase 2.1 blind map sample_id is not allowlisted")
        if sample_id in sample_ids:
            raise ValueError(f"duplicate Phase 2.1 blind map sample_id: {sample_id}")
        sample_ids.add(sample_id)
        engine_id = item.get("engine_id")
        if engine_id not in PUBLIC_ENGINE_IDS:
            raise ValueError("Phase 2.1 blind map engine_id is not allowlisted")
        case_id = item.get("case_id")
        if case_id not in PUBLIC_CASE_IDS:
            raise ValueError("Phase 2.1 blind map case_id is not allowlisted")
        category = item.get("category")
        if category not in PUBLIC_CATEGORIES:
            raise ValueError("Phase 2.1 blind map category is not allowlisted")


def validate_phase21_provenance(source_commit: str, source_tag: str) -> None:
    """Reject provenance values that could carry arbitrary private text."""
    if not isinstance(source_commit, str) or not _COMMIT_PATTERN.fullmatch(
        source_commit
    ):
        raise ValueError("Phase 2.1 source commit must be a 40-character SHA")
    if not isinstance(source_tag, str) or not _TAG_PATTERN.fullmatch(source_tag):
        raise ValueError("Phase 2.1 source tag must be a semantic version tag")


def validate_phase21_recommendation(recommendation: dict[str, Any]) -> None:
    """Reject private fields/paths and accidental human-score merging."""
    if not isinstance(recommendation, dict):
        raise TypeError("Phase 2.1 recommendation must be an object")
    forbidden_keys = {
        "sample_id",
        "audio_filename",
        "audio_path",
        "blind_map",
        "blind_mapping",
        "blind_mapping_hash",
        "model_id",
        "model_name",
        "model_snapshot",
        "model",
        "speaker_id",
        "speaker_name",
        "speaker",
        "character_name",
        "character",
        "engine_name",
        "reference_audio",
    }
    private_path = re.compile(
        r"(?i)^(?:/|~[/\\]|[A-Za-z]:[/\\])"
        r"|(?:^|[/\\])(?:home|mnt|tmp|users|reviewer_package|owner_private|audio_private)"
        r"(?:[/\\]|$)"
        r"|(?:^|[/\\])\.\.(?:[/\\]|$)"
        r"|\.(?:wav|safetensors|pt|bin|env)(?:$|[/\\])"
    )

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith(("_path", "_file", "_filename")):
                    raise ValueError(
                        f"public recommendation contains private path field: {key}"
                    )
                if key in forbidden_keys:
                    raise ValueError(
                        f"public recommendation contains private field: {key}"
                    )
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and private_path.search(value):
            raise ValueError("public recommendation contains private path value")

    walk(recommendation)
    comparison = recommendation.get("comparison")
    if not isinstance(comparison, list):
        raise TypeError("Phase 2.1 recommendation comparison must be a list")
    for row in comparison:
        if not isinstance(row, dict):
            raise TypeError("Phase 2.1 recommendation comparison row must be an object")
        other_dimensions = row.get("human_other_dimensions")
        if not isinstance(other_dimensions, dict):
            raise TypeError("Phase 2.1 recommendation missing null human dimensions")
        for field in _UNASSESSED_MEANS:
            if other_dimensions.get(field) is not None:
                raise ValueError(f"{field} must remain null in recommendation")
    machine_human = recommendation.get("machine_human_comparison")
    if (
        not isinstance(machine_human, dict)
        or machine_human.get("single_score") is not False
    ):
        raise ValueError("Phase 2.1 recommendation must keep metrics separate")


def _aggregate_row(
    engine_id: str, case_id: str, category: str, scores: list[float]
) -> dict[str, Any]:
    return {
        "engine_id": engine_id,
        "case_id": case_id,
        "category": category,
        "naturalness_mean": round(fmean(scores), 3),
        "naturalness_n": len(scores),
        **_UNASSESSED_MEANS,
    }


def aggregate_naturalness(
    rows: list[dict[str, Any]], blind_items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregate the naturalness-only scores after applying the private blind map."""
    validate_naturalness_only(rows, blind_items)
    by_sample = {item["sample_id"]: item for item in blind_items}
    engine_case: defaultdict[tuple[str, str, str], list[float]] = defaultdict(list)
    engine: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        item = by_sample[row["sample_id"]]
        score = float(row["naturalness"])
        key = (item["engine_id"], item["case_id"], item["category"])
        engine_case[key].append(score)
        engine[item["engine_id"]].append(score)

    case_rows = [
        _aggregate_row(engine_id, case_id, category, scores)
        for (engine_id, case_id, category), scores in sorted(engine_case.items())
    ]
    engine_rows = [
        {
            "engine_id": engine_id,
            "naturalness_mean": round(fmean(scores), 3),
            "naturalness_n": len(scores),
            **_UNASSESSED_MEANS,
        }
        for engine_id, scores in sorted(engine.items())
    ]
    return {
        "sample_count": len(rows),
        "reviewed_dimensions": ["naturalness"],
        "not_evaluated_dimensions": [
            "instruction_match",
            "pronunciation_quality",
            "would_use",
            "reading_issue",
            "note",
        ],
        "engine_aggregates": engine_rows,
        "engine_case_aggregates": case_rows,
    }


def validate_phase21_summary(
    summary: dict[str, Any],
    *,
    expected_sample_count: int | None = None,
    allowed_engine_ids: frozenset[str] | None = None,
    allowed_case_ids: frozenset[str] | None = None,
    allowed_categories: frozenset[str] | None = None,
) -> None:
    """Fail closed on the public naturalness-only summary contract."""
    required = {
        "schema_version",
        "phase",
        "status",
        "sample_count",
        "reviewed_dimensions",
        "not_evaluated_dimensions",
        "engine_aggregates",
        "engine_case_aggregates",
    }
    missing = sorted(required - summary.keys())
    if missing:
        raise ValueError(
            f"Phase 2.1 summary missing required fields: {', '.join(missing)}"
        )
    if summary["schema_version"] != "phase2.1-human-review-summary-1":
        raise ValueError("invalid Phase 2.1 human-review schema version")
    if summary["phase"] != "phase2.1" or summary["status"] != "complete":
        raise ValueError("Phase 2.1 human-review summary is not complete")
    if not isinstance(summary["sample_count"], int) or summary["sample_count"] < 1:
        raise ValueError("Phase 2.1 sample_count must be a positive integer")
    if (
        expected_sample_count is not None
        and summary["sample_count"] != expected_sample_count
    ):
        raise ValueError("Phase 2.1 sample_count does not match the fixed review set")
    if summary["reviewed_dimensions"] != ["naturalness"]:
        raise ValueError(
            "Phase 2.1 must contain naturalness as its only reviewed dimension"
        )
    if summary["not_evaluated_dimensions"] != list(UNASSESSED_REVIEW_FIELDS):
        raise ValueError("Phase 2.1 unassessed dimensions are inconsistent")

    def check_aggregate(row: dict[str, Any], *, case_level: bool) -> None:
        required_fields = {
            "engine_id",
            "naturalness_mean",
            "naturalness_n",
            *_UNASSESSED_MEANS,
        }
        if case_level:
            required_fields.update({"case_id", "category"})
        missing_fields = sorted(required_fields - row.keys())
        if missing_fields:
            raise ValueError(
                f"Phase 2.1 aggregate missing required fields: {', '.join(missing_fields)}"
            )
        if not isinstance(row["engine_id"], str) or not row["engine_id"]:
            raise ValueError("Phase 2.1 aggregate engine_id must be non-empty")
        if (
            allowed_engine_ids is not None
            and row["engine_id"] not in allowed_engine_ids
        ):
            raise ValueError("Phase 2.1 aggregate engine_id is not allowlisted")
        if (
            case_level
            and allowed_case_ids is not None
            and row["case_id"] not in allowed_case_ids
        ):
            raise ValueError("Phase 2.1 aggregate case_id is not allowlisted")
        if (
            case_level
            and allowed_categories is not None
            and row["category"] not in allowed_categories
        ):
            raise ValueError("Phase 2.1 aggregate category is not allowlisted")
        if not isinstance(row["naturalness_n"], int) or row["naturalness_n"] < 1:
            raise ValueError("Phase 2.1 naturalness_n must be a positive integer")
        score = row["naturalness_mean"]
        if (
            not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or not 1 <= score <= 5
        ):
            raise ValueError("Phase 2.1 naturalness_mean must be between 1 and 5")
        for field in _UNASSESSED_MEANS:
            if row[field] is not None:
                raise ValueError(f"{field} must remain null")

    engine_rows = summary["engine_aggregates"]
    case_rows = summary["engine_case_aggregates"]
    if not isinstance(engine_rows, list) or not isinstance(case_rows, list):
        raise TypeError("Phase 2.1 aggregates must be lists")
    engine_ids: set[str] = set()
    for row in engine_rows:
        check_aggregate(row, case_level=False)
        if row["engine_id"] in engine_ids:
            raise ValueError(
                f"duplicate Phase 2.1 engine aggregate: {row['engine_id']}"
            )
        engine_ids.add(row["engine_id"])
    case_keys: set[tuple[str, str, str]] = set()
    for row in case_rows:
        check_aggregate(row, case_level=True)
        key = (row["engine_id"], row["case_id"], row["category"])
        if key in case_keys:
            raise ValueError(f"duplicate Phase 2.1 engine/case aggregate: {key}")
        case_keys.add(key)
    if sum(row["naturalness_n"] for row in engine_rows) != summary["sample_count"]:
        raise ValueError("Phase 2.1 engine aggregates do not cover sample_count")
    if sum(row["naturalness_n"] for row in case_rows) != summary["sample_count"]:
        raise ValueError("Phase 2.1 case aggregates do not cover sample_count")

    forbidden_keys = {
        "sample_id",
        "audio_filename",
        "audio_path",
        "provisional_id",
        "blind_mapping_hash",
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if forbidden_keys.intersection(value):
                found = min(forbidden_keys.intersection(value))
                raise ValueError(
                    f"public Phase 2.1 summary contains private field: {found}"
                )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(summary)


def build_final_recommendation(
    phase2_summary: dict[str, Any], human_summary: dict[str, Any]
) -> dict[str, Any]:
    """Build a comparison without collapsing human and machine metrics."""
    human_by_engine = {
        row["engine_id"]: row for row in human_summary.get("engine_aggregates", [])
    }
    comparison: list[dict[str, Any]] = []
    for engine in phase2_summary.get("engines", []):
        engine_id = engine["engine_id"]
        target_out = engine.get("phase2_measurement_status") == "対象外"
        human = human_by_engine.get(engine_id, {})
        raw_reading = [
            row
            for row in phase2_summary.get("reading_variants", [])
            if row.get("engine_id") == engine_id
            and row.get("variant") == "raw"
            and str(row.get("case_id", "")).startswith("p")
        ]
        reading_counts = dict(
            Counter(row.get("pronunciation_result") for row in raw_reading)
        )
        comparison.append(
            {
                "engine_id": engine_id,
                "measurement_status": engine.get("phase2_measurement_status"),
                "machine_metrics": {
                    "content_cer_mean": None
                    if target_out
                    else engine.get("content_cer_mean"),
                    "generation_rtf_mean": None
                    if target_out
                    else engine.get("generation_rtf_mean"),
                    "same_speaker_multi_style": None
                    if target_out
                    else engine.get("same_speaker_multi_style"),
                    "raw_pronunciation_counts": reading_counts,
                },
                "human_naturalness": {
                    "naturalness_mean": human.get("naturalness_mean"),
                    "naturalness_n": human.get("naturalness_n", 0),
                },
                "human_other_dimensions": {
                    key: human.get(key) for key in _UNASSESSED_MEANS
                },
            }
        )

    scored = [
        row
        for row in comparison
        if row["human_naturalness"]["naturalness_mean"] is not None
    ]
    if scored:
        highest = max(row["human_naturalness"]["naturalness_mean"] for row in scored)
        leaders = [
            row["engine_id"]
            for row in scored
            if row["human_naturalness"]["naturalness_mean"] == highest
        ]
        leaders.sort()
    else:
        leaders = []
    case_rows = human_summary.get("engine_case_aggregates", [])
    expression_rows = [row for row in case_rows if row.get("category") == "expression"]
    expression_by_engine: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in expression_rows:
        expression_by_engine[row["engine_id"]].append(row)
    expression_means: dict[str, float] = {}
    for engine_id, rows_for_engine in expression_by_engine.items():
        weighted_scores = [
            row["naturalness_mean"] * row["naturalness_n"] for row in rows_for_engine
        ]
        total_n = sum(row["naturalness_n"] for row in rows_for_engine)
        if total_n:
            expression_means[engine_id] = round(sum(weighted_scores) / total_n, 3)
    expression_leaders: list[str] = []
    if expression_means:
        expression_highest = max(expression_means.values())
        expression_leaders = [
            engine_id
            for engine_id, score in sorted(expression_means.items())
            if score == expression_highest
        ]
    measured = [row for row in comparison if row["measurement_status"] != "対象外"]
    cer_values = {
        row["engine_id"]: row["machine_metrics"]["content_cer_mean"]
        for row in measured
        if isinstance(row["machine_metrics"]["content_cer_mean"], (int, float))
    }
    rtf_values = {
        row["engine_id"]: row["machine_metrics"]["generation_rtf_mean"]
        for row in measured
        if isinstance(row["machine_metrics"]["generation_rtf_mean"], (int, float))
    }
    cer_leaders = (
        [
            engine_id
            for engine_id, value in sorted(cer_values.items())
            if value == min(cer_values.values())
        ]
        if cer_values
        else []
    )
    rtf_leaders = (
        [
            engine_id
            for engine_id, value in sorted(rtf_values.items())
            if value == min(rtf_values.values())
        ]
        if rtf_values
        else []
    )
    default_candidates = sorted(
        leaders,
        key=lambda engine_id: (rtf_values.get(engine_id, float("inf")), engine_id),
    )
    default_candidate = default_candidates[0] if default_candidates else None
    same_speaker_candidates = [
        row["engine_id"]
        for row in measured
        if row["machine_metrics"]["same_speaker_multi_style"] is True
    ]
    return {
        "recommendations": {
            "human_naturalness": {
                "leader_engine_ids": leaders,
                "basis": "naturalness_mean only; other human dimensions are null",
            },
            "best_single_engine": {
                "default_candidate": default_candidate,
                "naturalness_leader_engine_ids": leaders,
                "selection_policy": "naturalness leaders, then lowest measured RTF; no composite score",
                "status": "provisional" if default_candidate else "not_available",
            },
            "expression_naturalness": {
                "leader_engine_ids": expression_leaders,
                "engine_means": expression_means,
                "basis": "naturalness_mean for expression samples only",
            },
            "reading_reliability": {
                "machine_content_cer_candidate_engine_ids": cer_leaders,
                "human_pronunciation_quality_mean": None,
                "status": "machine_candidate_only",
                "required_gate": "expected_reading or phoneme validation before production use",
            },
            "same_speaker_style": {
                "candidate_engine_ids": same_speaker_candidates,
                "basis": "Phase 2 capability metadata; instruction_match was not evaluated by humans",
            },
            "automation": {
                "lowest_phase2_rtf_engine_ids": rtf_leaders,
                "basis": "Phase 2 generation RTF only; not a human score",
            },
            "pipeline": "原文 → 読み前処理 → TTS → 自動検証",
        },
        "comparison": comparison,
        "machine_human_comparison": {
            "single_score": False,
            "human_dimension": "naturalness",
            "machine_dimensions": [
                "content_cer_mean",
                "generation_rtf_mean",
                "raw_pronunciation_counts",
            ],
            "formal_reversal_concluded": False,
            "reason": "human naturalness and Phase 2 machine metrics are different dimensions and were not merged",
        },
    }


def write_public_outputs(
    output_dir: str | Path,
    human_summary: dict[str, Any],
    recommendation: dict[str, Any],
) -> None:
    """Write anonymized review outputs without sample IDs or audio paths."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "review_summary.json").write_text(
        json.dumps(human_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / "final_recommendation.json").write_text(
        json.dumps(recommendation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fieldnames = (
        "engine_id",
        "case_id",
        "category",
        "naturalness_mean",
        "naturalness_n",
        "instruction_match_mean",
        "pronunciation_quality_mean",
        "would_use_mean",
        "reading_issue_count",
        "note",
    )
    with (directory / "review_scores_anonymized.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {field: row.get(field) for field in fieldnames}
            for row in human_summary.get("engine_case_aggregates", [])
        )
