import re

from app.language.amounts import semantic_text

CATEGORY_ALIASES = {
    "meal": {
        "وجبة", "وجبات", "الوجبات", "الطعام", "مصروفات الوجبات",
        "meal",
        "meals",
        "meal expense",
        "meal expenses",
        "food expense",
        "restaurant expense",
    },
    "hotel": {
        "فندق", "الفندق", "فنادق", "الفنادق", "إقامة", "الإقامة",
        "hotel",
        "hotels",
        "hotel expense",
        "hotel accommodation",
        "accommodation",
        "lodging",
    },
    "ground_transportation": {
        "النقل البري", "تاكسي", "سيارة أجرة", "سيارات الأجرة",
        "ground transportation",
        "transport",
        "transportation",
        "taxi",
        "rideshare",
        "ground transport",
    },
    "purchase": {
    "مشتريات", "المشتريات", "الشراء", "مستلزمات المكتب",
    "purchase",
    "purchases",
    "purchasing",
    "procurement",
    "purchase expense",
    "office purchase",
    "office purchases",
    },

    "all_expenses": {
        "جميع المصروفات", "كل المصروفات", "جميع النفقات",
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
        semantic_text(value)
    )

    for canonical, aliases in CATEGORY_ALIASES.items():
        if cleaned in aliases:
            return canonical

    # Unknown categories remain unchanged.
    # They are not automatically treated as
    # belonging to an existing category.
    return cleaned
