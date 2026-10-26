"""Manual, read-only production-PROMPT shadow on frozen TCT assignment candidates.

Imports the real editor and writer functions; never invokes generate.main,
publishing, archive mutation, newsletters, or scheduled production workflows.
The source inputs are reconstructed from archived evidence, NOT verbatim
captured production packets. Do not infer canonical-update/identity parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.historical_editorial_bakeoff import urlkey

MODELS = {"claude": "claude-sonnet-5", "openai": "gpt-6.1-sol"}
PRICES = {"claude": (2, 10), "openai": (2, 10)}
COUNTY_KEYS = {"martin", "st_lucie", "indian_river"}
SAMPLE_LIMIT = 2


def saved(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def utc(value):
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def frozen_evidence(*, allowed_urls, cutoff, historic_days=100, max_age_days=7):
    """Exact source URLs, captured before the source pool was actually reported."""
    log = subprocess.check_output(
        ["git", "log", "--format=%H%x09%ad", "--date=short", "--",
         "data/generation-cache.json"], text=True).splitlines()
    daily = []
    seen = set()
    for line in log:
        sha, _, day = line.partition("\t")
        if not day or day in seen:
            continue
        seen.add(day)
        daily.append(sha)
        if len(daily) >= historic_days:
            break

    matched = {}
    inspected = 0
    for sha in daily:
        try:
            cache = json.loads(subprocess.check_output(
                ["git", "show", sha + ":data/generation-cache.json"],
                text=True, timeout=35))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                UnicodeError, ValueError):
            continue
        inspected += 1
        for entry in (cache.get("source_text") or {}).values():
            if not isinstance(entry, dict):
                continue
            v = entry.get("value")
            if not isinstance(v, dict):
                continue
            key = urlkey(v.get("url"))
            if key not in allowed_urls:
                continue
            content = re.sub(r"\s+", " ", str(v.get("text") or "")).strip()
            if len(content.split()) < 110:
                continue
            try:
                captured = utc(entry.get("cached_at"))
            except (TypeError, ValueError):
                continue
            age = cutoff - captured
            if not timedelta(0) <= age <= timedelta(days=max_age_days):
                continue
            previous = matched.get(key)
            if previous is None or captured > utc(previous["captured"]):
                matched[key] = {
                    "evidence": content[:7500],
                    "source_url": v.get("url"),
                    "captured": captured.isoformat(),
                    "commit": sha,
                }
    return matched, inspected


def prepare_cases(report, evidence, *, limit):
    """Preserve real production candidate order and metadata; fail on absent text."""
    valid, diagnostic = [], []
    for cat in report.get("categories") or []:
        pool = cat.get("source_pool") or []
        key = str(cat.get("category_key") or "")
        if not key or not isinstance(pool, list):
            continue
        missing = [p.get("source_url") for p in pool
                   if not isinstance(p, dict) or
                   not evidence.get(urlkey(p.get("source_url")))]
        unique_urls = {urlkey(p.get("source_url")) for p in pool if isinstance(p, dict)}
        ready = not missing and len(unique_urls - {""}) >= 2
        diagnostic.append({
            "category_key": key, "original_sources": len(pool),
            "unique_source_urls": len(unique_urls - {""}),
            "missing_source_urls": missing, "ready": ready,
        })
        if not ready:
            continue
        rows = []
        for index, p in enumerate(pool, 1):
            e = evidence[urlkey(p["source_url"])]
            rows.append({
                "source_index": index, "title": p.get("title") or "",
                "published": p.get("published") or "",
                "source_type": p.get("source_type") or "publisher",
                "source_quality": p.get("source_quality") or "full",
                "hero_eligible": str(p.get("hero_eligible") or "").lower() in ("yes", "true", "1"),
                "category_match_score": p.get("category_match_score") or 0,
                "article_text": e["evidence"],
                "source_url": p["source_url"], "link": p["source_url"],
                "story_form": "new",
                "canonical_context_headline": "",
                "canonical_context_body": "",
            })
        original = cat.get("assignment_plan") or {}
        hero = original.get("hero") or {}
        fixed_idx = hero.get("source_index")
        if not isinstance(fixed_idx, int) or fixed_idx < 1 or fixed_idx > len(rows):
            fixed_idx = 1
        fixed = {
            "source_index": fixed_idx,
            "angle": hero.get("angle") or "Lead with the verified news development",
            "urgency_score": (hero.get("urgency_score")
                              if isinstance(hero.get("urgency_score"), int) else 6),
        }
        valid.append({
            "key": key, "label": cat.get("category_label") or key,
            "packet": {"category_key": key,
                       "category_label": cat.get("category_label") or key,
                       "source_inputs": rows},
            "fixed_writer_assignment": fixed,
            "production_reference": {
                "hero_source_index": (cat.get("final_baseline_output") or
                                      cat.get("baseline_output") or {}).get("hero", {}).get("source_index"),
            },
        })
    # Favor independent county categories, then richer candidate pools.
    valid.sort(key=lambda c: (c["key"] not in COUNTY_KEYS,
                              -len({urlkey(x["source_url"])
                                    for x in c["packet"]["source_inputs"]}),
                              c["key"]))
    return valid[:limit], diagnostic


def schema(mode, require_fit):
    assignment = {
        "type": "object",
        "properties": {
            "source_index": {"type": "integer"},
            "angle": {"type": "string"},
            "urgency_score": {"type": "integer"},
        },
        "required": ["source_index", "angle", "urgency_score"],
        "additionalProperties": False,
    }
    if mode == "writer":
        fields = {
            "headline": {"type": "string"}, "teaser": {"type": "string"},
            "body": {"type": "string"}, "urgency_score": {"type": "integer"},
        }
        return {"type": "object", "properties": fields,
                "required": list(fields), "additionalProperties": False}
    props = {"hero": assignment, "cards": {"type": "array", "items": assignment}}
    if require_fit:
        fit = {"type": "object", "properties": {
            "source_index": {"type": "integer"},
            "fits_category": {"type": "boolean"},
            "reason": {"type": "string"},
        }, "required": ["source_index", "fits_category", "reason"],
               "additionalProperties": False}
        props["category_fit"] = {"type": "array", "items": fit}
    return {"type": "object", "properties": props,
            "required": list(props), "additionalProperties": False}


def prompt_content(value):
    """Preserve role text and cached system text without transferring cache metadata."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(c.get("text") or "") if isinstance(c, dict) else str(c)
            for c in value)
    return str(value or "")


