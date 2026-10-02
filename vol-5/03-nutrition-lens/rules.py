"""Nutrition Lens rules layer: turn a matched meal into things to DO.

Imported by lens.py. Every function here is pure: meal items in, strings out.
No network, no files.

The science is kept directional on purpose. Vitamin C helps non-heme iron,
calcium and tea tannins hinder it, and the size of each effect depends on the
dose, the meal and the person. This module says "substantially" and never
invents a percentage.
"""

from __future__ import annotations

# Each action is (bucket, text). Buckets are printed in this order.
BUCKETS = ("ADD", "MOVE", "KNOW")


def amount(item: dict, key: str) -> float:
    """Scale a per-100g value in foods.json to this item's portion."""
    return item["food"].get(key, 0.0) * item["grams"] / 100.0


def totals(items: list[dict]) -> dict:
    """Meal-level sums the rules branch on."""
    heme = sum(amount(i, "iron_mg") for i in items if i["food"]["iron_type"] == "heme")
    nonheme = sum(amount(i, "iron_mg") for i in items if i["food"]["iron_type"] == "non-heme")
    return {
        "iron_heme_mg": heme,
        "iron_nonheme_mg": nonheme,
        "iron_mg": heme + nonheme,
        "calcium_mg": sum(amount(i, "calcium_mg") for i in items),
        "vitamin_c_mg": sum(amount(i, "vitamin_c_mg") for i in items),
        "caffeine_mg": sum(amount(i, "caffeine_mg") for i in items),
    }


def names(items: list[dict]) -> str:
    """'lentils, spinach and black tea'"""
    labels = [i["food"]["name"] for i in items]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def iron_leaders(items: list[dict], iron_type: str, limit: int = 2) -> list[dict]:
    ranked = [i for i in items if i["food"]["iron_type"] == iron_type]
    ranked.sort(key=lambda i: amount(i, "iron_mg"), reverse=True)
    return [i for i in ranked if amount(i, "iron_mg") >= 0.4][:limit]


def vitamin_c_sources(items: list[dict], floor: float = 8.0) -> list[dict]:
    found = [i for i in items if amount(i, "vitamin_c_mg") >= floor]
    found.sort(key=lambda i: amount(i, "vitamin_c_mg"), reverse=True)
    return found


def pantry_suggestions(db: dict, pantry: list[str], matched: list[dict], limit: int = 2) -> list[str]:
    """Vitamin C foods the profile says you already have, best first."""
    on_plate = {i["food"]["name"] for i in matched}
    wanted = [p.strip().lower() for p in pantry]
    picks = []
    for food in db["foods"]:
        if food["name"] in on_plate:
            continue
        keys = [food["name"]] + food.get("aliases", [])
        if any(k in wanted for k in keys) and food["vitamin_c_mg"] >= 25:
            picks.append(food)
    picks.sort(key=lambda f: f["vitamin_c_mg"], reverse=True)
    return [f["name"] for f in picks[:limit]]


def generic_suggestions(db: dict, matched: list[dict], limit: int = 3) -> list[str]:
    on_plate = {i["food"]["name"] for i in matched}
    picks = [f for f in db["foods"] if f["name"] not in on_plate and f["vitamin_c_mg"] >= 50]
    picks.sort(key=lambda f: f["vitamin_c_mg"], reverse=True)
    return [f["name"] for f in picks[:limit]]


