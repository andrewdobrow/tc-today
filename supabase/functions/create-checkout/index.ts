import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const siteUrl = (Deno.env.get('SITE_URL') ?? 'https://treasurecoast.today').replace(/\/$/, '')
const monthlyPrice = Deno.env.get('STRIPE_PRICE_MONTHLY') ?? ''
const annualPrice = Deno.env.get('STRIPE_PRICE_ANNUAL') ?? ''

const stripe = new Stripe(stripeSecret)
const ACTIVE_STATUSES = new Set(['active', 'trialing'])

function priceForPlan(plan: string) {
  if (plan === 'monthly') return monthlyPrice
  if (plan === 'annual') return annualPrice
  return ''
}

export default {
  fetch: withSupabase({ auth: 'user' }, async (req, ctx) => {
    if (!stripeSecret || !monthlyPrice || !annualPrice) {
      return Response.json({ error: 'Stripe membership secrets are not configured.' }, { status: 503 })
    }

    const userId = ctx.userClaims?.id
    const email = ctx.userClaims?.email ?? null
    if (!userId || !email) {
      return Response.json({ error: 'A confirmed email account is required.' }, { status: 400 })
    }

    let body: { plan?: string }
    try {
      body = await req.json()
    } catch {
      return Response.json({ error: 'Invalid request body.' }, { status: 400 })
    }

    const plan = String(body.plan ?? '').toLowerCase()
    const priceId = priceForPlan(plan)
    if (!priceId) {
      return Response.json({ error: 'Plan must be monthly or annual.' }, { status: 400 })
    }

    const { data: profile, error: profileError } = await ctx.supabaseAdmin
      .from('profiles')
      .select('id,is_admin,stripe_customer_id')
      .eq('id', userId)
      .maybeSingle()

    if (profileError) {
      console.error('create-checkout profile lookup failed', profileError)
      return Response.json({ error: 'Unable to start checkout.' }, { status: 500 })
    }

    if (profile?.is_admin) {
      return Response.json({ error: 'This administrator account already has full access.', code: 'ADMIN_ACCESS' }, { status: 409 })
    }

    const { data: activeSubscriptions, error: subscriptionError } = await ctx.supabaseAdmin
      .from('subscriptions')
      .select('status')
      .eq('user_id', userId)
      .in('status', [...ACTIVE_STATUSES])
      .limit(1)

    if (subscriptionError) {
      console.error('create-checkout subscription lookup failed', subscriptionError)
      return Response.json({ error: 'Unable to start checkout.' }, { status: 500 })
    }

    if ((activeSubscriptions ?? []).length > 0) {
      return Response.json({ error: 'This account already has an active membership.', code: 'ALREADY_MEMBER' }, { status: 409 })
    }

    let customerId = profile?.stripe_customer_id ?? null

    try {
      if (!customerId) {
        const customer = await stripe.customers.create({
          email,
          metadata: { supabase_user_id: userId },
        })
        customerId = customer.id

        const { error: updateError } = await ctx.supabaseAdmin
          .from('profiles')
          .upsert(
            {
              id: userId,
              email,
              stripe_customer_id: customerId,
              updated_at: new Date().toISOString(),
            },
            { onConflict: 'id' },
          )

        if (updateError) throw updateError
      }

      const session = await stripe.checkout.sessions.create({
        mode: 'subscription',
        customer: customerId,
        client_reference_id: userId,
        line_items: [{ price: priceId, quantity: 1 }],
        success_url: `${siteUrl}/membership-test.html?checkout=success`,
        cancel_url: `${siteUrl}/membership-test.html?checkout=cancelled`,
        metadata: {
          supabase_user_id: userId,
          plan,
        },
        subscription_data: {
          metadata: {
            supabase_user_id: userId,
            plan,
          },
        },
      })

      if (!session.url) {
        throw new Error('Stripe did not return a Checkout URL.')
      }

      return Response.json({ url: session.url })
    } catch (error) {
      console.error('create-checkout Stripe error', error)
      return Response.json({ error: 'Unable to start Stripe Checkout.' }, { status: 502 })
    }
  }),
}