def read_messages(kwargs):
    chunks = []
    system = kwargs.get("system")
    if system:
        chunks.append("SYSTEM:\n" + prompt_content(system))
    for msg in kwargs.get("messages") or []:
        chunks.append(str(msg.get("role") or "user").upper() + ":\n" +
                      prompt_content(msg.get("content")))
    return "\n\n".join(chunks)


class Budget:
    def __init__(self, ceiling):
        self.ceiling = float(ceiling)
        self.estimated_usd = 0.
        self.calls = []

    def check(self):
        if self.estimated_usd + .20 > self.ceiling:
            raise RuntimeError("Conservative $0.20 per-request cost reserve reached; no further API calls")



def copydesk_attempt_diagnostics(attempts, detector=None):
    """Inspect *unpublished* writer attempts using the unchanged TCT detector.

    Captures both the first rejected draft and any subsequent copy-desk repair.
    Diagnostics annotate the response; they never override publication guards.
    """
    results = []
    for attempt in attempts or []:
        if attempt.get("mode") != "writer":
            continue
        row = dict(attempt)
        raw = str(row.get("raw_response") or "")
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            payload = {}
            row["response_parse_error"] = True
        if not isinstance(payload, dict):
            payload = {}
            row["response_parse_error"] = True
        row["draft"] = {
            key: str(payload.get(key) or "")
            for key in ("headline", "teaser", "body")
        }
        row["copydesk_issues"] = []
        if callable(detector):
            for field in ("headline", "teaser", "body"):
                draft_text = row["draft"].get(field, "")
                if not draft_text:
                    continue
                try:
                    issues = detector(draft_text)
                except Exception as exc:
                    row["copydesk_detector_error"] = type(exc).__name__
                    continue
                for issue in issues or []:
                    if isinstance(issue, dict):
                        record = {
                            "field": field,
                            "code": str(issue.get("code") or "unknown"),
                        }
                        for name in ("sentence", "excerpt", "text", "detail", "reason"):
                            if issue.get(name):
                                record[name] = str(issue[name])[:350]
                        row["copydesk_issues"].append(record)
        results.append(row)
    return results


