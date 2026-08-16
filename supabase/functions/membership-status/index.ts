import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'
import { ACTIVE_STATUSES, firstNameFromDisplayName, STRIPE_LIVEMODE, stripeSecretMatchesMode } from '../_shared/membership.ts'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const stripe = stripeSecret ? new Stripe(stripeSecret) : null

export default {
  fetch: withSupabase({ auth: 'user' }, async (_req, ctx) => {
    const userId = ctx.userClaims?.id
    const email = ctx.userClaims?.email ?? null

    if (!userId) {
      return Response.json({ error: 'Authenticated user id is missing.' }, { status: 401 })
    }

    const { data: profile, error: profileError } = await ctx.supabaseAdmin
      .from('profiles')
      .select('id,email,is_admin,stripe_customer_id,first_name')
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
    let firstName = firstNameFromDisplayName(profile?.first_name)

    // Existing subscribers predate first-name persistence. Recover their name once
    // from the Stripe Customer or a completed Checkout Session, then cache it in
    // profiles so ordinary page views do not make recurring Stripe API calls.
    if (!firstName && profile?.stripe_customer_id && stripe && stripeSecretMatchesMode(stripeSecret)) {
      try {
        const customer = await stripe.customers.retrieve(profile.stripe_customer_id)
        if (!('deleted' in customer && customer.deleted)) {
          firstName = firstNameFromDisplayName(customer.name)
        }
        if (!firstName) {
          const sessions = await stripe.checkout.sessions.list({ customer: profile.stripe_customer_id, limit: 10 })
          for (const session of sessions.data) {
            firstName = firstNameFromDisplayName(session.customer_details?.individual_name || session.customer_details?.name)
            if (firstName) break
          }
        }
        if (firstName) {
          const { error: nameError } = await ctx.supabaseAdmin.from('profiles')
            .update({ first_name: firstName, updated_at: new Date().toISOString() }).eq('id', userId)
          if (nameError) console.error('membership-status first-name persistence failed', nameError)
        }
      } catch (nameError) {
        // Name personalization must never block an otherwise valid entitlement.
        console.error('membership-status first-name recovery failed', nameError)
      }
    }

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
      first_name: firstName,
      is_admin: isAdmin,
      entitled,
      entitlement_source: isAdmin ? 'admin' : active ? 'stripe_subscription' : 'none',
      subscription: active ?? null,
    })
  }),
}
