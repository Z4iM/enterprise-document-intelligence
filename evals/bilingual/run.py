"""Fixed synthetic bilingual field/policy metrics; optional isolated local Tesseract OCR."""

import argparse
import hashlib
import io
import json
import platform
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.classification.classifier import classify_document
from app.extraction.invoice_extractor import extract_invoice_data
from app.extraction.receipt_extractor import extract_receipt_data
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import verify_rule


def distance(reference, observed):
    previous = list(range(len(observed) + 1))
    for row, left in enumerate(reference, 1):
        current = [row]
        for column, right in enumerate(observed, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]


def inspect_record(record, text, method, latency_ms=0):
    observation = {
        "id": record["id"],
        "language": record["language"],
        "kind": record["kind"],
        "method": method,
        "latency_ms": latency_ms,
    }
    if record["kind"] == "policy":
        rule = PolicyRule(**record["rule"], source_quote=text)
        checked = verify_rule(rule, text)
        observation.update(
            verified=checked["verified"],
            expected_verified=record["expected_verified"],
            decision_correct=checked["verified"] == record["expected_verified"],
            reason=checked["reason"],
        )
    else:
        values = (
            extract_receipt_data
            if record["kind"] == "receipt"
            else extract_invoice_data
        )(text)
        gold = record["expected_fields"]
        observation.update(
            classification=classify_document(text)[0],
            classification_correct=classify_document(text)[0] == record["kind"],
            fields_correct=sum(values.get(key) == value for key, value in gold.items()),
            fields_total=len(gold),
            predicted_nonempty=sum(values.get(key) is not None for key in gold),
            correct_nonempty=sum(
                values.get(key) == value and value is not None
                for key, value in gold.items()
            ),
            required_values=sum(value is not None for value in gold.values()),
            false_abstentions=sum(
                values.get(key) is None and value is not None
                for key, value in gold.items()
            ),
            expected_fields=gold,
            actual_fields=values,
        )
    if method == "scanned_ocr":
        reference, observed = " ".join(record["text"].split()), " ".join(text.split())
        observation.update(
            cer=distance(reference, observed) / max(1, len(reference)),
            wer=distance(reference.split(), observed.split())
            / max(1, len(reference.split())),
            ocr_text=text,
        )
    return observation


def summarize(rows):
    fields = [row for row in rows if row["kind"] != "policy"]
    policies = [row for row in rows if row["kind"] == "policy"]
    total = sum(row["fields_total"] for row in fields)
    predicted = sum(row["predicted_nonempty"] for row in fields)
    required = sum(row["required_values"] for row in fields)
    return {
        "observations": len(rows),
        "field_exact_accuracy": round(
            sum(row["fields_correct"] for row in fields) / total, 4
        )
        if total
        else None,
        "nonempty_field_precision": round(
            sum(row["correct_nonempty"] for row in fields) / predicted, 4
        )
        if predicted
        else None,
        "false_abstention_rate": round(
            sum(row["false_abstentions"] for row in fields) / required, 4
        )
        if required
        else None,
        "classification_accuracy": round(
            sum(row["classification_correct"] for row in fields) / len(fields), 4
        )
        if fields
        else None,
        "policy_decision_accuracy": round(
            sum(row["decision_correct"] for row in policies) / len(policies), 4
        )
        if policies
        else None,
        "mean_cer": round(
            statistics.mean(row["cer"] for row in rows if "cer" in row), 4
        )
        if any("cer" in row for row in rows)
        else None,
        "mean_wer": round(
            statistics.mean(row["wer"] for row in rows if "wer" in row), 4
        )
        if any("wer" in row for row in rows)
        else None,
    }