class Adapter:
    """Expose Anthropic's messages interface to the actual TCT editor/writer."""
    def __init__(self, provider, budget, require_fit):
        self.provider = provider
        self.budget = budget
        self.require_fit = require_fit
        self.mode = "editor"
        self.messages = SimpleNamespace(create=self.create)
        self.prompts = []
        self.attempts = []  # Entire unpublished model responses, including repair attempts.
        self._anthropic = None
        self._openai = None

    def with_options(self, **kwargs):
        return self

    def create(self, **kwargs):
        self.budget.check()
        prompt = read_messages(kwargs)
        self.prompts.append({"mode": self.mode, "prompt_sha256":
                             hashlib.sha256(prompt.encode()).hexdigest()})
        contract = schema(self.mode, self.require_fit)
        if self.provider == "claude":
            if self._anthropic is None:
                import anthropic
                self._anthropic = anthropic.Anthropic(max_retries=1, timeout=110)
            request = dict(kwargs)
            request["model"] = MODELS["claude"]
            request["output_config"] = {"format": {"type": "json_schema",
                                                   "schema": contract}}
            r = self._anthropic.messages.create(**request)
            raw = "".join(x.text for x in r.content if getattr(x, "type", "") == "text")
            tokens = (r.usage.input_tokens, r.usage.output_tokens)
            stop = r.stop_reason
        else:
            if self._openai is None:
                from openai import OpenAI
                self._openai = OpenAI(max_retries=1, timeout=110)
            messages = [
                {"role": m.get("role") or "user",
                 "content": prompt_content(m.get("content"))}
                for m in kwargs.get("messages") or []
            ]
            args = {"model": MODELS["openai"], "input": messages,
                    "reasoning": {"effort": "medium"},
                    "max_output_tokens": 3000,
                    "text": {"format": {"type": "json_schema",
                                        "name": "tct_shadow_contract",
                                        "schema": contract, "strict": True}}}
            if kwargs.get("system"):
                args["instructions"] = prompt_content(kwargs["system"])
            r = self._openai.responses.create(**args)
            raw = r.output_text or ""
            tokens = (r.usage.input_tokens, r.usage.output_tokens)
            stop = r.status
        rate = PRICES[self.provider]
        cost = (tokens[0] * rate[0] + tokens[1] * rate[1]) / 1_000_000
        self.budget.estimated_usd += cost
        self.budget.calls.append({"provider": self.provider, "mode": self.mode,
                                  "input_tokens": tokens[0], "output_tokens": tokens[1],
                                  "estimated_usd": round(cost, 6),
                                  "response_state": stop})
        # Save the *raw response before* any JSON parsing or production copy-desk
        # checks. This enables a free retrospective diagnosis if the writer raises.
        self.attempts.append({
            "mode": self.mode, "sequence": len(self.attempts) + 1,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "response_state": str(stop), "raw_response": raw,
            "input_tokens": tokens[0], "output_tokens": tokens[1],
        })
        json.loads(raw)  # Fail on invalid billed responses rather than silently scoring.
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=raw)],
            model=MODELS[self.provider],
            usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]),
            stop_reason="end_turn")


