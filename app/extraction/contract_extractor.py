import re


def extract_contract_data(text: str) -> dict:
    data = {
        "parties": [],
        "start_date": None,
        "end_date": None,
        "signature_status": "unknown"
    }

    date_matches = re.findall(
        r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
        text
    )

    if len(date_matches) >= 1:
        data["start_date"] = date_matches[0]

    if len(date_matches) >= 2:
        data["end_date"] = date_matches[1]

    party_matches = re.findall(
        r"(?:between|party)\s*[:\-]?\s*([A-Za-z0-9 &.,'-]+)",
        text,
        re.IGNORECASE
    )

    for party in party_matches:
        cleaned_party = party.strip()

        if cleaned_party:
            data["parties"].append(cleaned_party)

    lower_text = text.lower()

    if "signature" in lower_text or "signed by" in lower_text:
        data["signature_status"] = "signature_reference_found"

    return data