import { createClient } from 'npm:@supabase/supabase-js@^2'

// TCT iOS manual-only alert sender. Deliberately NOT connected to any article
// ingestion, publication, newsletter, or Stripe workflow.
// Only an administrator with a separate 256-bit dispatch secret can invoke it.
const URL_BASE = Deno.env.get('SUPABASE_URL') ?? ''
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const ADMIN_KEY = Deno.env.get('TCT_PUSH_DISPATCH_KEY') ?? ''
const LIVE_ENABLED = Deno.env.get('TCT_PUSH_SENDING_ENABLED') === 'true'
const db = URL_BASE && SERVICE_KEY ? createClient(URL_BASE, SERVICE_KEY, {
  auth: { autoRefreshToken: false, persistSession: false },
}) : null

const TOPIC = 'com.treasurecoast.today.ios'
const MAX_DEVICES = 50 // Deliberate early-release ceiling; batch sender needed beyond this.
const slugPattern = /^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$/
const allowedAudiences = ['breaking', 'martin', 'st_lucie', 'indian_river']
const tokenPattern = /^[0-9a-f]{32,512}$/

function respond(body, status = 200) {
  return Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } })
}
function equalSecret(a, b) {
  if (a.length !== b.length) return false
  let different = 0
  for (let i = 0; i < a.length; i++) different |= a.charCodeAt(i) ^ b.charCodeAt(i)
  return different === 0
}
function encoded(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
function textEncoded(value) { return encoded(new TextEncoder().encode(value)) }

async function sha256(value) {
  return encoded(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))
}

// Stable, non-sensitive error codes for operator-only diagnostics. Never
// surface a credential, PEM body, underlying crypto error, or Apple token.
function apnsConfigurationError(code) {
  const error = new Error('APNs credential check failed')
  error.diagnosticCode = code
  return error
}
function apnsDiagnosticCode(error) {
  const code = error?.diagnosticCode
  return typeof code === 'string' && /^APNS_[A-Z0-9_]+$/.test(code)
    ? code : 'APNS_UNEXPECTED_ERROR'
}
function strictBase64Decode(input, code) {
  const compact = input.replace(/\s/g, '')
  if (!compact || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(compact)) {
    throw apnsConfigurationError(code)
  }
  try { return atob(compact) }
  catch { throw apnsConfigurationError(code) }
}

async function makeAppleToken() {
  const keyID = Deno.env.get('TCT_APNS_KEY_ID') ?? ''
  const teamID = Deno.env.get('TCT_APNS_TEAM_ID') ?? ''
  const fileB64 = Deno.env.get('TCT_APNS_P8_BASE64') ?? ''
  if (!keyID) throw apnsConfigurationError('APNS_KEY_ID_MISSING')
  if (!/^[A-Z0-9]{10}$/.test(keyID)) throw apnsConfigurationError('APNS_KEY_ID_FORMAT')
  if (!teamID) throw apnsConfigurationError('APNS_TEAM_ID_MISSING')
  if (!/^[A-Z0-9]{10}$/.test(teamID)) throw apnsConfigurationError('APNS_TEAM_ID_FORMAT')
  if (!fileB64) throw apnsConfigurationError('APNS_P8_MISSING')

  const pem = strictBase64Decode(fileB64, 'APNS_P8_BASE64_INVALID')
  if (!/^\s*-----BEGIN PRIVATE KEY-----[\s\S]*-----END PRIVATE KEY-----\s*$/.test(pem)) {
    throw apnsConfigurationError('APNS_P8_PEM_INVALID')
  }
  const raw = pem.replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g, '')
  const der = strictBase64Decode(raw, 'APNS_P8_BODY_INVALID')
  const bytes = Uint8Array.from(der, char => char.charCodeAt(0))
  let key
  try {
    key = await crypto.subtle.importKey('pkcs8', bytes, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign'])
  } catch { throw apnsConfigurationError('APNS_P8_IMPORT_FAILED') }
  const header = textEncoded(JSON.stringify({ alg: 'ES256', kid: keyID }))
  const payload = textEncoded(JSON.stringify({ iss: teamID, iat: Math.floor(Date.now() / 1000) }))
  const content = `${header}.${payload}`
  let signature
  try {
    signature = await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, new TextEncoder().encode(content))
  } catch { throw apnsConfigurationError('APNS_SIGN_FAILED') }
  return `${content}.${encoded(signature)}`
}

