import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const webhookSecret = Deno.env.get('STRIPE_WEBHOOK_SECRET') ?? ''
const stripe = new Stripe(stripeSecret)
const cryptoProvider = Stripe.createSubtleCryptoProvider()

function idFromExpandable(value: string | Stripe.Customer | Stripe.DeletedCustomer | null | undefined) {
  if (!value) return null
  return typeof value === 'string' ? value : value.id
}

function subscriptionPeriodEnd(subscription: Stripe.Subscription) {
  const direct = (subscription as unknown as { current_period_end?: number }).current_period_end
  if (typeof direct === 'number') return direct
  const item = subscription.items?.data?.[0] as unknown as { current_period_end?: number } | undefined
  return typeof item?.current_period_end === 'number' ? item.current_period_end : null
}

async function syncSubscription(subscription: Stripe.Subscription, supabaseAdmin: any) {
  const customerId = idFromExpandable(subscription.customer as any)
  let userId = subscription.metadata?.supabase_user_id || null

  if (!userId && customerId) {
    const { data: profile, error } = await supabaseAdmin
      .from('profiles')
      .select('id')
      .eq('stripe_customer_id', customerId)
      .maybeSingle()
    if (error) throw error
    userId = profile?.id ?? null
  }

  if (!userId) {
    throw new Error(`No Supabase user mapping for Stripe subscription ${subscription.id}`)
  }

  if (customerId) {
    const { error: profileError } = await supabaseAdmin
      .from('profiles')
      .update({ stripe_customer_id: customerId, updated_at: new Date().toISOString() })
      .eq('id', userId)
    if (profileError) throw profileError
  }

  const periodEnd = subscriptionPeriodEnd(subscription)
  const priceId = subscription.items?.data?.[0]?.price?.id ?? null

  const { error: subscriptionError } = await supabaseAdmin
    .from('subscriptions')
    .upsert(
      {
        user_id: userId,
        stripe_customer_id: customerId,
        stripe_subscription_id: subscription.id,
        stripe_price_id: priceId,
        status: subscription.status,
        current_period_end: periodEnd ? new Date(periodEnd * 1000).toISOString() : null,
        cancel_at_period_end: Boolean(subscription.cancel_at_period_end),
        updated_at: new Date().toISOString(),
      },
      { onConflict: 'stripe_subscription_id' },
    )

  if (subscriptionError) throw subscriptionError
}

export default {
  fetch: withSupabase({ auth: 'none' }, async (req, ctx) => {
    if (!stripeSecret || !webhookSecret) {
      return new Response('Stripe webhook secrets are not configured.', { status: 503 })
    }

    const signature = req.headers.get('Stripe-Signature')
    if (!signature) return new Response('Missing Stripe-Signature header.', { status: 400 })

    const rawBody = await req.text()
    let event: Stripe.Event

    try {
      event = await stripe.webhooks.constructEventAsync(
        rawBody,
        signature,
        webhookSecret,
        undefined,
        cryptoProvider,
      )
    } catch (error) {
      console.error('stripe-webhook signature verification failed', error)
      return new Response('Invalid webhook signature.', { status: 400 })
    }

    const { data: alreadyProcessed, error: seenError } = await ctx.supabaseAdmin
      .from('stripe_webhook_events')
      .select('event_id')
      .eq('event_id', event.id)
      .maybeSingle()

    if (seenError) {
      console.error('stripe-webhook idempotency lookup failed', seenError)
      return new Response('Webhook persistence unavailable.', { status: 500 })
    }

    if (alreadyProcessed) {
      return Response.json({ received: true, duplicate: true })
    }

    try {
      if (event.type === 'checkout.session.completed') {
        const session = event.data.object as Stripe.Checkout.Session
        const userId = session.client_reference_id || session.metadata?.supabase_user_id || null
        const customerId = idFromExpandable(session.customer as any)

        if (userId && customerId) {
          const { error } = await ctx.supabaseAdmin
            .from('profiles')
            .update({ stripe_customer_id: customerId, updated_at: new Date().toISOString() })
            .eq('id', userId)
          if (error) throw error
        }

        const subscriptionId = typeof session.subscription === 'string'
          ? session.subscription
          : session.subscription?.id
        if (subscriptionId) {
          const subscription = await stripe.subscriptions.retrieve(subscriptionId)
          await syncSubscription(subscription, ctx.supabaseAdmin)
        }
      } else if (
        event.type === 'customer.subscription.created' ||
        event.type === 'customer.subscription.updated' ||
        event.type === 'customer.subscription.deleted'
      ) {
        await syncSubscription(event.data.object as Stripe.Subscription, ctx.supabaseAdmin)
      }

      const { error: recordError } = await ctx.supabaseAdmin
        .from('stripe_webhook_events')
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
