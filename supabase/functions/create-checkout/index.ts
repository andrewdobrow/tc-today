import { withSupabase } from 'npm:@supabase/server@^1'
import Stripe from 'npm:stripe@^22'
import { safeReturnPath, STRIPE_MODE, stripeSecretMatchesMode } from '../_shared/membership.ts'

const stripeSecret = Deno.env.get('STRIPE_SECRET_KEY') ?? ''
const siteUrl = (Deno.env.get('SITE_URL') ?? 'https://treasurecoast.today').replace(/\/$/, '')
const monthlyPrice = Deno.env.get('STRIPE_PRICE_MONTHLY') ?? ''
const annualPrice = Deno.env.get('STRIPE_PRICE_ANNUAL') ?? ''
const stripe = new Stripe(stripeSecret)
const MONTHLY_INTRO_COUPON = Deno.env.get('STRIPE_MONTHLY_INTRO_COUPON') ?? 'z039dZCN'
const TCCN_FREE_MONTH_COUPON = Deno.env.get('STRIPE_TCCN_FREE_MONTH_COUPON') ?? 'RIoemf0n'

const TCCN_PARTNER_ID = 'treasure-coast-community-news'
const TCCN_PARTNER_NAME = 'Treasure Coast Community News'
const TCCN_LANDING_PATH = '/partners/treasure-coast-community-news.html'

function partnerOfferFor(raw: string | undefined) {
  const partner = String(raw ?? '').trim().toLowerCase()
  if (partner !== TCCN_PARTNER_ID) return null
  return {
    id: TCCN_PARTNER_ID,
    name: TCCN_PARTNER_NAME,
    coupon: TCCN_FREE_MONTH_COUPON,
    landingPath: TCCN_LANDING_PATH,
  }
}

function priceForPlan(plan: string) {
  if (plan === 'monthly') return monthlyPrice
  if (plan === 'annual') return annualPrice
  return ''
}

export default {
  // Checkout-first by design: Stripe collects the email and payment method. No TCT account is required
  // before Checkout. The signed Stripe webhook establishes/links the identity and paid entitlement.
  fetch: withSupabase({ auth: 'none' }, async (req) => {
    if (!stripeSecret || !monthlyPrice || !annualPrice) {
      return Response.json({ error: 'Stripe membership secrets are not configured.' }, { status: 503 })
    }
    if (!stripeSecretMatchesMode(stripeSecret)) {
      console.error(`create-checkout Stripe mode mismatch: expected ${STRIPE_MODE}`)
      return Response.json({ error: 'Stripe payment mode is not configured safely.' }, { status: 503 })
    }

    let body: { plan?: string; return_path?: string; partner?: string }
    try {
      body = await req.json()
    } catch {
      return Response.json({ error: 'Invalid request body.' }, { status: 400 })
    }

    const plan = String(body.plan ?? '').toLowerCase()
    const priceId = priceForPlan(plan)
    if (!priceId) return Response.json({ error: 'Plan must be monthly or annual.' }, { status: 400 })

    const returnPath = safeReturnPath(body.return_path)
    const next = encodeURIComponent(returnPath)
    const partnerOffer = partnerOfferFor(body.partner)
    const partnerCoupon = partnerOffer && plan === 'monthly' ? partnerOffer.coupon : ''
    const discounts = partnerCoupon
      ? [{ coupon: partnerCoupon }]
      : plan === 'monthly'
        ? [{ coupon: MONTHLY_INTRO_COUPON }]
        : undefined
    const introductoryOffer = partnerCoupon
      ? 'partner_free_first_month'
      : plan === 'monthly'
        ? 'first_month_1_usd'
        : 'none'
    const checkoutPath = partnerOffer?.landingPath ?? '/subscribe.html'
    const partnerMetadata = partnerOffer
      ? { partner: partnerOffer.id, partner_name: partnerOffer.name }
      : {}

    try {
      const session = await stripe.checkout.sessions.create({
        mode: 'subscription',
        payment_method_collection: 'always',
        name_collection: { individual: { enabled: true, optional: false } },
        line_items: [{ price: priceId, quantity: 1 }],
        success_url: `${siteUrl}${checkoutPath}?checkout=success&session_id={CHECKOUT_SESSION_ID}&next=${next}`,
        cancel_url: `${siteUrl}${checkoutPath}?checkout=cancelled&next=${next}`,
        discounts,
        metadata: {
          plan,
          return_path: returnPath,
          tct_stripe_mode: STRIPE_MODE,
          introductory_offer: introductoryOffer,
          ...partnerMetadata,
        },
        subscription_data: {
          metadata: {
            plan,
            tct_stripe_mode: STRIPE_MODE,
            introductory_offer: introductoryOffer,
            ...partnerMetadata,
          },
        },
      })
      if (!session.url) throw new Error('Stripe did not return a Checkout URL.')
      return Response.json({ url: session.url })
    } catch (error) {
      console.error('create-checkout Stripe error', error)
      return Response.json({ error: 'Unable to start Stripe Checkout.' }, { status: 502 })
    }
  }),
}
