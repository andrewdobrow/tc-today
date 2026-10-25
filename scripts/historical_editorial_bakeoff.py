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
            if url not in sources or len(text) > len(sources[url]["evidence"]):
                sources[url] = source
    return sources, len(commits)


def cases(archive, source_index, sample_size, seed):
    rows = {}
    for a in archive:
        if not isinstance(a, dict):
            continue
        slug = str(a.get("slug") or "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{5,180}", slug):
            continue
        if a.get("canonical_slug", slug) != slug or a.get("is_custom"):
            continue
        if a.get("legacy_identity_status") in ("legacy_unresolved", "quarantined"):
            continue
        s = source_index.get(urlkey(a.get("source_url")))
        if not s:
            continue
        day = str(a.get("date") or "")[:10]
        try:
            delta = (date.fromisoformat(str(s["captured"])[:10]) - date.fromisoformat(day)).days
            if not -2 <= delta <= 21:
                continue
        except ValueError:
            continue
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
            "headline, teaser, body (160-300 words), urgency_score (integer 0-10). "
            "No markdown.\nHistorical date: "+x["date"]+"\nSection: "+x["section"]+
            "\nOriginal-source title: "+x["source_headline"]+
            "\nArchived source text:\n"+x["evidence"])


def ranking_groups(selected):
    dates = defaultdict(list)
    for row in selected:
        dates[row["date"]].append(row)
    return [{"date": d, "rows": v[:6]} for d, v in sorted(dates.items()) if len(v) >= 3]


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


def complete(provider, prompt):
    if provider == "claude":
        import anthropic
        r = anthropic.Anthropic(max_retries=2, timeout=100).messages.create(
            model=MODELS[provider], max_tokens=1800,
            messages=[{"role": "user", "content": prompt}])
        raw = "".join(x.text for x in r.content if getattr(x, "type", "") == "text")
        tokens = [r.usage.input_tokens, r.usage.output_tokens]
    else:
        from openai import OpenAI
        r = OpenAI(max_retries=2, timeout=100).responses.create(
            model=MODELS[provider], input=prompt,
            reasoning={"effort": "medium"}, max_output_tokens=3200)
        raw = r.output_text
        tokens = [r.usage.input_tokens, r.usage.output_tokens]
    result = json.loads(raw.strip())
    return {"result": result, "tokens": tokens,
            "estimated_cost_usd": round(sum(x*y for x,y in zip(tokens, RATES))/1000000, 6)}


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
                "Source: "+x["source_url"], "", x["evidence"][:3000], ""]
        for label in ("A", "B"):
            v = item["variants"].get(label) or {}
            result = v.get("result") or {}
            txt += ["### Variant "+label, "", result.get("headline", ""),
                    result.get("teaser", ""), "", result.get("body", ""),
                    "", "Review __/100. Disqualifier? __. Notes: __", ""]
    for item in ranks:
        txt += ["## Rank "+item["date"]]
        for candidate in item.get("candidates", []):
            txt += [candidate["id"]+": "+candidate["source_headline"]+
                    " / "+candidate["evidence"][:650]]
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
    dump(output/"coverage.json", {"eligible": eligible, "sampled": len(pool),
        "history_snapshots": history_count, "source_urls": len(originals),
        "months": sorted({x["date"][:7] for x in pool})})
    if len(pool) < args.min_cases:
        raise RuntimeError("Too few verified historical article-source matches; "
                           "increase --history. No fabricated fallback allowed.")
    dump(output/"source-cases.json", pool)
    ranking_candidates = ranking_groups(all_candidates)
    dump(output/"ranking-candidate-groups.json", ranking_candidates)
    if args.dry_run:
        print("Historical dry run:", len(pool), "matches")
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
                data = complete(provider, prompt)
                result = data["result"]
                errors = []
                if ids is None:
                    if not isinstance(result, dict) or any(
                        not isinstance(result.get(k), str) or not result[k].strip()
                        for k in ("headline", "teaser", "body")):
                        errors.append("incomplete_draft")
                    if re.search(r"\b(WPTV|WPBF|WPEC|CBS12|TCPalm|WFLX)\b",
                                 str(result.get("body") or ""), re.I):
                        errors.append("competitor_name_in_body")
                elif not isinstance(result, dict) or sorted(result.get("order") or []) != sorted(ids):
                    errors.append("invalid_ranking")
                data["screening_flags"] = errors
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
    if any(usage[p]["calls"] < len(drafts) for p in MODELS):
        raise RuntimeError("One provider failed on historic article requests. "
                           "Inspect request errors in the private artifact.")
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
