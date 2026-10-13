# TCT APNs credential diagnostics — operator guide

This overlay applies to the **TCT website repository** (`tc-today`), not `tct-ios`.
It changes only the `push-dispatch` Edge Function, its existing manual GitHub Action,
and the accompanying Node regression test. Do **not** modify the Stripe, iOS,
news publishing, or Supabase database configuration for this diagnostic.

## Apply / deploy

1. Copy the overlay files into your **website** repository at their supplied paths. Review changes if `main` has advanced; do not discard any more recent `push-dispatch` edits.
2. Commit and push to `main`.
3. Run **Deploy TCT iOS Push Sender (manual)** in the website repository's GitHub Actions. This is a separate workflow and must run before the new behavior is available in Supabase. Normal website publishing will not deploy Edge Function changes.
4. In the existing **TCT iOS News Alert (manual preview or send)** workflow select `action = diagnose`. Use the same syntactically valid article slug, title, body, and audience as before; `confirm` can be empty. This mode **does not check the article, select recipients, call Apple, or write to the dispatch ledger**, and does not require `TCT_PUSH_SENDING_ENABLED=true`.
5. Look at the JSON printed in the workflow run. Share **only** `diagnostic_code`, if present. Never share secrets or `.p8` key contents.

## Example safe results

On success (local signing only):

```json
{"diagnostic":true,"apns_signing":"ok","sent":false,
 "note":"Local APNs JWT signing succeeded. Apple key/account matching and network delivery are not tested."}
```

On an invalid outer Base64 value, for example:

```json
{"diagnostic":true,"apns_signing":"failed","diagnostic_code":"APNS_P8_BASE64_INVALID","sent":false}
```

The failing diagnose workflow is expected to end **red with HTTP 503**; its JSON still identifies the failing stage. A normal `send` action also includes the same `diagnostic_code` if loading fails before reserving the article.

## Diagnostic codes

| Code | Meaning |
| --- | --- |
| `APNS_KEY_ID_MISSING` / `APNS_KEY_ID_FORMAT` | Missing or malformed 10-character APNs Key ID |
| `APNS_TEAM_ID_MISSING` / `APNS_TEAM_ID_FORMAT` | Missing or malformed 10-character Apple Team ID |
| `APNS_P8_MISSING` | The Base64-encoded `.p8` secret is empty |
| `APNS_P8_BASE64_INVALID` | Secret is not valid Base64 of the full PEM file |
| `APNS_P8_PEM_INVALID` | Decoded secret is not a PEM `PRIVATE KEY` block |
| `APNS_P8_BODY_INVALID` | The key's interior Base64 encoding is invalid |
| `APNS_P8_IMPORT_FAILED` | The key cannot be imported as an EC P-256 PKCS#8 signing key |
| `APNS_SIGN_FAILED` | WebCrypto failed while creating the local ES256 signature |
| `APNS_UNEXPECTED_ERROR` | Unexpected failure not classified above |

An `ok` result validates local JWT creation only. It **does not** verify that the Key ID matches the uploaded key, that Apple accepts this credential, or that the device will display a notification. Those checks still require a controlled send after the local configuration has passed.

## Safeguards

The endpoint is authenticated with the existing `TCT_PUSH_DISPATCH_KEY`. It never returns private key content, decoded key bytes, Key ID or Team ID values, APNs device tokens, or low-level crypto exception strings. The `diagnose` path has no external network calls or database writes, never sends an APNs notification, and does not consume an article's once-only send slot. Existing live-send switch, confirmation requirements, recipient filtering, and ledger logic remain unchanged.
