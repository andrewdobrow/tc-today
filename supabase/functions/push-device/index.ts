import { createClient } from 'npm:@supabase/supabase-js@^2'

// Public gateway: non-subscribers can opt into news. Each installation must
// prove possession of an independent random 256-bit secret to update its row.
// The service-role credential never leaves Supabase and the table has no
// anon/authenticated RLS policies.
const url = Deno.env.get('SUPABASE_URL') ?? ''
const serviceRole = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const supabase = url && serviceRole ? createClient(url, serviceRole, {
  auth: { autoRefreshToken: false, persistSession: false },
}) : null

type Preferences = {
  martin: boolean
  st_lucie: boolean
  indian_river: boolean
  breaking: boolean
  digest: boolean
}

function json(body: Record<string, unknown>, status = 200): Response {
  return Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } })
}

function hexSha256(value: string): Promise<string> {
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
    .then(bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join(''))
}

// Constant-time comparison avoids leaking whether a valid installation secret
// matched a known UUID through an early-exit string comparison.
function sameHash(a: string, b: string): boolean {
  if (a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i)
  return diff === 0
}

const uuidRe = /^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i
const tokenRe = /^(?:[a-f0-9]{2}){16,256}$/
const secretRe = /^[a-f0-9]{64}$/
const allowedPref = ['martin', 'st_lucie', 'indian_river', 'breaking', 'digest'] as const

function readPreferences(value: unknown): Preferences | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const input = value as Record<string, unknown>
  if (Object.keys(input).some(key => !allowedPref.includes(key as typeof allowedPref[number]))) return null
  if (allowedPref.some(key => typeof input[key] !== 'boolean')) return null
  return {
    martin: input.martin as boolean,
    st_lucie: input.st_lucie as boolean,
    indian_river: input.indian_river as boolean,
    breaking: input.breaking as boolean,
    // Morning Brief is explicitly unavailable in the first release.
    digest: false,
  }
}

Deno.serve(async req => {
  if (req.method !== 'POST') return json({ error: 'Method not allowed' }, 405)
  if (!supabase) return json({ error: 'Push enrollment is not configured' }, 503)

  // Bound memory use even for clients that omit Content-Length.
  if (Number(req.headers.get('content-length') ?? 0) > 4096) return json({ error: 'Request too large' }, 413)
  let input: Record<string, unknown>
  try {
    const text = await req.text()
    if (text.length > 4096) return json({ error: 'Request too large' }, 413)
    const parsed: unknown = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw Error('invalid')
    input = parsed as Record<string, unknown>
  } catch { return json({ error: 'Invalid JSON request' }, 400) }

  const action = input.action
  const id = input.installation_id
  const secret = input.installation_secret
  if ((action !== 'register' && action !== 'disable') ||
      typeof id !== 'string' || !uuidRe.test(id) ||
      typeof secret !== 'string' || !secretRe.test(secret)) {
    return json({ error: 'Invalid installation identity or action' }, 400)
  }

  let token: string | null = null
  let environment = 'production'
  let prefs: Preferences | null = null
  if (action === 'register') {
    if (typeof input.apns_token !== 'string' || !tokenRe.test(input.apns_token) ||
        (input.environment !== 'production' && input.environment !== 'sandbox')) {
      return json({ error: 'Invalid APNs token or environment' }, 400)
    }
    token = input.apns_token
    environment = input.environment
    prefs = readPreferences(input.preferences)
    if (!prefs) return json({ error: 'Invalid news alert preferences' }, 400)
  }

  const digest = await hexSha256(secret)
  const { data: existing, error: lookupError } = await supabase.from('ios_push_devices')
    .select('installation_id,registration_secret_hash').eq('installation_id', id).maybeSingle()
  if (lookupError) {
    console.error('push-device registry lookup failed', lookupError.code)
    return json({ error: 'Could not check enrollment' }, 503)
  }
  if (existing && !sameHash(existing.registration_secret_hash, digest)) {
    return json({ error: 'Installation credentials not recognized' }, 403)
  }
  if (!existing && action === 'disable') return json({ enrolled: false })

  const now = new Date().toISOString()
  if (action === 'disable') {
    const { error } = await supabase.from('ios_push_devices')
      .update({ enabled: false, apns_token: null, updated_at: now, last_seen_at: now })
      .eq('installation_id', id).eq('registration_secret_hash', digest)
    if (error) { console.error('push-device disable failed', error.code); return json({ error: 'Could not disable alerts' }, 503) }
    return json({ enrolled: false })
  }

  const values = {
    apns_token: token,
    environment,
    enabled: !!(prefs!.breaking || prefs!.martin || prefs!.st_lucie || prefs!.indian_river),
    martin: prefs!.martin,
    st_lucie: prefs!.st_lucie,
    indian_river: prefs!.indian_river,
    breaking: prefs!.breaking,
    digest: false,
    updated_at: now,
    last_seen_at: now,
  }
  // Do not upsert: an attacker must never replace someone else's secret when
  // racing an unknown installation ID. New IDs can only be created once.
  const result = existing
    ? await supabase.from('ios_push_devices').update(values)
      .eq('installation_id', id).eq('registration_secret_hash', digest)
    : await supabase.from('ios_push_devices').insert({
        installation_id: id,
        registration_secret_hash: digest,
        ...values,
      })
  if (result.error) {
    console.error('push-device enrollment failed', result.error.code)
    return json({ error: 'Could not save push preferences' }, 503)
  }
  return json({ enrolled: values.enabled })
})
