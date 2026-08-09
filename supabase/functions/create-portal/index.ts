import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const siteUrl = (Deno.env.get('SITE_URL') ?? 'https://treasurecoast.today').replace(/\/$/, '')
const stripe = new Stripe(stripeSecret)

export default {
  fetch: withSupabase({ auth: 'user' }, async (_req, ctx) => {
    if (!stripeSecret) return Response.json({ error: 'Stripe is not configured.' }, { status: 503 })
    const userId = ctx.userClaims?.id
    if (!userId) return Response.json({ error: 'Authentication required.' }, { status: 401 })

    const { data: profile, error } = await ctx.supabaseAdmin.from('profiles')
      .select('is_admin,stripe_customer_id').eq('id', userId).maybeSingle()
    if (error) return Response.json({ error: 'Unable to load membership account.' }, { status: 500 })
    if (profile?.is_admin && !profile?.stripe_customer_id) {
      return Response.json({ error: 'Administrator access has no Stripe billing account.', code: 'ADMIN_NO_BILLING' }, { status: 409 })
    }
    if (!profile?.stripe_customer_id) return Response.json({ error: 'No Stripe billing account is linked.' }, { status: 404 })

    try {
      const portal = await stripe.billingPortal.sessions.create({
        customer: profile.stripe_customer_id,
        return_url: `${siteUrl}/subscribe.html`,
      })
      return Response.json({ url: portal.url })
    } catch (portalError) {
      console.error('create-portal failed', portalError)
      return Response.json({ error: 'Unable to open billing management.' }, { status: 502 })
    }
  }),
}
