import { withSupabase } from 'npm:@supabase/server@^1'
import { ACTIVE_STATUSES, STRIPE_LIVEMODE } from '../_shared/membership.ts'

const METER_POLICY = 'one_free_article_per_month'
const METER_TIME_ZONE = 'America/New_York'
const FULL_BODY_MARKER = '<!--tct-full-article-v2-->'

type MeterPayload = {
  v: 1
  period: string
  slug: string
  issued_at: number
}

type RequestBody = {
  action?: string
  slug?: string
  meter_token?: string
}

function currentMeterPeriod() {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: METER_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
  }).formatToParts(new Date())
  const year = parts.find((part) => part.type === 'year')?.value ?? ''
  const month = parts.find((part) => part.type === 'month')?.value ?? ''
  if (!/^\d{4}$/.test(year) || !/^\d{2}$/.test(month)) throw new Error('Unable to resolve meter period.')
  return `${year}-${month}`
}

function bytesToBase64Url(bytes: Uint8Array) {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function textToBase64Url(value: string) {
  return bytesToBase64Url(new TextEncoder().encode(value))
}

function base64UrlToText(value: string) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4)
  const binary = atob(padded)
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}

function meterSecret() {
  const secret = (Deno.env.get('TCT_METER_TOKEN_SECRET') ?? Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '').trim()
  if (!secret) throw new Error('Meter token signing secret is unavailable.')
  return secret
}

async function meterSignature(payloadSegment: string) {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(meterSecret()),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const signature = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(payloadSegment))
  return bytesToBase64Url(new Uint8Array(signature))
}

async function signMeterToken(payload: MeterPayload) {
  const payloadSegment = textToBase64Url(JSON.stringify(payload))
  return `${payloadSegment}.${await meterSignature(payloadSegment)}`
}

async function readMeterToken(raw: unknown): Promise<MeterPayload | null> {
  const token = String(raw ?? '').trim()
  if (!token || token.length > 2048) return null
  const [payloadSegment, suppliedSignature, extra] = token.split('.')
  if (!payloadSegment || !suppliedSignature || extra) return null
  const expectedSignature = await meterSignature(payloadSegment)
  if (suppliedSignature !== expectedSignature) return null
  try {
    const parsed = JSON.parse(base64UrlToText(payloadSegment)) as Partial<MeterPayload>
    if (parsed.v !== 1 || !/^\d{4}-\d{2}$/.test(String(parsed.period ?? ''))) return null
    if (!/^[a-z0-9][a-z0-9-]{2,180}$/.test(String(parsed.slug ?? ''))) return null
    if (!Number.isFinite(Number(parsed.issued_at))) return null
    return parsed as MeterPayload
  } catch {
    return null
  }
}

async function optionalUserId(req: Request, ctx: any) {
  const auth = String(req.headers.get('authorization') ?? '')
  const match = auth.match(/^Bearer\s+(.+)$/i)
  const token = match?.[1]?.trim() ?? ''
  // Modern publishable keys are not user JWTs. Legacy anon keys look like JWTs
  // but resolve to no Auth user, so getUser still fails closed safely.
  if (!token || token.split('.').length !== 3) return null
  const { data, error } = await ctx.supabaseAdmin.auth.getUser(token)
  if (error) return null
  return data?.user?.id ?? null
}

async function hasMembership(ctx: any, userId: string | null) {
  if (!userId) return false
  const { data: profile, error: profileError } = await ctx.supabaseAdmin.from('profiles')
    .select('is_admin').eq('id', userId).maybeSingle()
  if (profileError) throw profileError
  if (profile?.is_admin) return true

  const { data: subscriptions, error: subscriptionError } = await ctx.supabaseAdmin.from('subscriptions')
    .select('status,stripe_livemode').eq('user_id', userId).eq('stripe_livemode', STRIPE_LIVEMODE).limit(20)
  if (subscriptionError) throw subscriptionError
  return (subscriptions ?? []).some((row: any) => ACTIVE_STATUSES.has(String(row.status || '')))
}

export default {
  fetch: withSupabase({ auth: 'none' }, async (req, ctx) => {
    let body: RequestBody
    try { body = await req.json() } catch { return Response.json({ error: 'Invalid request body.' }, { status: 400 }) }

    if (body.action === 'meter-capability') {
      return Response.json({
        meter_policy: METER_POLICY,
        free_articles_per_period: 1,
        period: currentMeterPeriod(),
        period_time_zone: METER_TIME_ZONE,
      })
    }

    const slug = String(body.slug ?? '').trim()
    if (!/^[a-z0-9][a-z0-9-]{2,180}$/.test(slug)) return Response.json({ error: 'Invalid article slug.' }, { status: 400 })

    const { data: article, error: articleError } = await ctx.supabaseAdmin.from('protected_articles')
      .select('slug,protected_body,updated_at').eq('slug', slug).maybeSingle()
    if (articleError) return Response.json({ error: 'Unable to load article.' }, { status: 500 })
    if (!article) return Response.json({ error: 'Protected article content is not available yet.' }, { status: 404 })

    const userId = await optionalUserId(req, ctx)
    try {
      if (await hasMembership(ctx, userId)) {
        return Response.json({
          slug: article.slug,
          protected_body: article.protected_body,
          updated_at: article.updated_at,
          access: 'member',
        })
      }
    } catch {
      return Response.json({ error: 'Unable to verify membership.' }, { status: 500 })
    }

    const period = currentMeterPeriod()
    const existingMeter = await readMeterToken(body.meter_token)
    if (existingMeter?.period === period && existingMeter.slug !== slug) {
      return Response.json({
        error: 'Your free article for this month has already been used.',
        code: 'FREE_ARTICLE_USED',
        meter_policy: METER_POLICY,
        period,
        used_slug: existingMeter.slug,
      }, { status: 403 })
    }

    let meterToken = String(body.meter_token ?? '').trim()
    if (!existingMeter || existingMeter.period !== period || existingMeter.slug !== slug) {
      meterToken = await signMeterToken({ v: 1, period, slug, issued_at: Date.now() })
    }

    return Response.json({
      slug: article.slug,
      protected_body: article.protected_body,
      updated_at: article.updated_at,
      access: 'monthly_free',
      meter_policy: METER_POLICY,
      free_articles_per_period: 1,
      period,
      meter_token: meterToken,
      full_body_payload: String(article.protected_body || '').startsWith(FULL_BODY_MARKER),
    })
  }),
}
