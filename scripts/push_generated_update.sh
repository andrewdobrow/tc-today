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
    sitemap.xml|archive.json|rss.xml|index.html|events.html|search.html|subscribe.html|account.html|weather.html)
      return 0
      ;;
    articles/*|missing-persons/*|martin/*|st-lucie/*|indian-river/*|port-st-lucie/*|jensen-beach/*|stuart/*|vero-beach/*|fellsmere/*|sebastian/*|partners/*)
      return 0
      ;;
    data/editorial_story_registry.json|data/editorial_story_registry.preflight.json|data/editorial_story_history.jsonl|data/editorial_story_history/*|data/editorial_state.json|data/editorial_audit.jsonl|data/generation-cache.json)
      return 0
      ;;
    data/*-report.json|data/*_report.json|data/story-index.json|data/*identity*.json|data/*ranking*.json|data/*observability*.json)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_generated_conflicts() {
  local conflicts unsafe path
  conflicts="$(git diff --name-only --diff-filter=U)"
  if [[ -z "$conflicts" ]]; then
    return 1
  fi

  unsafe=""
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    if is_generated_conflict "$path"; then
      echo "Auto-resolving generated rebase conflict with current run output: $path"
      # During rebase, --theirs is the commit being replayed (this bot run), while
      # --ours is the newly fetched origin/main.
      git checkout --theirs -- "$path"
      git add -- "$path"
    else
      unsafe+="${path}"$'\n'
    fi
  done <<< "$conflicts"

  if [[ -n "$unsafe" ]]; then
    echo "Unsafe source/config conflict(s) require human review:" >&2
    printf '%s' "$unsafe" >&2
    return 2
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
