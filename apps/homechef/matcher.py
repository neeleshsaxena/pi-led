"""Curates which dishes can be made from the ingredients currently marked
available. Pure function over plain data — no controller/state concerns here.

Staple ingredients (salt, oil, everyday spices) are assumed to always be on
hand and never count as "missing", even if not explicitly marked available.
"""
from __future__ import annotations


def suggest_dishes(ingredients: list[dict], dishes: list[dict], available: list[str], max_missing: int = 2) -> list[dict]:
    staples = {ing["name"] for ing in ingredients if ing.get("is_staple")}
    have = set(available) | staples

    results = []
    for dish in dishes:
        required = list(dish.get("ingredients") or [])
        countable = [n for n in required if n not in staples]
        missing = [n for n in countable if n not in have]

        if countable and len(missing) > max_missing:
            continue

        results.append(
            {
                "name": dish["name"],
                "ingredients": required,
                "missing": missing,
                "missing_count": len(missing),
                "total_count": len(countable),
                "is_full_match": len(missing) == 0,
            }
        )

    results.sort(key=lambda d: (d["missing_count"], -d["total_count"], d["name"]))
    return results
