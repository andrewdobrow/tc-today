import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'
import { firstNameFromDisplayName, idFromExpandable, resolveMembershipUser, STRIPE_MODE, stripeObjectMatchesMode, stripeSecretMatchesMode, syncSubscription } from '../_shared/membership.ts'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET') ?? ''
const stripe = new Stripe(stripeSecret)
const cryptoProvider = Stripe.createSubtleCryptoProvider()

export default {
  fetch: withSupabase({ auth: 'none' }, async (req, ctx) => {
    if (!stripeSecret || !webhookSecret) return new Response('Stripe webhook secrets are not configured.', { status: 503 })
    if (!stripeSecretMatchesMode(stripeSecret)) {
      console.error(`stripe-webhook Stripe mode mismatch: expected ${STRIPE_MODE}`)
      return new Response('Stripe payment mode is not configured safely.', { status: 503 })
    }
    const signature = req.headers.get('Stripe-Signature')
    if (!signature) return new Response('Missing Stripe-Signature header.', { status: 400 })

    const rawBody = await req.text()
    let event: Stripe.Event
    try {
      event = await stripe.webhooks.constructEventAsync(rawBody, signature, webhookSecret, undefined, cryptoProvider)
    } catch (error) {
      console.error('stripe-webhook signature verification failed', error)
      return new Response('Invalid webhook signature.', { status: 400 })
    }
    if (!stripeObjectMatchesMode(event)) {
      console.error(`stripe-webhook rejected ${event.id}: Stripe event mode does not match ${STRIPE_MODE}`)
      return new Response('Stripe event mode mismatch.', { status: 409 })
    }

    const { data: alreadyProcessed, error: seenError } = await ctx.supabaseAdmin
      .from('stripe_webhook_events').select('event_id').eq('event_id', event.id).maybeSingle()
    if (seenError) return new Response('Webhook persistence unavailable.', { status: 500 })
    if (alreadyProcessed) return Response.json({ received: true, duplicate: true })

    try {
      if (event.type === 'checkout.session.completed') {
        const session = event.data.object as Stripe.Checkout.Session
        const customerId = idFromExpandable(session.customer as any)
        const email = session.customer_details?.email || session.customer_email
        let userId = session.client_reference_id || session.metadata?.supabase_user_id || null

        if (!userId && email) {
          const resolved = await resolveMembershipUser(ctx.supabaseAdmin, email, customerId)
          userId = resolved.userId
        }
        if (!userId) throw new Error(`No membership identity for Checkout session ${session.id}`)

        const firstName = firstNameFromDisplayName(session.customer_details?.individual_name || session.customer_details?.name)
        if (customerId || firstName) {
          const profileUpdate: Record<string, unknown> = { updated_at: new Date().toISOString() }
          if (customerId) profileUpdate.stripe_customer_id = customerId
          if (firstName) profileUpdate.first_name = firstName
          const { error } = await ctx.supabaseAdmin.from('profiles')
            .update(profileUpdate).eq('id', userId)
          if (error) throw error
        }

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
      } else if (
        event.type === 'customer.subscription.created' ||
        event.type === 'customer.subscription.updated' ||
        event.type === 'customer.subscription.deleted'
      ) {
        await syncSubscription(event.data.object as Stripe.Subscription, ctx.supabaseAdmin)
      }

      const { error: recordError } = await ctx.supabaseAdmin.from('stripe_webhook_events')
        .insert({ event_id: event.id, event_type: event.type })
      if (recordError && recordError.code !== '23505') throw recordError
      return Response.json({ received: true })
    } catch (error) {
      console.error(`stripe-webhook processing failed for ${event.id}`, error)
      // Do not record the event as processed. Stripe can safely retry it.
      return new Response('Webhook processing failed.', { status: 500 })
    }
  }),
}