def blind_label(category, provider, seed):
    bit = hashlib.sha256(f"{seed}:{category}".encode()).digest()[0] & 1
    return "A" if (provider == "claude") == bool(bit) else "B"


def render_blind_review(rows):
    """Format an existing result artifact without API calls or model labels.

    The paid job stores source_inputs in each result row, not a nested packet.
    Report a missing writer as a failure, never as empty successful copy.
    """
    lines = [
        "# TCT production-prompt shadow — blind review", "",
        "Actual TCT editor and writer functions were used in the original run.",
        "The historical source text was reconstructed from archived caches; it is",
        "NOT a captured exact production packet. Canonical context was unavailable.",
        "Identity matching, material updates and final homepage ranking were not tested.",
        "Both variants are anonymized. Record judgments before opening answer-key.json.",
        "A model's copy-desk validation failure is a real writing failure, not a",
        "technical scoring tie and not permission to publish the rejected copy.", "",
    ]
    for row in rows:
        lines.extend([
            "## " + str(row.get("category_label") or row.get("category_key") or "Unknown"),
            "", "Reference production hero source index: " +
            str((row.get("production_reference") or {}).get("hero_source_index")), "",
            "**Original source evidence**", "",
        ])
        sources = row.get("source_inputs")
        if sources is None:
            sources = (row.get("packet") or {}).get("source_inputs") or []
        for source in sources:
            lines.extend([
                "### Source #" + str(source.get("source_index") or "?") +
                ": " + str(source.get("title") or ""),
                str(source.get("source_url") or ""),
                "Published: " + str(source.get("published") or ""),
                "", str(source.get("article_text") or ""),
                "",
            ])
        assignment = row.get("fixed_writer_assignment") or {}
        lines.extend([
            "**Controlled writing task:** Both variants receive source #" +
            str(assignment.get("source_index") or "?"),
            "Fixed angle: " + str(assignment.get("angle") or ""), "",
        ])
        for label in ("A", "B"):
            item = (row.get("variants") or {}).get(label) or {}
            status = str(item.get("status") or "missing")
            lines.extend(["### Variant " + label, "",
                          "**Status:** " + status, ""])
            if item.get("error"):
                lines.extend(["**Blocked by:** " + str(item["error"]), ""])
            plan = item.get("editor_plan")
            if isinstance(plan, dict):
                lines.extend(["**Actual assignment editor plan:**", "",
                              json.dumps(plan, ensure_ascii=False, indent=2), ""])
            else:
                lines.extend(["**Assignment plan unavailable.**", ""])
            draft = item.get("writer_fixed_source")
            if isinstance(draft, dict):
                lines.extend([
                    "**Writer headline:** " + str(draft.get("headline") or ""),
                    "**Writer teaser:** " + str(draft.get("teaser") or ""),
                    "", str(draft.get("body") or ""), "",
                ])
            else:
                lines.extend(["**No publishable writer result was returned.**", ""])
            writer_attempts = item.get("writer_attempts") or []
            if writer_attempts:
                lines.extend(["**Unpublished writer attempts (diagnostics only):**",
                              "These are NOT approved copy; preserve the original and repair.",
                              ""])
                for attempt in writer_attempts:
                    lines.extend([
                        "**Attempt #" + str(attempt.get("sequence") or "?") + "**",
                        "Response state: " + str(attempt.get("response_state") or ""),
                        "TCT copy-desk issues: " + json.dumps(
                            attempt.get("copydesk_issues") or [], ensure_ascii=False),
                        "",
                    ])
                    proposal = attempt.get("draft") or {}
                    lines.extend([
                        "Proposed headline: " + str(proposal.get("headline") or ""),
                        "Proposed teaser: " + str(proposal.get("teaser") or ""),
                        "", str(proposal.get("body") or attempt.get("raw_response") or ""), "",
                    ])
            elif status == "writer_failed":
                lines.extend([
                    "**Rejected raw drafts were not captured in this run.**",
                    "Do not infer why the copy-desk check failed without draft text.",
                    "",
                ])
            lines.extend([
                "Assignment judgment __ / Writing judgment __ / Fact flags __",
                "Reviewer notes: __", "",
            ])
    return "\n".join(lines) + "\n"


