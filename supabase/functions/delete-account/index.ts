import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'
import { deletedIdentifierHash, STRIPE_MODE, stripeSecretMatchesMode } from '../_shared/membership.ts'

// Deletion is authenticated, explicit, immediate, and never triggered by signing out
// or by ordinary subscription cancellation.
const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const stripe = stripeSecret ? new Stripe(stripeSecret) : null
const canCancel = new Set(['active', 'trialing', 'past_due', 'unpaid', 'paused', 'incomplete'])

export default {
  fetch: withSupabase({ auth: 'user' }, async (req, ctx) => {
    if (req.method !== 'POST') return Response.json({ error: 'Method not allowed.' }, { status: 405 })
    const userId = ctx.userClaims?.id
    if (!userId) return Response.json({ error: 'Authentication required.' }, { status: 401 })
    let input: { confirmation?: string }
    try { input = await req.json() } catch { return Response.json({ error: 'Invalid request body.' }, { status: 400 }) }
    if (input.confirmation !== 'DELETE') return Response.json({ error: 'Confirm permanent account deletion.' }, { status: 400 })

    if (!stripe || !stripeSecretMatchesMode(stripeSecret)) {
      console.error(`delete-account refused unsafe Stripe mode: ${STRIPE_MODE}`)
      return Response.json({ error: 'Account deletion is temporarily unavailable. Please contact support.' }, { status: 503 })
    }

    const admin = ctx.supabaseAdmin
    const { data: profile, error: profileError } = await admin.from('profiles')
      .select('id,is_admin,stripe_customer_id').eq('id', userId).maybeSingle()
    if (profileError) return Response.json({ error: 'Could not check account details.' }, { status: 500 })
    // Prevent accidental self-destruction of TCT's publishing/admin identity.
    if (profile?.is_admin) return Response.json({ error: 'Publisher/admin accounts require manual deletion through support.' }, { status: 403 })

    const { data: memberships, error: membershipError } = await admin.from('subscriptions')
      .select('stripe_customer_id,stripe_subscription_id').eq('user_id', userId)
    if (membershipError) return Response.json({ error: 'Could not check subscription details.' }, { status: 500 })
    const knownSubscriptionIds = new Set((memberships ?? [])
      .map((row: any) => row.stripe_subscription_id).filter((id: any) => typeof id === 'string' && id.startsWith('sub_')))
    const tctPriceIds = new Set([Deno.env.get('STRIPE_PRICE_MONTHLY'), Deno.env.get('STRIPE_PRICE_ANNUAL')].filter(Boolean))
    if (!tctPriceIds.size && !knownSubscriptionIds.size && profile?.stripe_customer_id) {
      return Response.json({ error: 'Could not safely identify TCT billing plans. Please contact support.' }, { status: 503 })
    }
    const linkedCustomers: string[] = [profile?.stripe_customer_id, ...(memberships ?? []).map((s: any) => s.stripe_customer_id)]
      .filter((id): id is string => typeof id === 'string' && id.startsWith('cus_'))
    // Recover old subscription rows without a linked customer rather than
    // silently deleting an account that might still have a renewal outstanding.
    try {
      for (const row of memberships ?? []) {
        if (row.stripe_customer_id) continue
        if (!row.stripe_subscription_id) throw new Error('Membership row has no billing identifiers')
        const subscription = await stripe.subscriptions.retrieve(row.stripe_subscription_id)
        const customerId = typeof subscription.customer === 'string' ? subscription.customer : subscription.customer?.id
        if (!customerId?.startsWith('cus_')) throw new Error('Invalid membership customer mapping')
        linkedCustomers.push(customerId)
      }
    } catch (error) {
      console.error('delete-account could not resolve previous Stripe memberships', error)
      return Response.json({ error: 'Could not verify all billing relationships. Please contact support.' }, { status: 503 })
    }
    const customers = [...new Set(linkedCustomers)]
    // A Stripe customer belonging to multiple Auth users needs human review;
    // canceling its subscriptions would otherwise affect someone else's access.
    for (const customerId of customers) {
      const { data: others, error: ownerError } = await admin.from('profiles')
        .select('id').eq('stripe_customer_id', customerId).neq('id', userId).limit(1)
      const { data: otherSubscriptions, error: subscriptionOwnerError } = await admin.from('subscriptions')
        .select('user_id').eq('stripe_customer_id', customerId).neq('user_id', userId).limit(1)
      if (ownerError || subscriptionOwnerError || others?.length || otherSubscriptions?.length) {
        return Response.json({ error: 'This billing profile needs manual review before account deletion. Please contact support.' }, { status: 409 })
      }
    }

    // Persist irreversible digests BEFORE Stripe calls or Auth deletion. This
    // prevents delayed checkout-complete/webhook events resurrecting the account.
    // No email, customer ID, or user UUID is stored in plaintext here.
    try {
      const identifiers = [await deletedIdentifierHash('user', userId),
        ...(await Promise.all(customers.map((id) => deletedIdentifierHash('customer', id))))]
      const { error: markerError } = await admin.from('membership_deleted_identifiers')
        .upsert(identifiers.map((identifier_hash) => ({ identifier_hash })), { onConflict: 'identifier_hash', ignoreDuplicates: true })
      if (markerError) throw markerError
    } catch (error) {
      console.error('delete-account could not persist replay protection', error)
      return Response.json({ error: 'Could not safely start deletion. No account data was deleted.' }, { status: 503 })
    }

    const isTCTSubscription = (sub: Stripe.Subscription) =>
      knownSubscriptionIds.has(sub.id) ||
      sub.items.data.some((item) => tctPriceIds.has(item.price.id)) ||
      (sub.metadata?.tct_stripe_mode === STRIPE_MODE && ['monthly', 'annual'].includes(sub.metadata?.plan || ''))

    let canceled = 0
    try {
      for (const customerId of customers) {
        // Auto-pagination is important: a customer may have many older subscriptions.
        for await (const subscription of stripe.subscriptions.list({ customer: customerId, status: 'all', limit: 100 })) {
          if (isTCTSubscription(subscription) && canCancel.has(subscription.status)) {
            try {
              await stripe.subscriptions.cancel(subscription.id, { prorate: false, invoice_now: false })
              canceled++
            } catch (error) {
              // A simultaneous cancellation webhook/portal action is not a failure
              // if Stripe now confirms the subscription is terminal.
              const current = await stripe.subscriptions.retrieve(subscription.id)
              if (canCancel.has(current.status)) throw error
            }
          }
        }
        // Do not delete the identity until Stripe confirms all renewals are stopped.
        for await (const subscription of stripe.subscriptions.list({ customer: customerId, status: 'all', limit: 100 })) {
          if (isTCTSubscription(subscription) && canCancel.has(subscription.status)) throw new Error('Stripe still has a renewable TCT subscription')
        }
      }
    } catch (error) {
      console.error('delete-account Stripe cancellation incomplete', error)
      return Response.json({
        error: 'We could not verify that all renewals were stopped. Your account has not been deleted. Please retry or contact support.',
        retryable: true,
      }, { status: 502 })
    }

    try {
      const { error: deleteError } = await admin.auth.admin.deleteUser(userId)
      if (deleteError) throw deleteError
      return Response.json({ deleted: true, subscriptions_canceled: canceled })
    } catch (error) {
      console.error('delete-account Supabase identity removal failed', error)
      return Response.json({
        error: 'Your subscriptions have been canceled, but account deletion could not finish. Please retry or contact support.',
        retryable: true,
      }, { status: 500 })
    }
  }),
}
