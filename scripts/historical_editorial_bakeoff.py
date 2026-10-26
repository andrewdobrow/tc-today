"""Historical TCT source-evidence replay. Never imports or runs the publisher."""
import argparse
import hashlib
import json
import os
import random
import re
import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

MODELS = {"claude": "claude-sonnet-5", "openai": "gpt-6.1-sol"}
RATES = (2.0, 10.0)

# Equivalent output contracts for both model APIs. Keep semantic prompts
# identical; schema-constrained generation avoids charging for malformed JSON.
WRITING_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "teaser": {"type": "string"},
        "body": {"type": "string"},
        "urgency_score": {"type": "integer"},
    },
    "required": ["headline", "teaser", "body", "urgency_score"],
    "additionalProperties": False,
}


def response_schema(ids=None):
    if ids is None:
        return WRITING_SCHEMA
    return {
        "type": "object",
        "properties": {
            "order": {"type": "array", "items": {"type": "string", "enum": ids}},
            "reasons": {
                "type": "object",
                "properties": {key: {"type": "string"} for key in ids},
                "required": ids,
                "additionalProperties": False,
            },
        },
        "required": ["order", "reasons"],
        "additionalProperties": False,
    }


def validate_response(result, ids=None):
    if not isinstance(result, dict):
        return ["invalid_json_object"]
    if ids is None:
        if any(not isinstance(result.get(k), str) or not result[k].strip()
               for k in ("headline", "teaser", "body")):
            return ["incomplete_draft"]
        score = result.get("urgency_score")
        if type(score) is not int or not 0 <= score <= 10:
            return ["invalid_urgency_score"]
        return []
    order = result.get("order")
    reasons = result.get("reasons")
    if (not isinstance(order, list) or len(order) != len(ids) or
            any(not isinstance(item, str) for item in order) or
            set(order) != set(ids) or
            not isinstance(reasons, dict) or
            set(reasons) != set(ids) or
            any(not isinstance(reasons[k], str) or not reasons[k].strip()
                for k in ids)):
        return ["invalid_ranking"]
    return []


def urlkey(value):
    try:
        u = urlsplit(str(value or ""))
        path = u.path.lower().rstrip("/")
        if u.scheme not in ("http", "https") or not u.hostname or len(path) < 9:
            return ""
        host = u.hostname.lower().removeprefix("www.")
        return "" if host.endswith("news.google.com") else host + path
    except (TypeError, ValueError):
        return ""


def archived_sources(depth):
    # One immutable cache snapshot per historic day, spanning months rather than
    # taking the last N hourly runs (which would cover only a few days).
    history = subprocess.check_output(
        ["git", "log", "--format=%H%x09%ad", "--date=short",
         "--", "data/generation-cache.json"], text=True).splitlines()
    commits, seen_days = [], set()
    for line in history:
        parts = line.split("\t", 1)
        if len(parts) != 2 or parts[1] in seen_days:
            continue
        commits.append(parts[0])
        seen_days.add(parts[1])
        if len(commits) >= depth:
            break
    sources = {}
    for sha in commits:
        try:
            text = subprocess.check_output(
                ["git", "show", sha+":data/generation-cache.json"],
                text=True, timeout=35)
            cache = json.loads(text)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            continue
        for item in (cache.get("source_text") or {}).values():
            value = item.get("value") if isinstance(item, dict) else None
            if not isinstance(value, dict):
                continue
            url = urlkey(value.get("url"))
            text = re.sub(r"\s+", " ", str(value.get("text") or "")).strip()
            if not url or len(text.split()) < 110:
                continue
            source = {"source_url": value.get("url"), "evidence": text[:7500],
                      "captured": item.get("cached_at") or "", "snapshot": sha}
            # Preserve original-period evidence, not merely the latest rewrite.
            versions = sources.setdefault(url, {})
            day = str(source["captured"])[:10]
            if day not in versions or len(text) > len(versions[day]["evidence"]):
                versions[day] = source
    return {url: list(v.values()) for url, v in sources.items()}, len(commits)


