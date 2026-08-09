import { withSupabase } from 'npm:@supabase/server@^1'

const expectedSecret = Deno.env.get('TCT_CONTENT_SYNC_SECRET') ?? ''

async function digest(value: string) {
  return new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))
}
async function secureEqual(left: string, right: string) {
  if (!left || !right) return false
  const a = await digest(left); const b = await digest(right)
  if (a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i]
  return diff === 0
}

export default {
  fetch: withSupabase({ auth: 'none' }, async (req, ctx) => {
    if (!expectedSecret) return Response.json({ error: 'Content sync is not configured.' }, { status: 503 })
    if (!(await secureEqual(req.headers.get('X-TCT-Content-Sync') ?? '', expectedSecret))) {
      return Response.json({ error: 'Unauthorized.' }, { status: 401 })
    }

    let body: {
      action?: string
      offset?: number
      limit?: number
      articles?: Array<{ slug?: string; protected_body?: string }>
    }
    try { body = await req.json() } catch { return Response.json({ error: 'Invalid request body.' }, { status: 400 }) }

    // Server-to-server snapshot used only to rehydrate already-paywalled repository
    // pages before applying a newer teaser format. It is protected by the dedicated
    // content-sync secret and is never available through browser configuration.
    if (body.action === 'snapshot') {
      const offset = Math.max(0, Math.floor(Number(body.offset ?? 0)))
      const limit = Math.min(250, Math.max(1, Math.floor(Number(body.limit ?? 200))))
      const { data, error } = await ctx.supabaseAdmin.from('protected_articles')
        .select('slug,protected_body,updated_at')
        .order('slug', { ascending: true })
        .range(offset, offset + limit - 1)
      if (error) {
        console.error('sync-protected-articles snapshot failed', error)
        return Response.json({ error: 'Protected article snapshot failed.' }, { status: 500 })
      }
      const rows = data ?? []
      return Response.json({
        articles: rows,
        next_offset: rows.length === limit ? offset + rows.length : null,
      })
    }

    const articles = Array.isArray(body.articles) ? body.articles : []
    if (!articles.length || articles.length > 100) return Response.json({ error: 'Batch must contain 1-100 articles.' }, { status: 400 })

    const now = new Date().toISOString()
    const rows = []
    for (const item of articles) {
      const slug = String(item.slug ?? '').trim()
      const protectedBody = String(item.protected_body ?? '')
      if (!/^[a-z0-9][a-z0-9-]{2,180}$/.test(slug) || !protectedBody.trim()) {
        return Response.json({ error: 'Invalid protected article payload.' }, { status: 400 })
      }
      rows.push({ slug, protected_body: protectedBody, updated_at: now })
    }
    const { error } = await ctx.supabaseAdmin.from('protected_articles').upsert(rows, { onConflict: 'slug' })
    if (error) {
      console.error('sync-protected-articles failed', error)
      return Response.json({ error: 'Protected article sync failed.' }, { status: 500 })
    }
    return Response.json({ synced: rows.length })
  }),
}
