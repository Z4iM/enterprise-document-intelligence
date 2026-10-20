import re

CATEGORY_ALIASES = {
    "meal": {
        "meal",
        "meals",
        "meal expense",
        "meal expenses",
        "food expense",
        "restaurant expense",
    },
    "hotel": {
        "hotel",
        "hotels",
        "hotel expense",
        "hotel accommodation",
        "accommodation",
        "lodging",
    },
    "ground_transportation": {
        "ground transportation",
        "transport",
        "transportation",
        "taxi",
        "rideshare",
        "ground transport",
    },
    "purchase": {
    "purchase",
    "purchases",
    "purchasing",
    "procurement",
    "purchase expense",
    "office purchase",
    "office purchases",
    },

    "all_expenses": {
        "all_expenses",
        "all expenses",
        "individual expenses",
        "general expenses",
},
}


def normalize_category(value: str | None) -> str:

    if not value:
        return ""

    cleaned = re.sub(
        r"[\s_-]+",
        " ",
        value.strip().lower()
    )

    for canonical, aliases in CATEGORY_ALIASES.items():
        if cleaned in aliases:
            return canonical

    # Unknown categories remain unchanged.
    # They are not automatically treated as
    # belonging to an existing category.
    return cleaned