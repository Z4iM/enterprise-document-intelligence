import json
import re

from app.llm.schemas import SCHEMA_MAP


def clean_json_response(response: str) -> str:
    response = response.strip()

    response = re.sub(
        r"^```json\s*",
        "",
        response,
        flags=re.IGNORECASE
    )

    response = re.sub(r"^```\s*", "", response)
    response = re.sub(r"\s*```$", "", response)

    return response.strip()


def normalize_llm_data(data: dict, document_type: str) -> dict:

    if document_type == "cv":

        email = data.get("email")

        if isinstance(email, str):
            email_match = re.search(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                email
            )

            if email_match:
                data["email"] = email_match.group()

        education = data.get("education", [])
        normalized_education = []

        for item in education:

            if isinstance(item, dict):
                degree = item.get("degree")

                if degree:
                    normalized_education.append(degree)

            elif isinstance(item, str):
                normalized_education.append(item)

        data["education"] = normalized_education


    elif document_type == "receipt":

        payment_method = data.get("payment_method")

        if isinstance(payment_method, list):
            data["payment_method"] = (
                payment_method[0]
                if payment_method
                else None
            )


    elif document_type == "contract":

        parties = data.get("parties", [])
        normalized_parties = []

        for party in parties:

            if isinstance(party, dict):
                name = party.get("name")

                if name:
                    normalized_parties.append(name)

            elif isinstance(party, str):
                normalized_parties.append(party)

        data["parties"] = normalized_parties


    return data


def validate_llm_response(
    response: str,
    document_type: str
) -> dict:

    cleaned_response = clean_json_response(response)

    parsed = json.loads(cleaned_response)

    normalized = normalize_llm_data(
        parsed,
        document_type
    )

    schema = SCHEMA_MAP[document_type]

    validated = schema(**normalized)

    return validated.model_dump()