def cases(archive, source_index, sample_size, seed):
    rows = {}
    for a in archive:
        if not isinstance(a, dict):
            continue
        slug = str(a.get("slug") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{5,180}", slug):
            continue
        if (a.get("canonical_slug", slug) != slug or a.get("is_custom")
                or a.get("sponsored") or a.get("article_type") in ("product_guide", "sponsored")):
            continue
        if a.get("legacy_identity_status") in ("legacy_unresolved", "quarantined"):
            continue
        versions = source_index.get(urlkey(a.get("source_url")))
        if not versions:
            continue
        if isinstance(versions, dict):
            versions = [versions]  # Supports focused offline fixtures.
        day = str(a.get("date") or "")[:10]
        valid = []
        for s in versions:
            try:
                delta = (date.fromisoformat(str(s["captured"])[:10]) - date.fromisoformat(day)).days
            except ValueError:
                continue
            # Evidence dated after publication would leak later facts into the replay.
            # Archive publication timestamps are day-level, so same-day later
            # developments remain a documented limitation, not an as-of-time proof.
            if -1 <= delta <= 0:
                valid.append((abs(delta), -len(s["evidence"]), s))
        if not valid:
            continue
        s = sorted(valid, key=lambda x: (x[0], x[1]))[0][2]
        rows[slug] = {"id": hashlib.sha256(slug.encode()).hexdigest()[:12],
                      "slug": slug, "date": day,
                      "section": a.get("category_label") or "",
                      "source_headline": a.get("source_headline") or "",
                      "reference_headline": a.get("headline") or "", **s}
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for x in rows.values():
        buckets[(x["date"][:7], x["section"])].append(x)
    for values in buckets.values():
        rng.shuffle(values)
    keys = sorted(buckets)
    rng.shuffle(keys)
    chosen = []
    while keys and len(chosen) < sample_size:
        remaining = []
        for key in keys:
            if buckets[key] and len(chosen) < sample_size:
                chosen.append(buckets[key].pop())
            if buckets[key]:
                remaining.append(key)
        keys = remaining
    return chosen, len(rows), list(rows.values())


def writing_prompt(x):
    return ("You write factually rigorous Treasure Coast Today local news. "
            "Write AS OF the historical date, NOT today. ONLY use the supplied "
            "archived source excerpt. Do not invent quotes, attributions, dates, "
            "interviews, allegations or later developments. Do not mention competing "
            "news outlets in published prose. Return only JSON with fields "
            "headline, teaser, body (aim for 160-300 words, shorter if the source "
            "is limited; never pad with unsupported details), urgency_score (integer 0-10). "
            "No markdown.\nHistorical date: "+x["date"]+"\nSection: "+x["section"]+
            "\nOriginal-source title: "+x["source_headline"]+
            "\nArchived source text:\n"+x["evidence"])


def ranking_groups(eligible, max_groups=8, seed=20261025):
    """Build independent same-day ranking cohorts from the entire eligible corpus.

    Writing stratification must not determine whether homepage judgment is tested.
    Require distinct original source URLs within a day to avoid ranking one
    incident's duplicated source as separate front-page news.
    """
    dates = defaultdict(list)
    for row in eligible:
        dates[row["date"]].append(row)
    rng = random.Random(seed)
    by_month = defaultdict(list)
    for day, rows in sorted(dates.items()):
        distinct = {}
        for row in sorted(rows, key=lambda x: (x["source_url"], x["slug"])):
            key = urlkey(row["source_url"])
            if key:
                distinct.setdefault(key, row)
        if len(distinct) < 3:
            continue
        candidates = list(distinct.values())
        rng.shuffle(candidates)
        by_month[day[:7]].append({"date": day, "rows": candidates[:6]})
    for values in by_month.values():
        rng.shuffle(values)
    # Round-robin by month preserves historical diversity in the ranking test.
    months = sorted(by_month)
    rng.shuffle(months)
    groups = []
    while months and len(groups) < max_groups:
        remaining = []
        for month in months:
            if by_month[month] and len(groups) < max_groups:
                groups.append(by_month[month].pop())
            if by_month[month]:
                remaining.append(month)
        months = remaining
    return groups


def ranking_prompt(group):
    candidates = [{"id": x["id"], "headline": x["source_headline"],
                   "evidence": x["evidence"][:2000], "date": x["date"]}
                  for x in group["rows"]]
    return ("You are TCT's homepage editor on "+group["date"]+
            ". Rank these contemporaneous local events for the lead story and "
            "homepage, considering public impact, urgency, verified facts and "
            "local relevance. Use only evidence. Return only JSON with 'order' "
            "(every candidate ID once, most important first) and 'reasons' "
            "(ID-to-explanation mapping).\n"+json.dumps(candidates))


def complete(provider, prompt, ids=None):
    """Count tokens even when the provider returns an unparseable billed result."""
    schema = response_schema(ids)
    if provider == "claude":
        import anthropic
        r = anthropic.Anthropic(max_retries=2, timeout=100).messages.create(
            model=MODELS[provider], max_tokens=1800,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}})
        raw = "".join(x.text for x in r.content if getattr(x, "type", "") == "text")
        tokens = [r.usage.input_tokens, r.usage.output_tokens]
        incomplete = r.stop_reason == "max_tokens"
    else:
        from openai import OpenAI
        r = OpenAI(max_retries=2, timeout=100).responses.create(
            model=MODELS[provider], input=prompt,
            reasoning={"effort": "medium"}, max_output_tokens=3200,
            text={"format": {
                "type": "json_schema", "name": "tct_editorial_result",
                "schema": schema, "strict": True}})
        raw = r.output_text
        tokens = [r.usage.input_tokens, r.usage.output_tokens]
        incomplete = r.status == "incomplete"
    error = None
    try:
        result = json.loads(raw.strip())
    except (ValueError, AttributeError) as exc:
        result = {}
        error = type(exc).__name__ + ": " + str(exc)[:170]
    flags = []
    if incomplete:
        flags.append("response_truncated")
    if error:
        flags.append("response_parse_failed")
    return {
        "result": result, "tokens": tokens,
        "estimated_cost_usd": round(sum(x*y for x, y in zip(tokens, RATES))/1000000, 6),
        "screening_flags": flags,
        **({"error": error} if error else {}),
    }


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


