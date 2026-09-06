from pathlib import Path
from zipfile import ZipFile

import pytest

from tts_benchmark.phase21 import (
    aggregate_naturalness,
    build_final_recommendation,
    load_review_workbook,
    validate_naturalness_only,
    validate_phase21_identifiers,
    validate_phase21_provenance,
    validate_phase21_recommendation,
    validate_phase21_summary,
    write_public_outputs,
)


def test_aggregate_naturalness_keeps_unassessed_dimensions_null():
    rows = [
        {
            "sample_id": "S01",
            "category": "expression",
            "case_id": "x01",
            "naturalness": 3.0,
            "instruction_match": None,
            "pronunciation_quality": None,
            "would_use": None,
            "reading_issue": None,
            "note": None,
            "completed": "完了",
        },
        {
            "sample_id": "S02",
            "category": "expression",
            "case_id": "x01",
            "naturalness": 5.0,
            "instruction_match": None,
            "pronunciation_quality": None,
            "would_use": None,
            "reading_issue": None,
            "note": None,
            "completed": "完了",
        },
    ]
    blind_items = [
        {
            "sample_id": "S01",
            "engine_id": "engine_a",
            "case_id": "x01",
            "category": "expression",
        },
        {
            "sample_id": "S02",
            "engine_id": "engine_a",
            "case_id": "x01",
            "category": "expression",
        },
    ]

    summary = aggregate_naturalness(rows, blind_items)

    assert summary["sample_count"] == 2
    assert summary["reviewed_dimensions"] == ["naturalness"]
    assert summary["engine_case_aggregates"] == [
        {
            "engine_id": "engine_a",
            "case_id": "x01",
            "category": "expression",
            "naturalness_mean": 4.0,
            "naturalness_n": 2,
            "instruction_match_mean": None,
            "pronunciation_quality_mean": None,
            "would_use_mean": None,
            "reading_issue_count": None,
            "note": None,
        }
    ]
    assert summary["engine_aggregates"][0]["naturalness_mean"] == 4.0
    assert summary["engine_aggregates"][0]["pronunciation_quality_mean"] is None


def test_validate_naturalness_only_rejects_other_review_scores():
    rows = [
        {
            "sample_id": "S01",
            "category": "pronunciation",
            "case_id": "p01",
            "naturalness": 3.0,
            "instruction_match": None,
            "pronunciation_quality": 4.0,
            "would_use": None,
            "reading_issue": None,
            "note": None,
            "completed": "完了",
        }
    ]
    blind_items = [
        {
            "sample_id": "S01",
            "engine_id": "engine_a",
            "case_id": "p01",
            "category": "pronunciation",
        }
    ]

    with pytest.raises(ValueError, match="pronunciation_quality"):
        validate_naturalness_only(rows, blind_items)