def summarize_shadow_results(rows, usage=None):
    """Always distinguish complete model pairs from incomplete quality outcomes."""
    rows = list(rows)
    complete_pairs = []
    editor_pairs = []
    failed = []
    for row in rows:
        variants = row.get("variants") or {}
        key = str(row.get("category_key") or "unknown")
        if all((variants.get(k) or {}).get("status") == "complete"
               for k in ("A", "B")):
            complete_pairs.append(key)
        if all(isinstance((variants.get(k) or {}).get("editor_plan"), dict)
               for k in ("A", "B")):
            editor_pairs.append(key)
        for label in ("A", "B"):
            v = variants.get(label) or {}
            if v.get("status") != "complete":
                failed.append({"category_key": key, "variant": label,
                               "status": v.get("status") or "missing",
                               "error": v.get("error") or ""})
    return {
        "categories_attempted": len(rows),
        "complete_writing_and_editor_pairs": len(complete_pairs),
        "complete_pair_categories": complete_pairs,
        "complete_assignment_editor_pairs": len(editor_pairs),
        "assignment_editor_pair_categories": editor_pairs,
        "failed_variants": failed,
        "result": ("complete" if len(complete_pairs) == len(rows) and rows
                   else "partial" if rows else "empty"),
        "estimated_api_cost_usd": (usage or {}).get("estimated_usd", 0),
        "provider_api_calls": len((usage or {}).get("calls") or []),
    }


def recover_existing_results(output):
    """Create missing blind review and summary from a saved Actions artifact, for $0."""
    rows = json.loads((output / "results.json").read_text(encoding="utf-8"))
    usage_path = output / "usage.json"
    usage = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.exists() else {}
    (output / "blind-review.md").write_text(
        render_blind_review(rows), encoding="utf-8")
    summary = summarize_shadow_results(rows, usage)
    saved(output / "summary.json", summary)
    return summary


