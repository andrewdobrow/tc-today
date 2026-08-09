#!/usr/bin/env python3
"""Write the browser-safe Supabase config used only by the membership test page."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "membership-config.js"


def main() -> None:
    url = os.getenv("TCT_SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("TCT_SUPABASE_PUBLISHABLE_KEY", "").strip()

    # Fail closed if a privileged key is accidentally put in the browser variable.
    lowered = key.lower()
    if key and not key.startswith("sb_publishable_"):
        raise RuntimeError(
            "TCT_SUPABASE_PUBLISHABLE_KEY must be a browser-safe sb_publishable_ key"
        )
    if lowered.startswith("sb_secret_") or "service_role" in lowered:
        raise RuntimeError("Refusing to publish a privileged Supabase key")

    payload = {
        "supabaseUrl": url,
        "supabasePublishableKey": key,
        "sandbox": True,
    }
    OUT.write_text(
        "window.TCT_MEMBERSHIP_CONFIG = " + json.dumps(payload, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Membership browser config written: url={'set' if url else 'missing'}, key={'set' if key else 'missing'}")


if __name__ == "__main__":
    main()
