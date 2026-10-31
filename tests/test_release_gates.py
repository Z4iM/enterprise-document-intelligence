"""Release checks distinguish known regressions from unfinished real-world quality."""

import copy

from evals.release.run import artifact_digest, assess


def test_published_artifact_hash_survives_git_line_ending_conversion(tmp_path):
    report = tmp_path / "report.json"
    report.write_bytes(b'{\r\n  "passed": true\r\n}\r\n')
    windows_digest = artifact_digest(report)
    report.write_bytes(b'{\n  "passed": true\n}\n')
    assert artifact_digest(report) == windows_digest
    report.write_bytes(b'{\n  "passed": false\n}\n')
    assert artifact_digest(report) != windows_digest


def reports():
    lexical = {
        "recall_at_5": 0.5,
        "citation_integrity": 1,
        "unanswerable_abstention_rate": 0.75,
    }
    native = {
        "observations": 20,
        "field_exact_accuracy": 1,
        "classification_accuracy": 1,
        "policy_decision_accuracy": 1,
    }
    return {
        "retrieval": {
            "methods": {
                "lexical": {
                    "by_language": {lang: dict(lexical) for lang in ("en", "ar")}
                }
            }
        },
        "bilingual": {
            "metrics": {
                "native_text": {
                    "by_language": {lang: dict(native) for lang in ("en", "ar")}
                }
            }
        },
        "specialists": {"cases": 12, "baseline_correct": 12, "specialists_correct": 12},
    }


def test_green_synthetic_regressions_do_not_certify_product_quality():
    result = assess(**reports())
    assert (
        result["regression_gate_passed"] and not result["product_quality_gate_passed"]
    )
    assert any(
        item["observed"]
        == "NOT RUN: separate explicit provider/data/quota approval required"
        for item in result["product_quality_checks"]
    )


def test_wrong_arabic_amount_canonical_decision_or_citation_blocks_regression_gate():
    base = reports()
    for area in ("field", "decision", "citation"):
        changed = copy.deepcopy(base)
        if area == "field":
            changed["bilingual"]["metrics"]["native_text"]["by_language"]["ar"][
                "field_exact_accuracy"
            ] = 0.95
        elif area == "decision":
            changed["specialists"]["specialists_correct"] = 11
        else:
            changed["retrieval"]["methods"]["lexical"]["by_language"]["ar"][
                "citation_integrity"
            ] = 0.99
        assert not assess(**changed)["regression_gate_passed"]
