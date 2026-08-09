import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'
import { idFromExpandable, maskedEmail, resolveMembershipUser, safeReturnPath, STRIPE_MODE, stripeObjectMatchesMode, stripeSecretMatchesMode, syncSubscription } from '../_shared/membership.ts'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const siteUrl = (Deno.env.get('SITE_URL') ?? 'https://treasurecoast.today').replace(/\/$/, '')
const stripe = new Stripe(stripeSecret)

export default {
  fetch: withSupabase({ auth: 'none' }, async (req, ctx) => {
    if (!stripeSecret) return Response.json({ error: 'Stripe is not configured.' }, { status: 503 })
    if (!stripeSecretMatchesMode(stripeSecret)) {
      console.error(`checkout-complete Stripe mode mismatch: expected ${STRIPE_MODE}`)
      return Response.json({ error: 'Stripe payment mode is not configured safely.' }, { status: 503 })
    }
    let body: { session_id?: string }
    try { body = await req.json() } catch { return Response.json({ error: 'Invalid request body.' }, { status: 400 }) }
    const sessionId = String(body.session_id ?? '').trim()
    if (!/^cs_(?:test_|live_)?[A-Za-z0-9]+$/.test(sessionId)) {
      return Response.json({ error: 'Invalid Checkout session.' }, { status: 400 })
    }

    try {
      const session = await stripe.checkout.sessions.retrieve(sessionId)
      if (!stripeObjectMatchesMode(session)) {
        return Response.json({ error: 'Checkout payment mode does not match this membership environment.' }, { status: 409 })
      }
      if (session.status !== 'complete' || !['paid', 'no_payment_required'].includes(String(session.payment_status))) {
        return Response.json({ error: 'Checkout is not complete.' }, { status: 409 })
      }
      const email = session.customer_details?.email || session.customer_email
      const customerId = idFromExpandable(session.customer as any)
      const { userId, email: normalizedEmail } = await resolveMembershipUser(ctx.supabaseAdmin, email, customerId)

      const subscriptionId = typeof session.subscription === 'string' ? session.subscription : session.subscription?.id
      if (subscriptionId) {
        let subscription = await stripe.subscriptions.retrieve(subscriptionId)
        if (subscription.metadata?.supabase_user_id !== userId) {
          subscription = await stripe.subscriptions.update(subscriptionId, {
            metadata: { ...subscription.metadata, supabase_user_id: userId },
          })
        }
        await syncSubscription(subscription, ctx.supabaseAdmin, userId)
      }

      const { data: sent } = await ctx.supabaseAdmin.from('membership_checkout_links')
        .select('session_id').eq('session_id', sessionId).maybeSingle()
      let linkSent = Boolean(sent)
      if (!linkSent) {
        const returnPath = safeReturnPath(session.metadata?.return_path)
        const separator = returnPath.includes('?') ? '&' : '?'
        const redirectTo = `${siteUrl}${returnPath}${separator}membership=welcome`
        const { error: otpError } = await ctx.supabaseAdmin.auth.signInWithOtp({
          email: normalizedEmail,
          options: { emailRedirectTo: redirectTo, shouldCreateUser: false },
        })
        if (otpError) throw otpError
        const { error: recordError } = await ctx.supabaseAdmin.from('membership_checkout_links').insert({ session_id: sessionId })
        if (recordError && recordError.code !== '23505') throw recordError
        linkSent = true
      }

      return Response.json({ complete: true, link_sent: linkSent, email: maskedEmail(normalizedEmail) })
    } catch (error) {
      console.error('checkout-complete failed', error)
      return Response.json({ error: 'Unable to finish membership setup.' }, { status: 500 })
    }
  }),
}