def markdown(drafts, ranks):
    txt = ["# TCT blind historical editorial comparison", "",
           "Each model saw the same archived SOURCE EVIDENCE, never TCT's finished "
           "article. The existing headline is a human review reference only.",
           "Human scoring: accuracy 30, judgment 25, context 20, writing 15, "
           "local relevance 10. Disqualify fabrication, false allegations, or "
           "wrong incidents. Automated screening is NOT independent fact checking.", ""]
    for item in drafts:
        x = item["source"]
        txt += ["## "+x["date"]+" / "+x["id"], "",
                "Published TCT reference: "+x["reference_headline"],
                "https://treasurecoast.today/articles/"+x["slug"]+".html",
                "Source: "+x["source_url"], "", "Original source evidence captured: "+str(x.get("captured", "")),
                 "Snapshot: "+str(x.get("snapshot", "")), "", x["evidence"], ""]
        for label in ("A", "B"):
            v = item["variants"].get(label) or {}
            result = v.get("result") or {}
            txt += ["### Variant "+label, "", result.get("headline", ""),
                    result.get("teaser", ""), "", result.get("body", ""),
                    "", "Review __/100. Disqualifier? __. Notes: __", ""]
    for item in ranks:
        txt += ["## Rank "+item["date"]]
        for candidate in item.get("candidates", []):
            txt += [candidate["id"]+": "+candidate["source_headline"],
                    "Source: "+candidate["source_url"],
                    "Ranking evidence (entire 2,000-character prompt excerpt): "+
                    candidate["evidence"][:2000], ""]
        for label in ("A", "B"):
            txt += [label+": "+json.dumps(
                (item["variants"].get(label) or {}).get("result") or {}, ensure_ascii=False), ""]
    return "\n".join(txt)


