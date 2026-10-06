import re


def extract_cv_data(text: str) -> dict:
    data = {
        "name": None,
        "email": None,
        "phone": None,
        "skills": [],
        "education": []
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if lines:
        data["name"] = lines[0]

    email_match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )

    if email_match:
        data["email"] = email_match.group()

    phone_match = re.search(
        r"(\+?\d[\d\s\-()]{7,}\d)",
        text
    )

    if phone_match:
        data["phone"] = phone_match.group().strip()

    common_skills = [
        "python",
        "sql",
        "excel",
        "power bi",
        "tableau",
        "machine learning",
        "deep learning",
        "pandas",
        "numpy",
        "fastapi",
        "docker",
        "git"
    ]

    lower_text = text.lower()

    for skill in common_skills:
        if skill in lower_text:
            data["skills"].append(skill)

    education_keywords = [
        "bachelor",
        "master",
        "university",
        "college",
        "computer science",
        "information systems"
    ]

    for line in lines:
        lower_line = line.lower()

        if any(keyword in lower_line for keyword in education_keywords):
            data["education"].append(line)

    return data