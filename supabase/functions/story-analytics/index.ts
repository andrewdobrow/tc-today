import { withSupabase } from 'npm:@supabase/server@^1'

const allowedOrigins = new Set([
  'https://treasurecoast.today',
  'https://www.treasurecoast.today',
])

function corsHeaders(req: Request) {
  const origin = req.headers.get('Origin') ?? ''
  return {
    'Access-Control-Allow-Origin': allowedOrigins.has(origin) ? origin : 'https://treasurecoast.today',
    'Access-Control-Allow-Headers': 'content-type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Vary': 'Origin',
    'Cache-Control': 'no-store',
  }
}

function json(req: Request, payload: unknown, status = 200) {
  return Response.json(payload, { status, headers: corsHeaders(req) })
}

export default {
  fetch: withSupabase({ auth: 'none' }, async (req, ctx) => {
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(req) })
    if (req.method !== 'POST') return json(req, { error: 'Method not allowed.' }, 405)

    let body: { action?: string; slug?: string; hours?: number; limit?: number }
    try { body = await req.json() } catch { return json(req, { error: 'Invalid request body.' }, 400) }

    if (body.action === 'capability') {
      const { error } = await ctx.supabaseAdmin.from('story_pageviews_hourly').select('slug').limit(1)
      return json(req, {
        feature: 'tct-most-read-v1',
        schema_ready: !error,
      })
    }

    if (body.action === 'record') {
      const origin = req.headers.get('Origin') ?? ''
      if (origin && !allowedOrigins.has(origin)) return json(req, { error: 'Origin not allowed.' }, 403)
      const slug = String(body.slug ?? '').trim()
      if (!/^[a-z0-9][a-z0-9-]{5,180}$/.test(slug)) return json(req, { error: 'Invalid slug.' }, 400)
      const { error } = await ctx.supabaseAdmin.rpc('increment_story_pageview', { p_slug: slug })
      if (error) {
        // Missing migration is a soft-unavailable state for the public site. The
        // Most Read UI stays hidden until the one-time schema is installed.
        console.error('story-analytics record unavailable', error)
        return json(req, { recorded: false, schema_ready: false }, 200)
      }
      return json(req, { recorded: true, schema_ready: true })
    }

    if (body.action === 'top') {
      const hours = Math.min(168, Math.max(1, Math.floor(Number(body.hours ?? 24))))
      const limit = Math.min(10, Math.max(1, Math.floor(Number(body.limit ?? 5))))
      const { data, error } = await ctx.supabaseAdmin.rpc('top_story_pageviews', { p_hours: hours, p_limit: limit })
      if (error) {
        console.error('story-analytics top unavailable', error)
        return json(req, { stories: [], schema_ready: false }, 200)
      }
      return json(req, {
        stories: (data ?? []).map((row: { slug?: string; views?: number | string }) => ({ slug: row.slug, views: Number(row.views ?? 0) })),
        schema_ready: true,
        hours,
      })
    }

    return json(req, { error: 'Unknown action.' }, 400)
  }),
}
