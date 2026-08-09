import { withSupabase } from 'npm:@supabase/server@^1'
import { ACTIVE_STATUSES, STRIPE_LIVEMODE } from '../_shared/membership.ts'

export default {
  fetch: withSupabase({ auth: 'user' }, async (req, ctx) => {
    const userId = ctx.userClaims?.id
    if (!userId) return Response.json({ error: 'Authentication required.' }, { status: 401 })
    let body: { slug?: string }
    try { body = await req.json() } catch { return Response.json({ error: 'Invalid request body.' }, { status: 400 }) }
    const slug = String(body.slug ?? '').trim()
    if (!/^[a-z0-9][a-z0-9-]{2,180}$/.test(slug)) return Response.json({ error: 'Invalid article slug.' }, { status: 400 })

    const { data: profile, error: profileError } = await ctx.supabaseAdmin.from('profiles')
      .select('is_admin').eq('id', userId).maybeSingle()
    if (profileError) return Response.json({ error: 'Unable to verify membership.' }, { status: 500 })

    let entitled = Boolean(profile?.is_admin)
    if (!entitled) {
      const { data: subscriptions, error: subscriptionError } = await ctx.supabaseAdmin.from('subscriptions')
        .select('status,stripe_livemode').eq('user_id', userId).eq('stripe_livemode', STRIPE_LIVEMODE).limit(20)
      if (subscriptionError) return Response.json({ error: 'Unable to verify membership.' }, { status: 500 })
      entitled = (subscriptions ?? []).some((row) => ACTIVE_STATUSES.has(String(row.status || '')))
    }
    if (!entitled) return Response.json({ error: 'Active membership required.', code: 'MEMBERSHIP_REQUIRED' }, { status: 403 })

    const { data: article, error: articleError } = await ctx.supabaseAdmin.from('protected_articles')
      .select('slug,protected_body,updated_at').eq('slug', slug).maybeSingle()
    if (articleError) return Response.json({ error: 'Unable to load article.' }, { status: 500 })
    if (!article) return Response.json({ error: 'Protected article content is not available yet.' }, { status: 404 })
    return Response.json({ slug: article.slug, protected_body: article.protected_body, updated_at: article.updated_at })
  }),
}
