"""Conservative safeguards for names explicitly attributed in source reporting.

Never identify anyone from a photo or inferred association.  A required name is
created only when the SAME publisher article says someone was arrested/charged
or identifies them as the suspect.  Writer drafts must carry those material facts
or be repaired / withheld.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_NAME = r"[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?(?:\s+(?:[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?|[A-Z]\.)){1,3}"
# Match only an explicit attribution/positive action, not a heading, police
# spokesperson's name, caption filename, or an unverified face/photo.
_ARREST_NAME_PATTERNS = tuple(re.compile(pattern) for pattern in (
    rf"\b(?:[Pp]olice|[Dd]eputies|[Aa]uthorities|[Ii]nvestigators|[Oo]fficers|[Dd]etectives)\s+(?:said\s+(?:they\s+)?(?:have\s+|had\s+)?|have\s+|had\s+)?(?:arrested|charged|apprehended)\s+(?:the\s+)?(?:suspect|driver|man|woman|person)?,?\s*(?:a\s+)?(?:\d{{1,3}}-year-old\s+)?(?P<name>{_NAME})\b",
    rf"\b(?:[Pp]olice|[Dd]eputies|[Aa]uthorities|[Ii]nvestigators|[Oo]fficers|[Dd]etectives)\s+(?:have\s+|had\s+)?(?:identified|named)\s+(?:the\s+)?(?:suspect|driver)\s+as\s+(?:a\s+)?(?:\d{{1,3}}-year-old\s+)?(?P<name>{_NAME})\b",
    rf"\b(?:[Tt]he\s+)?(?:suspect|driver|man|woman|person)\s+(?:was\s+|has\s+been\s+)?(?:identified\s+as|named\s+as)\s+(?:a\s+)?(?:\d{{1,3}}-year-old\s+)?(?P<name>{_NAME})\b",
    rf"\b(?:[Tt]he\s+)?(?:suspect|driver)\s*,\s*(?P<name>{_NAME})\s*,\s*(?:was\s+|has\s+been\s+)(?:arrested|charged|taken\s+into\s+custody)\b",
    rf"\b(?P<name>{_NAME})\s*,?\s*(?:\(?\d{{1,3}}\)?\s*,?\s*)?(?:was\s+|has\s+been\s+|is\s+)(?:arrested|charged|taken\s+into\s+custody|identified\s+as\s+(?:the\s+)?suspect)\b",
    rf"\b(?:[Aa]rrested|[Cc]harged)\s+(?:the\s+)?(?:suspect|driver),?\s+(?:a\s+)?(?:\d{{1,3}}-year-old\s+)?(?P<name>{_NAME})\b",
    rf"\b(?:[Ii]dentified|[Nn]amed)\s+(?P<name>{_NAME})\s+as\s+(?:the\s+)?(?:suspect|driver)\b",
))

_BLOCKED_NAMES = {
    "Police Department", "Sheriff Office", "Sheriff's Office", "Port St", "Port Saint",
    "Port St Lucie", "St Lucie", "Saint Lucie", "United States", "Florida Highway",
    "News Channel", "News Release", "Friday Morning", "Monday Morning",
    "Northwest University", "University Boulevard", "California Boulevard",
    "Police Chief", "Police Say", "Officials Say", "A Man", "The Suspect",
}


# A named charge imported from a publisher's related-story widget is not proof
# that person belongs to the assigned story. These are deliberately narrow,
# *different-incident* families: mere "arrested/charged" wording is not an
# incident identity. If a story intentionally covers both events, its headline
# will explicitly establish both. Otherwise do not auto-insert the accusation.
_STRONG_EVENT_FAMILIES = {
    "burglary": re.compile(r"\b(?:burglar\w*|break[- ]ins?|breaking\s+and\s+entering)\b", re.I),
    "violent_attack": re.compile(r"\b(?:attempted\s+murder|murder|homicide|stabb\w*|slash\w*|shooting|gunfire|box\s+cutter|aggravated\s+battery)\b", re.I),
    "crash": re.compile(r"\b(?:crash\w*|collision|hit[- ]and[- ]run|vehicle\s+struck|car\s+wreck)\b", re.I),
    "financial_fraud": re.compile(r"\b(?:fraud\w*|embezzl\w*|cryptocurrency\s+scheme)\b", re.I),
    "drug_case": re.compile(r"\b(?:drug\s+bust|drug\s+trafficking|narcotics\s+seizure|cocaine\s+seizure)\b", re.I),
}


def conflicting_named_crime_claim(source_title: str, evidence: str) -> bool:
    """True only for an explicit competing crime/incident type.

    This is a safety veto for *automatically mandatory* named-suspect facts.
    Lack of overlap in ordinary wording never proves an unrelated case.
    """
    headline = str(source_title or "")
    claim = str(evidence or "")
    title_events = {name for name, pat in _STRONG_EVENT_FAMILIES.items() if pat.search(headline)}
    claim_events = {name for name, pat in _STRONG_EVENT_FAMILIES.items() if pat.search(claim)}
    return bool(title_events and claim_events and title_events.isdisjoint(claim_events))


@dataclass(frozen=True)
class NamedSuspectFact:
    name: str
    evidence: str


def _sentences(text: str) -> Iterable[str]:
    # Article extracts may be flattened into a single paragraph. Restrict regex
    # to local sentence boundaries to avoid stitching two unrelated statements.
    for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n+", str(text or "")):
        clean = re.sub(r"\s+", " ", part).strip()
        if clean:
            yield clean


def named_suspect_facts(source_text: str, *, max_facts: int = 5, source_title: str = "") -> tuple[NamedSuspectFact, ...]:
    found: list[NamedSuspectFact] = []
    for sentence in _sentences(source_text):
        if not re.search(r"\b(arrested|charged|apprehended|taken into custody|suspect|driver)\b", sentence, re.I):
            continue
        # Ignore reporting about an explicitly denied/unconfirmed arrest.
        if re.search(r"\b(?:not|never|hasn.t|haven.t|wasn.t|didn.t)\s+(?:been\s+)?(?:arrested|charged|identified)\b", sentence, re.I):
            continue
        if source_title and conflicting_named_crime_claim(source_title, sentence):
            # The same HTML page may include a wholly different criminal case.
            # Never make that allegation a mandatory fact in the assigned story.
            continue
        for pattern in _ARREST_NAME_PATTERNS:
            for match in pattern.finditer(sentence):
                name = re.sub(r"\s+", " ", match.group("name")).strip(" ,.;:")
                words = name.split()
                while len(words) > 2 and words[-1].lower() in {
                    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
                    "sunday", "today", "yesterday", "after", "before", "following",
                }:
                    words.pop()
                name = " ".join(words)
                if name in _BLOCKED_NAMES or name.lower() in {"the suspect", "a suspect"}:
                    continue
                if not any(name.lower() == old.name.lower() for old in found):
                    found.append(NamedSuspectFact(name=name, evidence=sentence[:420]))
                if len(found) >= max_facts:
                    return tuple(found)
    return tuple(found)


def unrelated_named_crime_facts(source_title: str, article_text: str) -> tuple[NamedSuspectFact, ...]:
    """Hard publication veto on cross-incident named criminal allegations."""
    return tuple(
        fact for fact in named_suspect_facts(article_text)
        if conflicting_named_crime_claim(source_title, fact.evidence)
    )


def as_named_suspect_facts(facts: Iterable) -> tuple[NamedSuspectFact, ...]:
    result = []
    for fact in facts or ():
        if isinstance(fact, NamedSuspectFact):
            result.append(fact)
        elif isinstance(fact, dict) and fact.get("name") and fact.get("evidence"):
            result.append(NamedSuspectFact(str(fact["name"]), str(fact["evidence"])))
    return tuple(result)


def missing_named_suspects(article_text: str, facts: Iterable[NamedSuspectFact]) -> tuple[NamedSuspectFact, ...]:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(article_text or "").lower()).strip()
    return tuple(
        fact for fact in as_named_suspect_facts(facts)
        if not re.search(
            r"(?<!\w)" + re.escape(re.sub(r"[^a-z0-9]+", " ", fact.name.lower()).strip()) + r"(?!\w)",
            normalized,
        )
    )


def facts_instruction(facts: Iterable[NamedSuspectFact]) -> str:
    facts = as_named_suspect_facts(facts)
    if not facts:
        return ""
    return (
        "\nCRITICAL POSITIVE FACTS FROM THIS SAME SOURCE (never infer an identity from a photograph):\n"
        + "\n".join(f"- {fact.evidence}" for fact in facts)
        + "\nInclude the explicitly identified person's name accurately and with allegation/"
          "police attribution. If that source fact does not fit the assigned event,"
          " do not conflate incidents; report the conflict instead of inventing a connection.\n"
    )


def reconcile_same_article_extraction(primary_text: str, alternate_text: str, *, source_title: str = "") -> str:
    """Retain explicit identifying fact sentences a primary extractor omitted.

    ``alternate_text`` MUST be from the same publisher HTML article, not a
    separate photo search, related-news widget, or a different publisher story.
    No names are guessed and no sentences are manufactured.
    """
    primary = str(primary_text or "").strip()
    alternate = str(alternate_text or "").strip()
    if not primary:
        return alternate
    missing = missing_named_suspects(primary, named_suspect_facts(alternate, source_title=source_title))
    if not missing:
        return primary
    additions = list(dict.fromkeys(fact.evidence for fact in missing))
    return primary + (" " if additions else "") + " ".join(additions)
