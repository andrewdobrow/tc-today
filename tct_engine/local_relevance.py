"""Deterministic Treasure Coast locality classification and scoring."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class LocalRelevance:
    scope: str
    score: int
    counties: tuple[str, ...] = ()
    places: tuple[str, ...] = ()

_PLACE_TO_COUNTY = {
    "stuart": "Martin County", "jensen beach": "Martin County", "palm city": "Martin County", "hobe sound": "Martin County",
    "port st. lucie": "St. Lucie County", "port saint lucie": "St. Lucie County", "fort pierce": "St. Lucie County",
    "vero beach": "Indian River County", "sebastian": "Indian River County", "fellsmere": "Indian River County",
}
_COUNTIES = {"martin county", "st. lucie county", "saint lucie county", "indian river county"}

def classify_local_relevance(*, locations=(), county: str | None = None, text: str = "") -> LocalRelevance:
    haystack = " ".join([text, county or "", *[str(x) for x in locations]]).casefold()
    places=[]; counties=[]
    for place, mapped in _PLACE_TO_COUNTY.items():
        if place in haystack:
            places.append(place.title().replace("St. Lucie", "St. Lucie"))
            counties.append(mapped)
    for c in _COUNTIES:
        if c in haystack:
            normalized = "St. Lucie County" if c in {"st. lucie county", "saint lucie county"} else c.title()
            counties.append(normalized)
    counties=tuple(dict.fromkeys(counties)); places=tuple(dict.fromkeys(places))
    if counties: return LocalRelevance("treasure_coast_local", 100, counties, places)
    if "treasure coast" in haystack: return LocalRelevance("treasure_coast_region", 95, (), places)
    if "florida" in haystack or "tallahassee" in haystack: return LocalRelevance("florida", 65, (), places)
    if any(x in haystack for x in ("united states", "u.s.", "national", "washington")): return LocalRelevance("national", 20)
    return LocalRelevance("unknown", 35)