async function articleExists(slug) {
  const url = `https://treasurecoast.today/articles/${slug}.html`
  try {
    const response = await fetch(url, { method: 'HEAD', redirect: 'manual', signal: AbortSignal.timeout(8000) })
    return response.status === 200 && response.url === url
  } catch { return false }
}

async function listRecipients(audience) {
  // One extra row to fail safely instead of silently sending to a subset.
  const { data, error } = await db.from('ios_push_devices')
    .select('installation_id,apns_token')
    .eq('enabled', true).eq('environment', 'production').eq(audience, true)
    .not('apns_token', 'is', null).range(0, MAX_DEVICES)
  if (error) throw Error('Could not retrieve opted-in devices')
  const devices = data ?? []
  if (devices.length > MAX_DEVICES) throw Error(`Over ${MAX_DEVICES} devices match; bulk sending is disabled until batching is built`)
  // iPhones can generate duplicate registration rows during a reinstall.
  const seen = new Set()
  return devices.filter(row => {
    const token = row.apns_token
    if (typeof token !== 'string' || !tokenPattern.test(token) || seen.has(token)) return false
    seen.add(token)
    return true
  })
}

async function sendToApple(row, jwt, message, collapseID) {
  try {
    const response = await fetch(`https://api.push.apple.com/3/device/${row.apns_token}`, {
      method: 'POST',
      headers: {
        authorization: `bearer ${jwt}`,
        'apns-topic': TOPIC,
        'apns-push-type': 'alert',
        'apns-priority': '10',
        'apns-collapse-id': collapseID,
        'content-type': 'application/json',
      },
      body: JSON.stringify(message),
      signal: AbortSignal.timeout(9000),
    })
    if (response.status === 200) return { ok: true, reason: 'Accepted' }
    let reason = 'APNs HTTP ' + response.status
    try {
      const reply = await response.json()
      if (typeof reply?.reason === 'string') reason = reply.reason
    } catch { /* No sensitive response body in logs */ }
    // APNs rejection for permanently invalid tokens: stop trying this exact token.
    // Only Apple's explicit Unregistered(410) clears an enrollment automatically.
    // BadDeviceToken and DeviceTokenNotForTopic may reflect a sender configuration
    // mistake, so an administrator must investigate before deleting tokens.
    if (response.status === 410 && reason === 'Unregistered') {
      await db.from('ios_push_devices').update({ enabled: false, apns_token: null, updated_at: new Date().toISOString() })
        .eq('installation_id', row.installation_id).eq('apns_token', row.apns_token)
    }
    return { ok: false, reason }
  } catch { return { ok: false, reason: 'Network or timeout error' } }
}

