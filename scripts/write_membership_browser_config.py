#!/usr/bin/env python3
"""Write browser-safe Supabase membership configuration.

Privileged credentials are never written. When membership UI is enabled, a
missing public URL/key is a deployment error rather than a silently broken page.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "membership-config.js"
SUBSCRIBE = ROOT / "subscribe.html"


def _enabled() -> bool:
    return os.getenv("TCT_MEMBERSHIP_UI_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    url = os.getenv("TCT_SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("TCT_SUPABASE_PUBLISHABLE_KEY", "").strip()
    ui_enabled = _enabled()
    payment_mode = os.getenv("TCT_STRIPE_MODE", "test").strip().lower() or "test"
    if payment_mode not in {"test", "live"}:
        raise RuntimeError("TCT_STRIPE_MODE must be either test or live")

    lowered = key.lower()
    if key and not key.startswith("sb_publishable_"):
        raise RuntimeError("TCT_SUPABASE_PUBLISHABLE_KEY must be a browser-safe sb_publishable_ key")
    if lowered.startswith("sb_secret_") or "service_role" in lowered:
        raise RuntimeError("Refusing to publish a privileged Supabase key")
    if ui_enabled and (not url or not key):
        raise RuntimeError("Membership UI cannot be enabled without browser-safe Supabase configuration")
    if ui_enabled and payment_mode != "live":
        raise RuntimeError("Membership UI cannot be enabled until TCT_STRIPE_MODE=live")

    payload = {
        "supabaseUrl": url,
        "supabasePublishableKey": key,
        "uiEnabled": ui_enabled,
        "paymentMode": payment_mode,
        "sandbox": payment_mode == "test",
    }
    OUT.write_text(
        "window.TCT_MEMBERSHIP_CONFIG = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    if SUBSCRIBE.exists():
        text = SUBSCRIBE.read_text(encoding="utf-8")
        robots = "index,follow" if ui_enabled else "noindex,nofollow,noarchive"
        text = re.sub(
            r'(<meta\s+id="membership-robots"\s+name="robots"\s+content=")[^"]*(">)',
            rf'\g<1>{robots}\g<2>',
            text,
            count=1,
            flags=re.I,
        )
        SUBSCRIBE.write_text(text, encoding="utf-8")

    print(
        f"Membership browser config written: url={'set' if url else 'missing'}, "
        f"key={'set' if key else 'missing'}, ui={'enabled' if ui_enabled else 'dark'}, "
        f"stripe={payment_mode}"
    )


if __name__ == "__main__":
    main()