def render(record, font_path):
    from PIL import Image, ImageDraw, ImageFont, features

    if record["language"] == "ar" and not features.check("raqm"):
        raise RuntimeError(
            "Arabic shaping support is required for honest scan fixtures."
        )
    font = ImageFont.truetype(font_path, 48)
    width = max(
        1800,
        int(max(font.getlength(line) for line in record["text"].splitlines())) + 140,
    )
    height = 120 + len(record["text"].splitlines()) * 85
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(record["text"].splitlines()):
        if record["language"] == "ar":
            draw.text(
                (width - 70, 60 + index * 85),
                line,
                font=font,
                fill="black",
                anchor="ra",
                direction="rtl",
                language="ar",
            )
        else:
            draw.text((70, 60 + index * 85), line, font=font, fill="black")
    output = io.BytesIO()
    image.save(output, format="PNG", dpi=(200, 200))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--check-native",
        action="store_true",
        help="Fail on supported deterministic native golden regressions; OCR quality is reported separately.",
    )
    parser.add_argument(
        "--docker",
        help="Explicit Docker executable for optional offline OCR; no application data is mounted",
    )
    parser.add_argument("--image", default="edi-verification-backend:a41030202602")
    parser.add_argument(
        "--font", help="Public system font supporting Arabic, e.g. Arial or DejaVuSans"
    )
    args = parser.parse_args()
    source = Path(__file__).with_name("corpus.json").read_bytes()
    corpus = json.loads(source)
    observations = [
        inspect_record(record, record["text"], "native_text")
        for record in corpus["documents"]
    ]
    container = "edi-bilingual-eval-" + uuid.uuid4().hex[:10]
    scans = [record for record in corpus["documents"] if record["input"] == "scan"]
    ocr_version = None
    if args.docker:
        if not args.font:
            raise SystemExit(
                "Supply a public Arabic-capable --font for scan rendering."
            )
        subprocess.run(
            [
                args.docker,
                "run",
                "-d",
                "--name",
                container,
                "--network",
                "none",
                "--read-only",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--tmpfs",
                "/tmp:size=67108864,mode=1777",
                args.image,
                "sleep",
                "3600",
            ],
            check=True,
            capture_output=True,
        )
        try:
            ocr_version = subprocess.check_output(
                [args.docker, "exec", container, "tesseract", "--version"], text=True
            ).splitlines()[0]
            for record in scans:
                data = render(record, args.font)
                started = time.perf_counter()
                completed = subprocess.run(
                    [
                        args.docker,
                        "exec",
                        "-i",
                        container,
                        "python",
                        "-c",
                        "import sys; from app.ingestion.ocr import extract_image_text; sys.stdout.write(extract_image_text(sys.stdin.buffer.read()))",
                    ],
                    input=data,
                    capture_output=True,
                    timeout=35,
                    check=True,
                )
                observations.append(
                    inspect_record(
                        record,
                        completed.stdout.decode("utf-8").strip(),
                        "scanned_ocr",
                        round((time.perf_counter() - started) * 1000, 2),
                    )
                )
        finally:
            subprocess.run(
                [args.docker, "stop", container], check=True, capture_output=True
            )
    report = {
        "corpus_version": corpus["version"],
        "corpus_sha256": hashlib.sha256(source).hexdigest(),
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "unique_documents": len(corpus["documents"]),
        "scope": corpus["scope"],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "ocr_version": ocr_version,
        "ocr_configuration": {
            "image": args.image if args.docker else None,
            "languages": "eng+ara",
            "segmentation": "Tesseract default",
            "upscale": 2,
            "timeout_seconds": 5,
            "font": Path(args.font).name if args.font else None,
        },
        "scan_cases_not_run": [] if args.docker else [record["id"] for record in scans],
        "method_notes": "Native text is a reference baseline for all 40 templates. Eight scans additionally use the actual app extract_image_text preprocessing/default segmentation/eng+ara/5-second OCR timeout in the named container. OCR transport included in latency; CER/WER collapse whitespace only. No LLM, keys or real data.",
        "metrics": {},
    }
    for method in ("native_text", "scanned_ocr"):
        rows = [row for row in observations if row["method"] == method]
        report["metrics"][method] = {
            "overall": summarize(rows),
            "by_language": {
                language: summarize(
                    [row for row in rows if row["language"] == language]
                )
                for language in ("en", "ar")
            },
        }
    report["per_document"] = observations
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    if args.check_native and any(
        row.get("fields_correct", 0) != row.get("fields_total", 0)
        or not row.get("classification_correct", True)
        or not row.get("decision_correct", True)
        for row in observations
        if row["method"] == "native_text"
    ):
        raise SystemExit("Native bilingual golden regression.")


if __name__ == "__main__":
    main()