def produce(cases, ceiling, seed, output):
    from scripts import generate  # Import only, never execute the publishing entrypoint.
    budget = Budget(ceiling)
    completed = []
    key = {}
    try:
        for case in cases:
            packet = case["packet"]
            row = {"category_key": case["key"], "category_label": case["label"],
                   "source_inputs": packet["source_inputs"],
                   "fixed_writer_assignment": case["fixed_writer_assignment"],
                   "production_reference": case["production_reference"],
                   "variants": {}}
            for provider in sorted(MODELS, key=lambda p: blind_label(case["key"], p, seed)):
                label = blind_label(case["key"], provider, seed)
                key.setdefault(case["key"], {})[label] = provider
                adapter = Adapter(provider, budget, case["key"] not in COUNTY_KEYS)
                item = {"status": "editor_pending", "prompts": adapter.prompts}
                row["variants"][label] = item
                try:
                    generate.client = adapter
                    adapter.mode = "editor"
                    plan, diagnostics, _, _ = generate._run_assignment_editor(packet)
                    item["editor_plan"] = plan
                    item["editor_diagnostics"] = diagnostics
                    item["status"] = "writer_pending"
                    adapter.mode = "writer"
                    draft, _, _ = generate._run_assignment_writer(
                        packet, case["fixed_writer_assignment"], role="hero")
                    item["writer_fixed_source"] = draft
                    item["status"] = "complete"
                except Exception as e:
                    item["status"] = ("writer_failed" if "editor_plan" in item
                                      else "editor_failed")
                    item["error"] = type(e).__name__ + ": " + str(e)[:250]
                finally:
                    # The actual TCT copy-desk detector is read-only. Never
                    # monkeypatch, relax or bypass it to manufacture a pass.
                    detector = getattr(generate, "_copydesk_text_issues", None)
                    item["writer_attempts"] = copydesk_attempt_diagnostics(
                        getattr(adapter, "attempts", []), detector)
                    if item["status"] == "writer_failed":
                        item["rejected_writer_attempts_captured"] = bool(
                            item["writer_attempts"])
                saved(output / "results.json", completed + [row])
                saved(output / "usage.json", {
                    "estimated_usd": round(budget.estimated_usd, 6),
                    "calls": budget.calls, "budget_guard_usd": ceiling})
            completed.append(row)
    finally:
        saved(output / "answer-key.json", key)
        saved(output / "usage.json", {
            "estimated_usd": round(budget.estimated_usd, 6),
            "calls": budget.calls, "budget_guard_usd": ceiling})
        saved(output / "results.json", completed)
        summary = recover_existing_results(output)
    if not summary["complete_writing_and_editor_pairs"]:
        raise RuntimeError("No complete paired writing comparison. Review results and "
                           "summary artifacts; do not score missing writer outputs.")
    print("Production-prompt shadow:", summary["categories_attempted"],
          "categories,", summary["complete_writing_and_editor_pairs"],
          "complete writing pairs,", summary["complete_assignment_editor_pairs"],
          "assignment editor pairs; status", summary["result"],
          "; estimated USD", round(budget.estimated_usd, 6))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="data/assignment-editor-shadow-report.json")
    parser.add_argument("--output", default="editorial-shadow-output")
    parser.add_argument("--history", type=int, default=100)
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--categories", type=int, default=2)
    parser.add_argument("--max-cost", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recover-existing", action="store_true",
                        help="Recreate review/summary from previous results without API calls")
    args = parser.parse_args()
    if args.recover_existing:
        summary = recover_existing_results(Path(args.output))
        print("Recovered offline shadow review:", summary["result"],
              summary["complete_writing_and_editor_pairs"], "complete pairs; no API calls")
        return
    if not 1 <= args.categories <= 3 or not 10 <= args.history <= 160:
        parser.error("categories must be 1-3 and history 10-160")
    if not 1 <= args.max_age_days <= 14 or not 1 <= args.max_cost <= 50:
        parser.error("source age 1-14 days and budget $1-$50")
    # This first limited shadow cannot consume an accidental $12 workflow default.
    # An estimated guard is not a provider-side hard cap.
    effective_max_cost = min(args.max_cost, 2.0)
    output = Path(args.output)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    cutoff = utc(report["generated_at"])
    allowed = {
        urlkey(row.get("source_url"))
        for cat in report.get("categories") or []
        for row in cat.get("source_pool") or []
        if isinstance(row, dict) and urlkey(row.get("source_url"))
    }
    evidence, snapshots = frozen_evidence(
        allowed_urls=allowed, cutoff=cutoff,
        historic_days=args.history, max_age_days=args.max_age_days)
    cases, diagnostics = prepare_cases(report, evidence, limit=args.categories)
    saved(output / "coverage.json", {
        "snapshot_generated_at": report["generated_at"],
        "source_urls_requested": len(allowed), "source_urls_matched": len(evidence),
        "snapshots_inspected": snapshots,
        "selected_categories": [case["key"] for case in cases],
        "category_diagnostics": diagnostics,
        "limitations": ["reconstructed_source_text_not_verbatim_live_packet",
                        "missing_historical_canonical_context",
                        "no_identity_update_or_final_publication_pipeline"],
    })
    saved(output / "packets.json", cases)
    if not cases:
        raise RuntimeError("No complete original production-category source sets recoverable; "
                           "coverage.json has missing URL diagnostics. No fabricated fallback.")
    if args.dry_run:
        print("Production-prompt shadow dry run: prepared", len(cases),
              "complete-category historical packet(s); no API calls")
        return
    if not os.getenv("ANTHROPIC_API_KEY") or not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Both provider secrets required for non-dry run")
    produce(cases, effective_max_cost, args.seed, output)


if __name__ == "__main__":
    main()
