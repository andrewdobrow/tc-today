# TCT iPhone push sending v0.9 — controlled rollout and full checklist

This overlay applies ONLY to the **Treasure Coast Today WEBSITE repository**. It does not change the iOS repo, website publishing, subscriptions, Stripe, or any production editorial workflows. It is additive to the already-deployed push-device v0.7 backend. **Do not install over a different Supabase project.**

## Status and limitations

- This introduces a **manual-only, separate** push-dispatch Edge Function. It NEVER watches new articles or sends on a schedule.
- Default secret `TCT_PUSH_SENDING_ENABLED=false` causes every live send to be rejected; preview remains possible.
- A manually run GitHub Actions `TCT iOS News Alert (manual preview or send)` workflow accepts audience, article slug, title and body.
- The manual workflow is NOT a bulk sender. It refuses an audience over 50 enrolled production tokens; it never knowingly sends a subset instead. **Before public rollout with more than 50 devices, build an asynchronous queue, durable per-device delivery state, rates, and retries.**
- A database unique key prevents a given article slug from being dispatched twice, even to different audience categories. This is intentionally conservative: after partial send or network interruption, do NOT delete the ledger record or resend blindly.
- Apple APNs *acceptance* means APNs received the request, NOT that the user saw it. Real transport and phone delivery can't be verified before TestFlight can be installed.
- No private key, APNs token, or database service role credential is included in this overlay.

## Exact order of work

**1. Add overlay to the WEBSITE repository.** Unzip and upload the **contents** with their original relative paths; do not upload to `tct-ios`. Add the following *new* section (do not duplicate) to the EXISTING `supabase/config.toml` through GitHub's file editor:

```toml
# Manually approved notification dispatcher (validates its own admin key).
[functions.push-dispatch]
verify_jwt = false
```

The included `scripts/configure_ios_push_dispatch.ps1` performs that append if you have a local checkout, but you need not use it when editing via GitHub. Keep the existing `[functions.push-device]` and every other function section untouched. Commit to `main`.

**2. One-time new database table.** Open the *same TCT Supabase project* SQL Editor at
`https://supabase.com/dashboard/project/pbvhdbmgqvoumcytvwyq/sql`.
Click **New query**, paste the ENTIRE `supabase/migrations/202610120001_ios_push_dispatch_ledger.sql` from the overlay, click **Run**, and confirm `Success`. This creates `public.ios_push_dispatches`. It adds no triggers.

**3. Supabase Edge Function Secrets — store Apple credentials there, NEVER in GitHub.** Open:
`https://supabase.com/dashboard/project/pbvhdbmgqvoumcytvwyq/settings/functions` (or open **Edge Functions → Secrets** from the dashboard navigation).
Create these **five exact names**. Supabase permits multiple names and stores them on the server. Do not alter any existing Stripe / membership secrets:

| Secret name | Value |
|---|---|
| `TCT_APNS_KEY_ID` | Your Apple APNs Key ID (10 alphanumeric characters) |
| `TCT_APNS_TEAM_ID` | Your Apple Developer Team ID (10 alphanumeric characters) |
| `TCT_APNS_P8_BASE64` | The entire `.p8` file converted to a single-line Base64 string using the clipboard helper below |
| `TCT_PUSH_DISPATCH_KEY` | Fresh, unique 64-character lowercase hex administrator key generated below |
| `TCT_PUSH_SENDING_ENABLED` | `false` (literally the word false, no quotes) |

Create them before deploying and do NOT set `TCT_PUSH_SENDING_ENABLED=true` until an actual physical-device test has passed. The base64 string is still **sensitive** because it encodes the private Apple key. It belongs only in Supabase's secrets manager.

### Windows helper — encode your `.p8` to the clipboard without uploading the file

Open **Windows PowerShell** and paste the whole block. It opens a file selection window so you can choose the exact Apple APNs `.p8` file. The result goes **directly to your clipboard** and is not printed or saved to a separate file:

```powershell
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = "Select your TCT APNs .p8 private key"
$dialog.Filter = "Apple push key (*.p8)|*.p8"
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($dialog.FileName)) | Set-Clipboard
    Write-Host "Encoded key copied. Paste ONLY into the Supabase secret TCT_APNS_P8_BASE64."
}
```

Paste it into the Supabase secret `TCT_APNS_P8_BASE64`. Never paste it in ChatGPT, a GitHub file, or an Actions log.

