#!/usr/bin/env python3
"""Fix timing of TCT deleted-identity replay markers. No network or deployment.
Run at the root of the `tc-today` repository after pulling latest main.
Only modifies supabase/functions/delete-account/index.ts.
"""
from pathlib import Path
import difflib
import sys

path = Path('supabase/functions/delete-account/index.ts')
if not path.is_file():
    raise SystemExit(f'Missing {path}. Run from tc-today repository root.')
source = path.read_text(encoding='utf-8')

old_marker = '''    // Persist irreversible digests BEFORE Stripe calls or Auth deletion. This
    // prevents delayed checkout-complete/webhook events resurrecting the account.
    // No email, customer ID, or user UUID is stored in plaintext here.
    try {
      const identifiers = [await deletedIdentifierHash('user', userId),
        ...(await Promise.all(customers.map((id) => deletedIdentifierHash('customer', id))))]
      const { error: markerError } = await admin.from('membership_deleted_identifiers')
        .upsert(identifiers.map((identifier_hash) => ({ identifier_hash })), { onConflict: 'identifier_hash', ignoreDuplicates: true })
      if (markerError) throw markerError
    } catch (error) {
      console.error('delete-account could not persist replay protection', error)
      return Response.json({ error: 'Could not safely start deletion. No account data was deleted.' }, { status: 503 })
    }

'''
new_marker = '''    // Stripe cancellation and final renewal verification must succeed BEFORE
    // writing deletion replay markers. A failed billing lookup must not mark an
    // account that still exists as deleted (and block its webhook updates).
    // These digests are still persisted BEFORE Auth deletion so delayed events
    // cannot resurrect an identity after its account is removed.
    // No email, customer ID, or user UUID is stored in plaintext here.
    try {
      const identifiers = [await deletedIdentifierHash('user', userId),
        ...(await Promise.all(customers.map((id) => deletedIdentifierHash('customer', id))))]
      const { error: markerError } = await admin.from('membership_deleted_identifiers')
        .upsert(identifiers.map((identifier_hash) => ({ identifier_hash })), { onConflict: 'identifier_hash', ignoreDuplicates: true })
      if (markerError) throw markerError
    } catch (error) {
      console.error('delete-account could not persist replay protection', error)
      return Response.json({ error: 'Billing was verified, but account deletion could not safely finish. Please retry or contact support.' }, { status: 503 })
    }

'''
anchor = '''    try {
      const { error: deleteError } = await admin.auth.admin.deleteUser(userId)
'''

if new_marker in source and old_marker not in source:
    print('Already fixed: marker is after Stripe verification. No changes written.')
    sys.exit(0)
if source.count(old_marker) != 1 or source.count(anchor) != 1:
    raise SystemExit('Source mismatch: delete-account differs from reviewed version. No changes written; send current file.')
if source.index(old_marker) > source.index(anchor):
    raise SystemExit('Unexpected ordering. No changes written.')
patched = source.replace(old_marker, '', 1)
patched = patched.replace(anchor, new_marker + anchor, 1)
stripe_verification = '''      console.error('delete-account Stripe cancellation incomplete', error)'''
if not (patched.index(stripe_verification) < patched.index(new_marker) < patched.index(anchor)):
    raise SystemExit('Unsafe ordering detected. No changes written.')
if patched.count("await admin.auth.admin.deleteUser(userId)") != 1:
    raise SystemExit('Unexpected account-delete call count. No changes written.')
path.write_text(patched, encoding='utf-8')
print('Applied marker-order fix to supabase/functions/delete-account/index.ts only.')
print('Next: review diff, commit and push, run Deploy TCT Membership Backend manually, verify deployment.')
