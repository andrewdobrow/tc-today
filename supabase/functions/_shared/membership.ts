import Stripe from 'npm:stripe@^22'

export const ACTIVE_STATUSES = new Set(['active', 'trialing'])

const rawStripeMode = (Deno.env.get('TCT_STRIPE_MODE') ?? 'test').trim().toLowerCase()
export const STRIPE_MODE = rawStripeMode === 'live' ? 'live' : 'test'
export const STRIPE_LIVEMODE = STRIPE_MODE === 'live'

export function stripeSecretMatchesMode(secret: string) {
  if (!secret) return false
  return STRIPE_LIVEMODE ? secret.startsWith('sk_live_') : secret.startsWith('sk_test_')
}

export function stripeObjectMatchesMode(value: { livemode?: boolean } | null | undefined) {
  return Boolean(value?.livemode) === STRIPE_LIVEMODE
}

export function normalizeEmail(value: unknown) {
  return String(value ?? '').trim().toLowerCase()
}

export function safeReturnPath(value: unknown) {
  const raw = String(value ?? '').trim()
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return '/'
  try {
    const parsed = new URL(raw, 'https://treasurecoast.today')
    if (parsed.origin !== 'https://treasurecoast.today') return '/'
    return `${parsed.pathname}${parsed.search}${parsed.hash}` || '/'
  } catch {
    return '/'
  }
}

export function maskedEmail(email: string) {
  const [local, domain] = email.split('@')
  if (!local || !domain) return 'your email address'
  const visible = local.slice(0, Math.min(2, local.length))
  return `${visible}${'*'.repeat(Math.max(2, Math.min(6, local.length - visible.length)))}@${domain}`
}

export function idFromExpandable(value: string | Stripe.Customer | Stripe.DeletedCustomer | null | undefined) {
  if (!value) return null
  return typeof value === 'string' ? value : value.id
}

export function subscriptionPeriodEnd(subscription: Stripe.Subscription) {
  const direct = (subscription as unknown as { current_period_end?: number }).current_period_end
  if (typeof direct === 'number') return direct
  const item = subscription.items?.data?.[0] as unknown as { current_period_end?: number } | undefined
  return typeof item?.current_period_end === 'number' ? item.current_period_end : null
}

export async function resolveMembershipUser(
  supabaseAdmin: any,
  emailValue: unknown,
  customerId: string | null,
) {
  const email = normalizeEmail(emailValue)
  if (!email || !email.includes('@')) throw new Error('Stripe Checkout did not provide a usable email address.')

  const { data: profiles, error: profileError } = await supabaseAdmin
    .from('profiles')
    .select('id,email,stripe_customer_id')
    .ilike('email', email)
    .limit(2)
  if (profileError) throw profileError
  if ((profiles ?? []).length > 1) throw new Error(`Ambiguous Supabase profile mapping for ${email}`)

  let userId = profiles?.[0]?.id ?? null
  if (!userId) {
    const { data: created, error: createError } = await supabaseAdmin.auth.admin.createUser({
      email,
      email_confirm: false,
      user_metadata: { membership_source: 'stripe_checkout' },
    })
    if (createError) {
      // A webhook/completion race may have created the user milliseconds earlier.
      const { data: retryProfiles, error: retryError } = await supabaseAdmin
        .from('profiles')
        .select('id,email,stripe_customer_id')
        .ilike('email', email)
        .limit(2)
      if (retryError) throw retryError
      if ((retryProfiles ?? []).length !== 1) throw createError
      userId = retryProfiles[0].id
    } else {
      userId = created?.user?.id ?? null
    }
  }
  if (!userId) throw new Error('Unable to establish a Supabase membership identity.')

  const profilePayload: Record<string, unknown> = {
    id: userId,
    email,
    updated_at: new Date().toISOString(),
  }
  if (customerId) profilePayload.stripe_customer_id = customerId

  const { error: upsertError } = await supabaseAdmin
    .from('profiles')
    .upsert(profilePayload, { onConflict: 'id' })
  if (upsertError) throw upsertError

  return { userId, email }
}

export async function syncSubscription(
  subscription: Stripe.Subscription,
  supabaseAdmin: any,
  forcedUserId: string | null = null,
) {
  const customerId = idFromExpandable(subscription.customer as any)
  let userId = forcedUserId || subscription.metadata?.supabase_user_id || null

  if (!userId && customerId) {
    const { data: profile, error } = await supabaseAdmin
      .from('profiles')
      .select('id')
      .eq('stripe_customer_id', customerId)
      .maybeSingle()
    if (error) throw error
    userId = profile?.id ?? null
  }

  if (!userId) throw new Error(`No Supabase user mapping for Stripe subscription ${subscription.id}`)

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
        stripe_livemode: Boolean(subscription.livemode),
        current_period_end: periodEnd ? new Date(periodEnd * 1000).toISOString() : null,
        cancel_at_period_end: Boolean(subscription.cancel_at_period_end),
        updated_at: new Date().toISOString(),
      },
      { onConflict: 'stripe_subscription_id' },
    )
  if (subscriptionError) throw subscriptionError
  return userId
}