def apply_rules(items: list[dict], db: dict, profile: dict) -> list[tuple[str, str]]:
    """The whole rules layer. Returns [(bucket, imperative), ...]."""
    t = totals(items)
    cut = db["thresholds"]
    low_iron = any("iron" in c.lower() for c in profile.get("concerns", []))
    actions: list[tuple[str, str]] = []

    nonheme_matters = t["iron_nonheme_mg"] >= cut["iron_notable_mg"]
    leaders = iron_leaders(items, "non-heme")
    lead_names = names(leaders) if leaders else "the plant foods here"

    # 1. Tannins and caffeine in the same sitting as plant iron.
    drinks = [i for i in items
              if i["food"].get("tannin_level") == "high"
              or amount(i, "caffeine_mg") >= cut["caffeine_notable_mg"]]
    if drinks and nonheme_matters:
        actions.append((
            "MOVE",
            f"Drink the {names(drinks)} 1 to 2 hours after this meal, not with it. "
            f"The {lead_names} here account for {t['iron_nonheme_mg']:.1f} mg of non-heme iron, "
            f"and tannins plus caffeine in the same sitting cut how much of that you absorb, "
            f"substantially. An hour of spacing is the whole fix."
        ))
    elif drinks:
        actions.append((
            "KNOW",
            f"No need to move the {names(drinks)}. There is little plant iron in this meal "
            f"({t['iron_nonheme_mg']:.1f} mg) for tannins and caffeine to block."
        ))

    # 2. Calcium load against plant iron.
    heavy_calcium = [i for i in items if amount(i, "calcium_mg") >= cut["calcium_inhibits_mg"]]
    if heavy_calcium and nonheme_matters:
        actions.append((
            "MOVE",
            f"Shift the {names(heavy_calcium)} to a different meal or an afternoon snack. "
            f"This plate carries about {t['calcium_mg']:.0f} mg of calcium, and calcium at that "
            f"level competes with non-heme iron for the same absorption path. You want both, "
            f"just not in the same hour."
        ))
    elif heavy_calcium:
        actions.append((
            "KNOW",
            f"That is roughly {t['calcium_mg']:.0f} mg of calcium, mostly from the "
            f"{names(heavy_calcium)}. Nothing to work around: there is no meaningful plant "
            f"iron here for it to block."
        ))

    # 3. Vitamin C, the one lever that pushes the other way.
    sources = vitamin_c_sources(items)
    if nonheme_matters and t["vitamin_c_mg"] >= cut["vitamin_c_strong_mg"]:
        actions.append((
            "KNOW",
            f"Keep the {names(sources)} on this plate. That is roughly "
            f"{t['vitamin_c_mg']:.0f} mg of vitamin C eaten with the iron, which is the single "
            f"strongest thing you can do for plant iron absorption."
        ))
    elif nonheme_matters:
        have = pantry_suggestions(db, profile.get("pantry", []), items)
        suggest = have or generic_suggestions(db, items)
        where = "you already have" if have else "to pick up"
        if sources:
            actions.append((
                "ADD",
                f"Add {' or '.join(suggest)} that {where}. The vitamin C already on the plate, "
                f"from the {names(sources)}, comes to about {t['vitamin_c_mg']:.0f} mg: a start, "
                f"not enough. Vitamin C eaten with the meal is what makes plant iron absorbable."
            ))
        else:
            actions.append((
                "ADD",
                f"Add {' or '.join(suggest)} that {where}. There is almost no vitamin C on this "
                f"plate ({t['vitamin_c_mg']:.0f} mg) and {t['iron_nonheme_mg']:.1f} mg of plant "
                f"iron waiting for it. Raw and in the same sitting is what counts."
            ))

    # 4. Heme iron already in the meal helps the plant iron beside it.
    heme = iron_leaders(items, "heme")
    if heme and nonheme_matters:
        actions.append((
            "KNOW",
            f"Keep the {names(heme)} next to the plant foods. Animal iron is absorbed well on its "
            f"own and also lifts absorption of the non-heme iron eaten with it."
        ))
    elif heme:
        actions.append((
            "KNOW",
            f"The iron in this meal is the {names(heme)}, about {t['iron_heme_mg']:.1f} mg, and "
            f"that is the form your body takes up most readily."
        ))

    # 5. Oxalates: the spinach trap.
    oxalic = [i for i in items if i["food"].get("oxalate_level") == "high"]
    if oxalic:
        actions.append((
            "KNOW",
            f"Do not bank on the iron number for {names(oxalic)}. Oxalates bind much of it in the "
            f"gut, so it reads far better on a label than it behaves in you. Treat it as a bonus, "
            f"not the source."
        ))

    # 6. Phytates in the staple.
    phytic = [i for i in items if i["food"].get("phytate_level") == "high"]
    if phytic and nonheme_matters and t["vitamin_c_mg"] < cut["vitamin_c_meaningful_mg"]:
        actions.append((
            "KNOW",
            f"Soaking, sprouting or fermenting the {names(phytic)} lowers the phytates, which are "
            f"part of why plant iron is hard to reach. Vitamin C in the same meal does more, faster."
        ))

    # 7. Egg yolk and other per-food inhibitor notes.
    for i in items:
        note = i["food"].get("inhibitor_note")
        if note and nonheme_matters:
            actions.append((
                "KNOW",
                f"Worth knowing about the {i['food']['name']}: {note}. Not a reason to skip it, "
                f"a reason to put the vitamin C beside it."
            ))

    # 8. Supplement timing, straight from the profile.
    supplements = [s for s in profile.get("habits", {}).get("supplements", []) if "iron" in s.lower()]
    if supplements and (drinks or heavy_calcium):
        blockers = names(drinks + heavy_calcium)
        actions.append((
            "MOVE",
            f"Do not take your iron supplement with this meal. What blocks food iron here, the "
            f"{blockers}, blocks the supplement too. An empty stomach with a glass of orange "
            f"juice is the better slot."
        ))

    # 9. Nothing to optimise.
    if not nonheme_matters and not heme:
        actions.append((
            "KNOW",
            f"This is not an iron meal: {t['iron_mg']:.1f} mg total, and nothing here blocks or "
            f"boosts much. If iron is the goal, the lever is the next plate, not this one."
        ))

    if low_iron and nonheme_matters:
        actions.append((
            "KNOW",
            "Your profile says low iron, so these pairings are not a rounding error for you. "
            "Same food, different order, measurably different outcome over weeks."
        ))

    return actions
