"""Reproduce deterministic regressions; separately report unmet product-quality gates."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def assess(retrieval, bilingual, specialists, ocr=None):
    checks, quality = [], []

    def check(name, passed, observed, target, *, product=False):
        (quality if product else checks).append(
            {
                "name": name,
                "passed": bool(passed),
                "observed": observed,
                "target": target,
            }
        )

    for language in ("en", "ar"):
        native = bilingual["metrics"]["native_text"]["by_language"][language]
        check(
            f"{language}.native_fixture_count",
            native["observations"] >= 20,
            native["observations"],
            ">=20",
        )
        for metric in (
            "field_exact_accuracy",
            "classification_accuracy",
            "policy_decision_accuracy",
        ):
            check(f"{language}.native.{metric}", native[metric] == 1, native[metric], 1)
        lexical = retrieval["methods"]["lexical"]["by_language"][language]
        for metric, minimum in (
            ("recall_at_5", 0.5),
            ("citation_integrity", 1),
            ("unanswerable_abstention_rate", 0.75),
        ):
            check(
                f"{language}.keyword.{metric}",
                lexical[metric] >= minimum,
                lexical[metric],
                minimum,
            )
        scan = (
            (ocr or {})
            .get("metrics", {})
            .get("scanned_ocr", {})
            .get("by_language", {})
            .get(language, {})
        )
        count, accuracy = scan.get("observations", 0), scan.get("field_exact_accuracy")
        check(
            f"{language}.scan_sample_size",
            count >= 20,
            count,
            ">=20 held-out scans/language",
            product=True,
        )
        check(
            f"{language}.scan_field_accuracy",
            accuracy is not None and accuracy >= 0.9,
            accuracy,
            ">=0.90; sufficient held-out sample also required",
            product=True,
        )
        check(
            f"{language}.keyword_abstention",
            lexical["unanswerable_abstention_rate"] >= 0.9,
            lexical["unanswerable_abstention_rate"],
            ">=0.90",
            product=True,
        )
    for method in ("baseline", "specialists"):
        correct = specialists[f"{method}_correct"]
        check(
            f"{method}.canonical_outcomes",
            specialists["cases"] >= 12 and correct == specialists["cases"],
            f"{correct}/{specialists['cases']}",
            "12/12 or larger fixed golden corpus",
        )
    check(
        "live_model_quality_and_cost",
        False,
        "NOT RUN: separate explicit provider/data/quota approval required",
        "authorized held-out comparison with measured usage and latency",
        product=True,
    )
    check(
        "held_out_ocr_corpus",
        False,
        "Current OCR report uses development templates",
        "independently held-out realistic receipts/invoices/policies",
        product=True,
    )
    return {
        "regression_gate_passed": all(item["passed"] for item in checks),
        "product_quality_gate_passed": all(item["passed"] for item in quality),
        "regression_checks": checks,
        "product_quality_checks": quality,
        "limitations": "Regression success is not showcase/production certification. OCR/retrieval thresholds are initial engineering targets, not statistical guarantees. No inference is run by this command.",
    }


def artifact_digest(path):
    """Keep published report hashes stable across Git's LF/CRLF conversion."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", required=True)
    parser.add_argument(
        "--ocr-report",
        help="Optional existing measured report; never triggers OCR or model calls",
    )
    parser.add_argument("--require-product-quality", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = Path(args.output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for name, script in (
        ("retrieval", "evals/retrieval/run.py"),
        ("bilingual", "evals/bilingual/run.py"),
        ("specialists", "evals/specialists/run.py"),
    ):
        target = output / f"{name}.json"
        subprocess.run(
            [sys.executable, str(root / script), "--output", str(target)],
            cwd=root,
            check=True,
            timeout=180,
            stdout=subprocess.DEVNULL,
        )
        reports[name] = json.loads(target.read_text(encoding="utf-8"))
    ocr = (
        json.loads(Path(args.ocr_report).read_text(encoding="utf-8"))
        if args.ocr_report
        else None
    )
    if ocr:
        source = (
            (root / "evals/bilingual/corpus.json").read_bytes().replace(b"\r\n", b"\n")
        )
        valid_hashes = {
            hashlib.sha256(source).hexdigest(),
            hashlib.sha256(source.replace(b"\n", b"\r\n")).hexdigest(),
        }
        if ocr.get("corpus_sha256") not in valid_hashes:
            raise SystemExit("OCR report does not match the fixed bilingual corpus.")
    result = assess(**reports, ocr=ocr)
    result.update(
        generated_at=datetime.now(UTC).isoformat(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        provider_inference="not_run",
        ocr_source="existing_development_report" if ocr else "not_run",
        artifact_hash_normalization="CRLF to LF before SHA256",
        artifact_sha256={
            path.name: artifact_digest(path)
            for path in (output / f"{name}.json" for name in reports)
        },
    )
    (output / "release.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if (
        not result["regression_gate_passed"]
        or args.require_product_quality
        and not result["product_quality_gate_passed"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
