
import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth"
PREDICTIONS_DIR = BASE_DIR / "predictions"

CURRENCIES = "USD|EUR|GBP|EGP|SAR|AED"

MONEY_PATTERN = re.compile(
    rf"^\s*(?P<prefix>{CURRENCIES})?\s*"
    r"(?P<symbol>\$)?\s*"
    r"(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)\s*"
    rf"(?P<suffix>{CURRENCIES})?\s*$",
    re.IGNORECASE,
)


def normalize_money(value):
    """Convert a supported monetary string to (currency, Decimal)."""
    if not isinstance(value, str):
        return None

    match = MONEY_PATTERN.fullmatch(value.strip())

    if match is None:
        return None

    prefix = match.group("prefix")
    suffix = match.group("suffix")
    symbol = match.group("symbol")

    prefix = prefix.upper() if prefix else None
    suffix = suffix.upper() if suffix else None

    if prefix and suffix and prefix != suffix:
        return None

    currency = prefix or suffix

    # USD-only benchmark convention: $ represents USD.
    if symbol:
        if currency and currency != "USD":
            return None
        currency = "USD"

    if currency is None:
        return None

    try:
        amount = Decimal(
            match.group("amount").replace(",", "")
        )
    except InvalidOperation:
        return None

    return currency, amount


def fields_match(field, expected, predicted):
    """Return exact-match and normalized-match results."""
    exact = expected == predicted

    if exact:
        return True, True

    if field == "total":
        expected_money = normalize_money(expected)
        predicted_money = normalize_money(predicted)

        normalized = (
            expected_money is not None
            and predicted_money is not None
            and expected_money == predicted_money
        )

        return False, normalized

    return False, False


def evaluate_case(ground_truth, prediction):
    expected_fields = ground_truth["expected_fields"]
    predicted_fields = prediction["predicted_fields"]

    results = {}

    for field, expected in expected_fields.items():
        predicted = predicted_fields.get(field)

        exact, normalized = fields_match(
            field,
            expected,
            predicted,
        )

        results[field] = {
            "expected": expected,
            "predicted": predicted,
            "exact_match": exact,
            "normalized_match": normalized,
            "missing": expected is not None and predicted is None,
            "unexpected_value": expected is None and predicted is not None,
        }

    classification_correct = (
        ground_truth["expected_document_type"]
        == prediction["predicted_document_type"]
    )

    return {
        "case_id": ground_truth["case_id"],
        "classification_correct": classification_correct,
        "classification_score": prediction.get("classification_score"),
        "fields": results,
        "unexpected_fields": sorted(
            set(predicted_fields) - set(expected_fields)
        ),
    }


def run_evaluation(provider):
    cases = []

    for truth_path in sorted(GROUND_TRUTH_DIR.glob("*.json")):
        ground_truth = json.loads(
            truth_path.read_text(encoding="utf-8")
        )

        case_id = ground_truth["case_id"]

        prediction_path = (
            PREDICTIONS_DIR / f"{case_id}_{provider}.json"
        )

        if not prediction_path.exists():
            print(f"SKIPPED: {case_id} (prediction not found)")
            continue

        prediction = json.loads(
            prediction_path.read_text(encoding="utf-8")
        )

        if prediction.get("case_id") != case_id:
            raise ValueError(
                f"Prediction case ID mismatch: {prediction_path}"
            )

        result = evaluate_case(ground_truth, prediction)
        cases.append(result)

        print(f"\n=== {case_id} ===")
        print(
            "Classification:",
            "PASS" if result["classification_correct"] else "FAIL",
        )

        for field, comparison in result["fields"].items():
            status = (
                "EXACT"
                if comparison["exact_match"]
                else "NORMALIZED"
                if comparison["normalized_match"]
                else "FAIL"
            )

            print(f"{field}: {status}")

    if not cases:
        raise SystemExit(
            f"No matching predictions found for provider: {provider}"
        )

    all_fields = [
        comparison
        for case in cases
        for comparison in case["fields"].values()
    ]

    total = len(all_fields)
    exact_matches = sum(
        field["exact_match"] for field in all_fields
    )
    normalized_matches = sum(
        field["normalized_match"] for field in all_fields
    )
    missing = sum(
        field["missing"] for field in all_fields
    )
    unexpected_values = sum(
        field["unexpected_value"] for field in all_fields
    )
    extra_fields = sum(
        len(case["unexpected_fields"]) for case in cases
    )

    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Provider: {provider}")
    print(f"Cases evaluated: {len(cases)}")
    print(
        "Classification accuracy:",
        f"{sum(c['classification_correct'] for c in cases) / len(cases):.2%}",
    )
    print(f"Exact field accuracy: {exact_matches / total:.2%}")
    print(
        "Normalized field accuracy:",
        f"{normalized_matches / total:.2%}",
    )
    print(f"Missing expected values: {missing}")
    print(f"Unexpected values for null fields: {unexpected_values}")
    print(f"Unrecognized prediction fields: {extra_fields}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider",
        default="gemini",
        help="Prediction provider name",
    )
    args = parser.parse_args()
    run_evaluation(args.provider)