Deno.serve(async request => {
  if (request.method !== 'POST') return respond({ error: 'Method not allowed' }, 405)
  const supplied = request.headers.get('x-tct-push-dispatch-key') ?? ''
  if (!/^[0-9a-f]{64}$/.test(ADMIN_KEY) || !equalSecret(supplied, ADMIN_KEY)) {
    return respond({ error: 'Not authorized' }, 401)
  }
  if (!db) return respond({ error: 'Backend is not configured' }, 503)

  let input
  try {
    if (Number(request.headers.get('content-length') ?? '0') > 3000) throw Error('large')
    const raw = await request.text()
    if (raw.length > 3000) throw Error('large')
    input = JSON.parse(raw)
  } catch { return respond({ error: 'Invalid JSON input' }, 400) }
  // Authenticate first, then handle credential-only diagnostics before the
  // article, audience or message fields. Diagnostics intentionally require
  // only {action:"diagnose"}; they must not validate publication inputs.
  if (!input || typeof input !== 'object' || Array.isArray(input) ||
      !['preview', 'diagnose', 'send'].includes(input.action)) {
    return respond({ error: 'Invalid action. Use diagnose, preview, or send.' }, 400)
  }
  if (input.action === 'diagnose') {
    try {
      await makeAppleToken()
      return respond({ diagnostic: true, apns_signing: 'ok', sent: false,
        note: 'Local APNs JWT signing succeeded. Apple key/account matching and network delivery are not tested.' })
    } catch (error) {
      return respond({ diagnostic: true, apns_signing: 'failed',
        diagnostic_code: apnsDiagnosticCode(error), sent: false }, 503)
    }
  }

  // Only preview and send require live-story and message fields.
  // Return a field-specific safe error, never echo supplied content.
  if (typeof input.slug !== 'string' || input.slug.length > 180 || !slugPattern.test(input.slug)) {
    return respond({ error: 'Invalid story slug: use the article filename without .html.', field: 'slug' }, 400)
  }
  if (typeof input.audience !== 'string' || !allowedAudiences.includes(input.audience)) {
    return respond({ error: 'Invalid audience: choose breaking or a supported county.', field: 'audience' }, 400)
  }
  if (typeof input.title !== 'string' || !input.title.trim() || input.title.length > 100) {
    return respond({ error: 'Invalid notification title: enter 1–100 characters.', field: 'title' }, 400)
  }
  if (typeof input.body !== 'string' || !input.body.trim() || input.body.length > 180) {
    return respond({ error: 'Invalid notification body: enter 1–180 characters.', field: 'body' }, 400)
  }
  const { action, slug, audience } = input
  const title = input.title.trim()
  const body = input.body.trim()

  if (!(await articleExists(slug))) {
    return respond({ error: 'Story is not a live, non-redirecting TCT article. Check its URL before alerting readers.' }, 422)
  }
  const { data: prior, error: priorError } = await db.from('ios_push_dispatches')
    .select('slug,status').eq('slug', slug).maybeSingle()
  if (priorError) return respond({ error: 'Could not check dispatch history' }, 503)
  let recipients
  try { recipients = await listRecipients(audience) }
  catch (error) { return respond({ error: String(error?.message ?? 'Could not select recipients') }, 409) }

  if (action === 'preview') {
    return respond({ preview: true, audience, slug, eligible_devices: recipients.length,
      already_dispatched: !!prior, sending_enabled: LIVE_ENABLED,
      note: 'No notification has been sent and no dispatch was recorded.' })
  }
  if (!LIVE_ENABLED) return respond({ error: 'Live sending is OFF. Preview remains available.' }, 403)
  if (input.confirm !== 'SEND') return respond({ error: 'Explicit SEND confirmation is required.' }, 400)
  if (prior) return respond({ error: 'This article already has a dispatch. Duplicate send blocked.' }, 409)
  if (!recipients.length) return respond({ error: 'No enrolled production devices match this audience.' }, 409)

  // Validate APNs key BEFORE claiming the one-time story dispatch.
  let jwt
  try { jwt = await makeAppleToken() }
  catch (error) {
    return respond({ error: 'APNs provider credentials could not be loaded.',
      diagnostic_code: apnsDiagnosticCode(error) }, 503)
  }

  // Unique slug is a database-enforced lock across concurrent requests, including
  // calls for different audiences. We never auto-retry an uncertain delivery.
  const { error: reserveError } = await db.from('ios_push_dispatches').insert({
    slug, audience, title, body, status: 'reserved', attempted: 0, accepted: 0, rejected: 0,
  })
  if (reserveError) return respond({ error: 'Dispatch could not be reserved or this story was already sent.' },
    reserveError.code === '23505' ? 409 : 503)

  const message = { aps: { alert: { title, body }, sound: 'default' }, slug }
  const collapseID = (await sha256(slug)).slice(0, 40)
  let accepted = 0
  let rejected = 0
  const reasons = {}
  // A conservative concurrency limit; an edge-runtime interruption keeps the
  // story locked to prevent blind retries and duplicate reader notifications.
  for (let i = 0; i < recipients.length; i += 5) {
    const batch = await Promise.all(recipients.slice(i, i + 5)
      .map(row => sendToApple(row, jwt, message, collapseID)))
    for (const result of batch) {
      if (result.ok) accepted++
      else { rejected++; reasons[result.reason] = (reasons[result.reason] ?? 0) + 1 }
    }
  }
  const { error: saveError } = await db.from('ios_push_dispatches').update({
    status: rejected ? 'partial' : 'completed',
    attempted: accepted + rejected, accepted, rejected,
    finished_at: new Date().toISOString(),
  }).eq('slug', slug)
  if (saveError) console.error('push-dispatch ledger update failed', saveError.code)
  return respond({ sent: true, slug, audience, attempted: accepted + rejected,
    accepted_by_apns: accepted, rejected_by_apns: rejected, rejected_reasons: reasons,
    ledger_saved: !saveError,
    note: 'APNs acceptance does not guarantee display on the phone. Never rerun the same story blindly.' })
})