def test_load_review_workbook_reads_numeric_naturalness_and_blank_fields(tmp_path):
    path = tmp_path / "scores.xlsx"
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Target="worksheets/sheet1.xml"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
</Relationships>"""
    headers = [
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
    ]
    cells = []
    for index, value in enumerate(headers, start=1):
        col = chr(64 + index)
        cells.append(f'<c r="{col}1" t="inlineStr"><is><t>{value}</t></is></c>')
    cells.extend(
        [
            '<c r="A2" t="inlineStr"><is><t>S01</t></is></c>',
            '<c r="B2" t="inlineStr"><is><t>expression</t></is></c>',
            '<c r="C2" t="inlineStr"><is><t>x01</t></is></c>',
            '<c r="F2"><v>4</v></c>',
            '<c r="L2" t="inlineStr"><is><t>完了</t></is></c>',
        ]
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData><row r="1">{"".join(cells[:12])}</row>'
        f'<row r="2">{"".join(cells[12:])}</row></sheetData></worksheet>'
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)

    rows = load_review_workbook(path)

    assert rows == [
        {
            "sample_id": "S01",
            "category": "expression",
            "case_id": "x01",
            "text": None,
            "instruction": None,
            "naturalness": 4.0,
            "instruction_match": None,
            "pronunciation_quality": None,
            "would_use": None,
            "reading_issue": None,
            "note": None,
            "completed": "完了",
        }
    ]


def test_final_recommendation_separates_human_naturalness_from_machine_metrics():
    phase2_summary = {
        "engines": [
            {
                "engine_id": "engine_a",
                "phase2_measurement_status": "実測完了",
                "content_cer_mean": 0.12,
                "generation_rtf_mean": 0.2,
                "same_speaker_multi_style": False,
            },
            {
                "engine_id": "engine_b",
                "phase2_measurement_status": "実測完了",
                "content_cer_mean": 0.2,
                "generation_rtf_mean": 0.1,
                "same_speaker_multi_style": True,
            },
        ],
        "reading_variants": [],
    }
    human_summary = {
        "engine_aggregates": [
            {
                "engine_id": "engine_a",
                "naturalness_mean": 4.0,
                "naturalness_n": 2,
                "instruction_match_mean": None,
                "pronunciation_quality_mean": None,
                "would_use_mean": None,
                "reading_issue_count": None,
                "note": None,
            },
            {
                "engine_id": "engine_b",
                "naturalness_mean": 3.0,
                "naturalness_n": 1,
                "instruction_match_mean": None,
                "pronunciation_quality_mean": None,
                "would_use_mean": None,
                "reading_issue_count": None,
                "note": None,
            },
        ],
        "engine_case_aggregates": [],
        "reviewed_dimensions": ["naturalness"],
        "not_evaluated_dimensions": [
            "instruction_match",
            "pronunciation_quality",
            "would_use",
            "reading_issue",
            "note",
        ],
    }

    recommendation = build_final_recommendation(phase2_summary, human_summary)

    assert recommendation["recommendations"]["human_naturalness"][
        "leader_engine_ids"
    ] == ["engine_a"]
    assert (
        recommendation["comparison"][0]["machine_metrics"]["content_cer_mean"] == 0.12
    )
    assert (
        recommendation["comparison"][0]["human_naturalness"]["naturalness_mean"] == 4.0
    )
    assert recommendation["comparison"][0]["human_other_dimensions"] == {
        "instruction_match_mean": None,
        "pronunciation_quality_mean": None,
        "would_use_mean": None,
        "reading_issue_count": None,
        "note": None,
    }
    assert recommendation["machine_human_comparison"]["single_score"] is False
    assert (
        recommendation["recommendations"]["best_single_engine"]["default_candidate"]
        == "engine_a"
    )


def test_final_recommendation_keeps_target_out_machine_fields_unmeasured():
    recommendation = build_final_recommendation(
        {
            "engines": [
                {
                    "engine_id": "target_out",
                    "phase2_measurement_status": "対象外",
                    "content_cer_mean": None,
                    "generation_rtf_mean": None,
                    "same_speaker_multi_style": True,
                }
            ],
            "reading_variants": [
                {
                    "engine_id": "target_out",
                    "variant": "raw",
                    "case_id": "p01",
                    "pronunciation_result": "対象外",
                }
            ],
        },
        {"engine_aggregates": [], "engine_case_aggregates": []},
    )

    machine = recommendation["comparison"][0]["machine_metrics"]
    assert machine["content_cer_mean"] is None
    assert machine["generation_rtf_mean"] is None
    assert machine["same_speaker_multi_style"] is None


def test_validate_phase21_recommendation_rejects_private_path_values():
    recommendation = build_final_recommendation(
        {
            "engines": [],
            "reading_variants": [],
        },
        {"engine_aggregates": [], "engine_case_aggregates": []},
    )
    recommendation["private_debug_path"] = "/home/private/model"

    with pytest.raises(ValueError, match="private path"):
        validate_phase21_recommendation(recommendation)

    del recommendation["private_debug_path"]
    recommendation["debug"] = "reviewer_package/audio_private/S01.wav"
    with pytest.raises(ValueError, match="private path"):
        validate_phase21_recommendation(recommendation)


def test_validate_phase21_identifiers_rejects_unallowlisted_map_values():
    with pytest.raises(ValueError, match="engine_id"):
        validate_phase21_identifiers(
            [
                {
                    "sample_id": "S01",
                    "engine_id": "private-model-name",
                    "case_id": "x01",
                    "category": "expression",
                }
            ]
        )


def test_validate_phase21_provenance_rejects_private_text_in_commit_or_tag():
    with pytest.raises(ValueError, match="commit"):
        validate_phase21_provenance("private-model-name", "v0.2.0")

    with pytest.raises(ValueError, match="tag"):
        validate_phase21_provenance("a" * 40, "private-model-name")


def test_phase21_results_readme_lists_complete_public_outputs():
    readme = (
        Path(__file__).resolve().parents[1] / "results" / "phase2_1" / "README.md"
    ).read_text(encoding="utf-8")
    assert "..." + "[truncated]" not in readme
    for filename in (
        "review_summary.json",
        "review_scores_anonymized.csv",
        "final_recommendation.json",
        "validation.json",
    ):
        assert f"`{filename}`" in readme


def test_write_public_outputs_does_not_emit_blind_sample_ids(tmp_path):
    human_summary = {
        "engine_aggregates": [],
        "engine_case_aggregates": [
            {
                "engine_id": "engine_a",
                "case_id": "x01",
                "category": "expression",
                "naturalness_mean": 4.0,
                "naturalness_n": 1,
                "instruction_match_mean": None,
                "pronunciation_quality_mean": None,
                "would_use_mean": None,
                "reading_issue_count": None,
                "note": None,
            }
        ],
        "reviewed_dimensions": ["naturalness"],
        "not_evaluated_dimensions": [
            "instruction_match",
            "pronunciation_quality",
            "would_use",
            "reading_issue",
            "note",
        ],
    }

    write_public_outputs(tmp_path, human_summary, {"status": "complete"})

    csv_text = (tmp_path / "review_scores_anonymized.csv").read_text()
    assert "sample_id" not in csv_text
    assert "engine_a,x01,expression,4.0,1,,,,," in csv_text
    assert (
        '"status": "complete"' in (tmp_path / "final_recommendation.json").read_text()
    )


def test_validate_phase21_summary_rejects_non_null_unassessed_dimension():
    summary = {
        "schema_version": "phase2.1-human-review-summary-1",
        "phase": "phase2.1",
        "status": "complete",
        "sample_count": 1,
        "reviewed_dimensions": ["naturalness"],
        "not_evaluated_dimensions": [
            "instruction_match",
            "pronunciation_quality",
            "would_use",
            "reading_issue",
            "note",
        ],
        "engine_aggregates": [
            {
                "engine_id": "engine_a",
                "naturalness_mean": 4.0,
                "naturalness_n": 1,
                "instruction_match_mean": None,
                "pronunciation_quality_mean": 4.0,
                "would_use_mean": None,
                "reading_issue_count": None,
                "note": None,
            }
        ],
        "engine_case_aggregates": [],
    }

    with pytest.raises(ValueError, match="pronunciation_quality_mean"):
        validate_phase21_summary(summary)
