from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_inactive_subscription_status_is_returned_without_entitlement():
    source = (ROOT / "supabase/functions/membership-status/index.ts").read_text()
    assert "subscription_status: latestSubscriptionStatus || null" in source
    assert "active?.status || subscriptions?.[0]?.status" in source
    assert "const entitled = isAdmin || Boolean(active)" in source

def test_subscription_ui_distinguishes_payment_problem_from_signin():
    source = (ROOT / "membership.js").read_text()
    assert "['past_due', 'unpaid', 'incomplete']" in source
    assert "you are signed in" in source.lower()
    assert "data-inactive-membership-notice" in source
    assert "Go to my account" in source
    assert "We could not verify your membership" in source
    assert "tct-member-authenticated" in source