### Windows helper — generate separate dispatcher key

Paste this separate block into PowerShell. It generates a random 256-bit key and copies it to the clipboard:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$key = -join ($bytes | ForEach-Object { $_.ToString("x2") })
Set-Clipboard -Value $key
Write-Host "Push dispatch key copied. Paste it into Supabase and GitHub Secrets (NOT source files)."
```

Paste exactly the **same generated value** into the Supabase `TCT_PUSH_DISPATCH_KEY` secret **and** GitHub website repository → Settings → Secrets and variables → Actions → Repository secrets → New repository secret named `TCT_PUSH_DISPATCH_KEY`. Don't generate a separate key for GitHub. Afterward clear your clipboard if you wish.

**4. Deploy this sender ALONE.** In the WEBSITE repository → GitHub Actions, run **Deploy TCT iOS Push Sender (manual)** on main. Confirm green. This workflow deploys only `push-dispatch` and leaves all existing functions alone. The `SUPABASE_PROJECT_REF` variable and `SUPABASE_ACCESS_TOKEN` secret were already proven to work when v0.7 was green; no new Supabase access token is needed.

**5. Safe preflight.** In WEBSITE repository Actions, run `TCT iOS News Alert (manual preview or send)` with:
- `action`: **preview** (never send for the initial check)
- `audience`: choose `breaking`, `martin`, `st_lucie`, or `indian_river`
- `slug`: choose a REAL published article URL's filename, but remove `/articles/` and `.html` (example `2026-10-11-stuart-city-council-review`, **only if that exact article exists**)
- `title`: a truthful headline, up to 100 characters
- `body`: a short teaser, up to 180 characters
- `confirm`: leave blank

The workflow checks the live article via a non-redirecting HEAD request, verifies the dispatch hasn't already happened, and returns `eligible_devices`, `sending_enabled:false`, `already_dispatched:false`. With TestFlight still blocked and nobody enrolled, **0 eligible devices is expected**. Preview does not write ledger records or send APNs requests.

**6. Physical-device acceptance before enabling live sending.** First resolve the existing TestFlight installation issue. On a physical iPhone, install TCT, accept first-launch alerts, confirm on the Account screen that server enrollment succeeded, verify that a matching production APNs device row exists via an admin-only table count, and re-run preview until `eligible_devices` is 1. Test a separate new article slug (never sent before), enable the live-send flag ONLY after confirming the Apple APNs key's topic/environment and authenticating the sender. Use `action=send`, `confirm=SEND`, and a targeted audience containing only your opted-in test phone. Verify Apple acceptance and iPhone notification tap opens the same article. Then disable live-send again pending a production readiness review.

Do NOT run a production-wide test or turn on sending simply because code compiled. TestFlight builds use production APNs; sandbox-mode tokens are deliberately excluded here.

## Security and operational invariants

- Admin dispatch key is 256-bit random, required for every HTTP request, even preview. Supabase's public gateway skips JWT verification for this function **only** because it checks the separate server-side admin secret. Do not use the app's publishable key for this action.
- `TCT_APNS_P8_BASE64` is stored in **Supabase secrets only**, never GitHub; GitHub only sees a different administrator dispatch key.
- Only production registered tokens that have opted into the selected audience are queried; anonymous users may subscribe to *alerts*, but no subscription purchase is required.
- A SQL ledger locks a story by its canonical slug, preventing accidental repeat pushes across audience groups. No publication automation.
- One live article must exist with an identical URL; redirects are not accepted.
- Only confirmed APNs `410 Unregistered` automatically removes the affected token. `BadDeviceToken` and `DeviceTokenNotForTopic` are reported to the operator without unregistering readers, since a wrong sending environment or key could be responsible.
- Safe preview + disabled live sending is the shipping default. A cap of 50 devices is a hard safety stop; do not quietly raise it without designing durable batch jobs and per-device state.
- Apple needs HTTP/2/TLS for APNs. This exact outbound transport must be verified on the hosted runtime against APNs before calling delivery complete.

## Reference docs

Apple APNs provider JWT and authentication: https://developer.apple.com/documentation/usernotifications/establishing-a-token-based-connection-to-apns
Apple APNs request and topic requirements: https://developer.apple.com/documentation/usernotifications/sending-notification-requests-to-apns
Supabase server secrets: https://supabase.com/docs/guides/functions/secrets