def run(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    archive = json.loads(Path("archive.json").read_text())
    originals, history_count = archived_sources(args.history)
    pool, eligible, all_candidates = cases(archive, originals, args.count, args.seed)
    ranking_candidates = ranking_groups(all_candidates, seed=args.seed)
    dump(output/"coverage.json", {"eligible": eligible, "sampled": len(pool),
        "history_snapshots": history_count, "source_urls": len(originals),
        "months": sorted({x["date"][:7] for x in pool}),
        "ranking_cohorts": len(ranking_candidates),
        "ranking_dates": [g["date"] for g in ranking_candidates],
        "evidence_date_rule": "source captured on or before publication date (up to 1 day before)"})
    dump(output/"source-cases.json", pool)
    dump(output/"ranking-candidate-groups.json", ranking_candidates)
    if len(pool) < args.min_cases:
        raise RuntimeError("Too few verified historical article-source matches; "
                           "increase --history. No fabricated fallback allowed.")
    if not ranking_candidates:
        raise RuntimeError("No same-day ranking cohorts with at least 3 distinct original "
                           "source URLs. Cannot claim to test homepage judgment; "
                           "review coverage artifact and improve historical evidence.")
    if args.dry_run:
        print("Historical dry run:", len(pool), "writing matches and",
              len(ranking_candidates), "ranking cohorts")
        return
    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Add GitHub Actions secrets ANTHROPIC_API_KEY and OPENAI_API_KEY.")
    drafts, ranks, key = [], [], {}
    usage = {p: {"calls": 0, "usd": 0.0, "tokens": [0, 0]} for p in MODELS}
    total = 0.0

    def variants(identifier, prompt, ids=None):
        nonlocal total
        first = "claude" if int(hashlib.sha256(
            (str(args.seed)+identifier).encode()).hexdigest()[-1], 16) % 2 else "openai"
        second = "openai" if first == "claude" else "claude"
        key[identifier] = {"A": first, "B": second}
        value = {}
        for label, provider in (("A", first), ("B", second)):
            if total + .20 > args.max_cost:
                raise RuntimeError("Estimated API spending cap reached.")
            try:
                data = complete(provider, prompt, ids)
                result = data["result"]
                errors = list(data.get("screening_flags") or [])
                errors.extend(validate_response(result, ids))
                if ids is None and isinstance(result, dict):
                    if re.search(r"\b(WPTV|WPBF|WPEC|CBS12|TCPalm|WFLX)\b",
                                 str(result.get("body") or ""), re.I):
                        errors.append("competitor_name_in_body")
                    source_text = " ".join(prompt.split()).lower()
                    for quote in re.findall(r'["“]([^"”]{12,})["”]',
                                            str(result.get("body") or "")):
                        if " ".join(quote.split()).lower() not in source_text:
                            errors.append("quote_not_verbatim_in_source")
                            break
                data["screening_flags"] = sorted(set(errors))
                total += data["estimated_cost_usd"]
                u = usage[provider]
                u["calls"] += 1
                u["usd"] += data["estimated_cost_usd"]
                u["tokens"] = [u["tokens"][i]+data["tokens"][i] for i in (0,1)]
                value[label] = data
            except Exception as exc:
                value[label] = {"result": {}, "screening_flags": ["request_failed"],
                                "error": type(exc).__name__+": "+str(exc)[:240]}
        return value

    try:
        for x in pool:
            drafts.append({"source": x, "variants": variants(x["id"], writing_prompt(x))})
            dump(output/"writing.json", drafts)
        for group in ranking_candidates:
            ids = [r["id"] for r in group["rows"]]
            ranks.append({"date": group["date"], "candidate_ids": ids,
                          "candidates": group["rows"],
                          "variants": variants("rank:"+group["date"], ranking_prompt(group), ids)})
            dump(output/"ranking.json", ranks)
    finally:
        dump(output/"answer-key.json", {"mapping": key, "models": MODELS})
        dump(output/"usage.json", {"providers": usage, "estimated_total_usd": round(total, 5)})
        (output/"blind-review.md").write_text(markdown(drafts, ranks), encoding="utf-8")
    fatal_flags = {"request_failed", "response_truncated", "response_parse_failed",
                   "invalid_json_object", "incomplete_draft", "invalid_urgency_score",
                   "invalid_ranking"}
    if any(fatal_flags.intersection(
               (item["variants"].get(label) or {}).get("screening_flags") or [])
           for item in drafts + ranks for label in ("A", "B")):
        raise RuntimeError("One or more provider results were missing, truncated or "
                           "invalid. Inspect blind writing/ranking artifacts and "
                           "usage.json; no incomplete case can be scored.")
    print("Compared", len(drafts), "historic article cases and", len(ranks),
          "ranking groups. Estimated cost USD", round(total, 5))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--history", type=int, default=80)
    p.add_argument("--min-cases", type=int, default=12)
    p.add_argument("--seed", type=int, default=20261025)
    p.add_argument("--max-cost", type=float, default=12.0)
    p.add_argument("--output", default="editorial-bakeoff-output")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not 12 <= args.count <= 50 or not 10 <= args.history <= 160:
        p.error("count must be 12-50, history 10-160")
    if not 12 <= args.min_cases <= args.count or not 2 <= args.max_cost <= 50:
        p.error("invalid minimum cases or max cost")
    run(args)


if __name__ == "__main__":
    main()
