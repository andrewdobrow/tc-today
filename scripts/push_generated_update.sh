#!/usr/bin/env bash
set -euo pipefail

# Commit generated site output and safely rebase it over a main branch that may
# have moved during a long newsroom run.  Generated-file conflicts are resolved
# in favor of the just-produced output; source/config conflicts still fail closed.

is_generated_conflict() {
  local path="$1"
  case "$path" in
    data/custom_articles.json|data/manual_events.json)
      return 1
      ;;
    sitemap.xml|feed.xml|archive.html|archive.json|rss.xml|data.json|story-registry.json|index.html|events.html|search.html|subscribe.html|account.html|weather.html)
      return 0
      ;;
    articles/*|missing-persons/*|martin/*|st-lucie/*|indian-river/*|port-st-lucie/*|jensen-beach/*|stuart/*|vero-beach/*|fellsmere/*|sebastian/*|partners/*)
      return 0
      ;;
    # Independently refreshed calendar artifacts are generated, never source
    # configuration. A concurrent Events job can rewrite these while the longer
    # newsroom build is in flight. Preserve the newer calendar set on rebase.
    events/*|data/events-source-cache.json|data/events-retention.json)
      return 0
      ;;
    data/editorial_story_registry.json|data/editorial_story_registry.preflight.json|data/editorial_story_history.jsonl|data/editorial_story_history/*|data/editorial_state.json|data/editorial_audit.jsonl|data/generation-cache.json)
      return 0
      ;;
    # Generated editorial state and feeds. Explicit entries are intentional:
    # data/ also contains editor-maintained corrections and configuration that
    # must NEVER be silently replaced by a long-running automation.
    data/stories.json|data/story-registry.json|data/story-processed-articles.json|data/story-shadow-log.json|data/top-news-app-feed.json|data/trusted-source-recovery.json|data/canonical-cleanup-history.jsonl|data/canonical-publication-ledger.json|data/canonical-redirects.json|data/editorial-image-rotation.json|data/editorial_activation.json|data/editorial_activation_history.jsonl|data/editorial_observability.json|data/events.json|data/events-source-status.json)
      return 0
      ;;
    # Read-only post-generation diagnostics/validation artifacts. The Update
    # job writes these every run, so concurrent runs/human pushes can conflict.
    data/*-report.json|data/*_report.json|data/story-index.json|data/*identity*.json|data/*ranking*.json|data/*observability*.json|data/*-contract.json|data/*-dedup.json|data/*-dedupe.json|data/*-repair.json|data/*-reconciliation.json|data/*-integrity.json|data/*-invariant.json|data/*-purge.json|data/*-suppression.json|data/*-authority.json|data/*-gate.json|data/*-selection.json|data/*-audit.json|data/*-rebind.json|data/*-migration.json|data/*-review.md)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# An independently completed calendar refresh owns these outputs. During
# rebase --ours is newest origin/main and --theirs is the older newsroom run.
# Keep the current calendar bundle together, not a mix of stale cache and
# newer event pages.
is_concurrent_events_output() {
  case "$1" in
    events.html|events/*|data/events.json|data/events-source-cache.json|data/events-source-status.json|data/events-retention.json)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

reconcile_event_sitemap_after_rebase() {
  # The newsroom sitemap includes the newly generated articles. After
  # preserving the newer calendar, rewrite only its event URLs against that
  # calendar; do not lose new news URLs or publish stale/deleted event links.
  python - <<'PY'
from scripts.build_audience_features import update_sitemap, validate_event_detail_lifecycle

print("Reconciled event URLs into newsroom sitemap:", update_sitemap())
print("Event lifecycle validated after concurrent refresh:", validate_event_detail_lifecycle())
PY
  git add -- sitemap.xml
}

resolve_generated_conflicts() {
  local conflicts unsafe path event_conflicts=0
  conflicts="$(git diff --name-only --diff-filter=U)"
  if [[ -z "$conflicts" ]]; then
    return 1
  fi

  # Validate the entire conflict set *before* staging any resolution.
  # Hand-edited corrections and source/config changes must fail closed.
  unsafe=""
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    if ! is_generated_conflict "$path"; then
      unsafe+="${path}"$'\n'
    fi
  done <<< "$conflicts"

  if [[ -n "$unsafe" ]]; then
    echo "Unsafe source/config rebase conflict(s) require human review; generated changes NOT pushed:" >&2
    printf '%s' "$unsafe" >&2
    return 2
  fi

  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    # Rebase semantics: --ours is up-to-date origin/main; --theirs is this
    # newsroom run. Prefer the newer Events refresh for calendar-owned files.
    # All other generated outputs keep the newsroom run's freshly written news.
    local stage=3
    if is_concurrent_events_output "$path"; then
      stage=2
      event_conflicts=1
      echo "Keeping newer event-refresh output from main: $path"
    else
      echo "Auto-resolving generated rebase conflict with current run output: $path"
    fi
    # Stage 2 or 3 can be absent when the selected side deleted the file.
    if git ls-files -u -- "$path" | awk -v stage="$stage" '$3 == stage { found = 1 } END { exit !found }'; then
      if [[ "$stage" -eq 2 ]]; then
        git checkout --ours -- "$path"
      else
        git checkout --theirs -- "$path"
      fi
      git add -- "$path"
    else
      git rm -f -- "$path"
    fi
  done <<< "$conflicts"
  if [[ "$event_conflicts" -eq 1 ]]; then
    reconcile_event_sitemap_after_rebase
  fi
  return 0
}

rebase_onto_latest_main() {
  git fetch origin main
  if git merge-base --is-ancestor origin/main HEAD; then
    return 0
  fi

  if git rebase origin/main; then
    return 0
  fi

  local status=0
  resolve_generated_conflicts || status=$?
  if [[ "$status" -eq 2 ]]; then
    git rebase --abort || true
    return 2
  elif [[ "$status" -ne 0 ]]; then
    git rebase --abort || true
    return 1
  fi

  # A bot run creates one commit, but keep this bounded loop defensive in case a
  # future workflow adds another generated commit before push.
  for _ in 1 2 3; do
    if GIT_EDITOR=true git rebase --continue; then
      return 0
    fi
    status=0
    resolve_generated_conflicts || status=$?
    if [[ "$status" -eq 2 ]]; then
      git rebase --abort || true
      return 2
    elif [[ "$status" -ne 0 ]]; then
      git rebase --abort || true
      return 1
    fi
  done

  git rebase --abort || true
  echo "Generated update rebase did not converge after bounded retries." >&2
  return 1
}

git config user.name "TCT Bot"
git config user.email "bot@treasurecoast.today"
git add -A

if git diff --staged --quiet; then
  echo "No generated changes to commit."
  exit 0
fi

git commit -m "Update: $(date -u '+%b %d %Y %H:%M UTC')"

# A human push can move main while a 20-40 minute generation job is running even
# though scheduled TCT workflows share a concurrency lock. Retry a bounded number
# of times instead of throwing away the completed run on a generated-file conflict.
for attempt in 1 2 3; do
  echo "Push attempt ${attempt}/3: rebasing generated update onto latest main"
  rebase_onto_latest_main
  if git push origin HEAD:main; then
    exit 0
  fi
  echo "Remote moved again before push; retrying with latest main." >&2
  sleep $((attempt * 2))
done

echo "Could not push generated update after 3 bounded retries." >&2
exit 1
