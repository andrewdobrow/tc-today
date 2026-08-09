import { withSupabase } from 'npm:@supabase/server@^1'
import { ACTIVE_STATUSES, STRIPE_LIVEMODE } from '../_shared/membership.ts'

export default {
  fetch: withSupabase({ auth: 'user' }, async (_req, ctx) => {
    const userId = ctx.userClaims?.id
    const email = ctx.userClaims?.email ?? null

    if (!userId) {
      return Response.json({ error: 'Authenticated user id is missing.' }, { status: 401 })
    }

    const { data: profile, error: profileError } = await ctx.supabaseAdmin
      .from('profiles')
      .select('id,email,is_admin,stripe_customer_id')
      .eq('id', userId)
      .maybeSingle()

    if (profileError) {
      console.error('membership-status profile lookup failed', profileError)
      return Response.json({ error: 'Unable to check membership.' }, { status: 500 })
    }

    // The migration backfills profiles, but keep the endpoint resilient if a
    // brand-new auth user arrives during a deployment race.
    if (!profile) {
      const { error: insertError } = await ctx.supabaseAdmin
        .from('profiles')
        .upsert({ id: userId, email }, { onConflict: 'id' })
      if (insertError) {
        console.error('membership-status profile repair failed', insertError)
        return Response.json({ error: 'Unable to check membership.' }, { status: 500 })
      }
    }

    const isAdmin = Boolean(profile?.is_admin)

    const { data: subscriptions, error: subscriptionError } = await ctx.supabaseAdmin
      .from('subscriptions')
      .select('status,current_period_end,cancel_at_period_end,stripe_price_id,stripe_subscription_id,stripe_livemode')
      .eq('user_id', userId)
      .eq('stripe_livemode', STRIPE_LIVEMODE)
      .order('current_period_end', { ascending: false, nullsFirst: false })

    if (subscriptionError) {
      console.error('membership-status subscription lookup failed', subscriptionError)
      return Response.json({ error: 'Unable to check membership.' }, { status: 500 })
    }

    const active = (subscriptions ?? []).find((row) => ACTIVE_STATUSES.has(String(row.status || '')))
    const entitled = isAdmin || Boolean(active)

    return Response.json({
      authenticated: true,
      user_id: userId,
      email,
      is_admin: isAdmin,
      entitled,
      entitlement_source: isAdmin ? 'admin' : active ? 'stripe_subscription' : 'none',
      subscription: active ?? null,
    })
  }),
}
