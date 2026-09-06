import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'

const config = window.TCT_MEMBERSHIP_CONFIG || {}
const configured = Boolean(config.supabaseUrl && config.supabasePublishableKey)
const supabase = configured ? createClient(config.supabaseUrl, config.supabasePublishableKey) : null
let membershipStatusPromise = null
let authSessionPromise = null

const MEMBER_HINT_KEY = 'tct_member_entitled_hint'
const METER_STATE_KEY = 'tct_monthly_free_article_v1'
const METER_PENDING_TTL_MS = 120000
const FULL_ARTICLE_NEWSLETTER_UID = '30e15672d3'
const FULL_ARTICLE_NEWSLETTER_SRC = 'https://treasure-coast-today.kit.com/30e15672d3/index.js'
const FREE_ARTICLE_BANNER_DISMISS_PREFIX = 'tct_free_article_banner_dismissed_v1:'
const FREE_ARTICLE_BANNER_DELAY_MS = 1750
const FREE_ARTICLE_BANNER_SCROLL_PX = 120

function setMemberHint(entitled){
  try {
    if (entitled) localStorage.setItem(MEMBER_HINT_KEY, '1')
    else localStorage.removeItem(MEMBER_HINT_KEY)
  } catch {}
  document.documentElement.classList.toggle('tct-member-preverified', Boolean(entitled))
}
function endMemberPrepaint(){
  document.documentElement.classList.remove('tct-member-preverified')
}
function endMeterPrepaint(){
  document.documentElement.classList.remove('tct-meter-precheck')
}
function currentMeterPeriod(){
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      year: 'numeric',
      month: '2-digit',
    }).formatToParts(new Date())
    const year = parts.find(part => part.type === 'year')?.value || ''
    const month = parts.find(part => part.type === 'month')?.value || ''
    return /^\d{4}$/.test(year) && /^\d{2}$/.test(month) ? `${year}-${month}` : ''
  } catch { return '' }
}
function readMeterState(){
  try {
    const raw = localStorage.getItem(METER_STATE_KEY)
    if (!raw) return null
    const state = JSON.parse(raw)
    if (!state || typeof state !== 'object') return null
    if (!/^\d{4}-\d{2}$/.test(String(state.period || ''))) return null
    if (!/^[a-z0-9][a-z0-9-]{2,180}$/.test(String(state.slug || ''))) return null
    if (state.pending && !state.meter_token && Date.now() - Number(state.started_at || 0) > METER_PENDING_TTL_MS) {
      localStorage.removeItem(METER_STATE_KEY)
      return null
    }
    return state
  } catch { return null }
}
function writeMeterState(state){
  try { localStorage.setItem(METER_STATE_KEY, JSON.stringify(state)) } catch {}
}
function clearPendingMeterFor(slug){
  const state = readMeterState()
  if (!state || state.slug !== slug || !state.pending || state.meter_token) return
  try { localStorage.removeItem(METER_STATE_KEY) } catch {}
}
function reserveMeterArticle(slug){
  const period = currentMeterPeriod()
  if (!period) return { allowed:false, state:null, reason:'period_unavailable' }
  const state = readMeterState()
  if (state?.period === period) {
    if (state.slug !== slug) return { allowed:false, state, reason:'already_used' }
    return { allowed:true, state, period, meterToken:String(state.meter_token || '') }
  }
  const pending = { period, slug, meter_token:'', pending:true, started_at:Date.now() }
  writeMeterState(pending)
  return { allowed:true, state:pending, period, meterToken:'' }
}
function monthNameForPeriod(period){
  const match = String(period || '').match(/^(\d{4})-(\d{2})$/)
  if (!match) return 'this month'
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1))
  return date.toLocaleString('en-US', { month:'long', timeZone:'UTC' })
}
function resetLabelForPeriod(period){
  const match = String(period || '').match(/^(\d{4})-(\d{2})$/)
  if (!match) return ''
  const next = new Date(Date.UTC(Number(match[1]), Number(match[2]), 1))
  return `Your free article resets ${next.toLocaleString('en-US', { month:'long', timeZone:'UTC' })} 1.`
}

if (config.paymentMode === 'test' || config.sandbox) {
  document.querySelector('[data-membership-sandbox]')?.classList.remove('hidden')
} else if (!config.uiEnabled) {
  document.querySelector('[data-membership-live-validation]')?.classList.remove('hidden')
}

function qs(sel, root=document){ return root.querySelector(sel) }
function qsa(sel, root=document){ return [...root.querySelectorAll(sel)] }
function safeNext(raw){
  try {
    if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return '/'
    const url = new URL(raw, window.location.origin)
    return url.origin === window.location.origin ? `${url.pathname}${url.search}${url.hash}` : '/'
  } catch { return '/' }
}
function setMessage(el, text, error=false){
  if (!el) return
  el.textContent = text || ''
  el.classList.toggle('hidden', !text)
  el.classList.toggle('error', Boolean(error))
}
function returnPathFor(button){
  const explicit = button?.dataset?.returnPath
  if (explicit) return safeNext(explicit)
  const next = new URLSearchParams(window.location.search).get('next')
  if (next) return safeNext(next)
  if (document.body.dataset.articleSlug) return window.location.pathname
  return '/'
}

async function startCheckout(button){
  if (!supabase) return
  const plan = button.dataset.plan
  const message = qs('[data-membership-message]') || qs('.membership-message', button.closest('.tct-paywall') || document)
  button.disabled = true
  setMessage(message, 'Opening secure Stripe checkout…')
  const { data, error } = await supabase.functions.invoke('create-checkout', {
    body: { plan, return_path: returnPathFor(button) },
  })
  button.disabled = false
  if (error || !data?.url) {
    setMessage(message, `Checkout failed: ${data?.error || error?.message || 'Please try again.'}`, true)
    return
  }
  window.location.assign(data.url)
}

async function sendMagicLink(form){
  if (!supabase) return
  const input = qs('input[type="email"]', form)
  const email = input?.value?.trim()
  const message = qs('.membership-message', form.parentElement) || qs('[data-membership-message]')
  if (!email) return
  const next = safeNext(form.dataset.returnPath || new URLSearchParams(location.search).get('next') || window.location.pathname)
  setMessage(message, 'Sending your secure sign-in link…')
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${window.location.origin}${next}`,
      shouldCreateUser: false,
    },
  })
  setMessage(message, error ? `Sign-in failed: ${error.message}` : 'Check your email for your secure sign-in link.', Boolean(error))
}

function invalidateMembershipStatus(){ membershipStatusPromise = null }
function invalidateAuthSession(){ authSessionPromise = null }

async function authSession(){
  if (!supabase) return null
  if (!authSessionPromise) authSessionPromise = supabase.auth.getSession()
  try {
    const result = await authSessionPromise
    return result?.data?.session || null
  } catch {
    return null
  }
}

async function membershipStatus(){
  if (!supabase) return null
  if (membershipStatusPromise) return membershipStatusPromise
  membershipStatusPromise = (async () => {
    const session = await authSession()
    if (!session) {
      setMemberHint(false)
      document.body.classList.remove('tct-member-entitled')
      return { authenticated:false, entitled:false }
    }
    const { data, error } = await supabase.functions.invoke('membership-status')
    if (error) {
      // A transport/backend failure is not an entitlement decision. Reveal the
      // normal paywall so its error state is visible, but keep the stored hint so
      // the next navigation can still avoid a flash after service recovers.
      endMemberPrepaint()
      return { authenticated:true, entitled:false, error:error.message }
    }
    const entitled = Boolean(data?.entitled)
    setMemberHint(entitled)
    document.body.classList.toggle('tct-member-entitled', entitled)
    return data
  })()
  return membershipStatusPromise
}

function statusWithArticleAuthority(status, articleResult){
  if (articleResult?.access === 'member') {
    return { ...(status || {}), authenticated:true, entitled:true }
  }
  return status
}

function applySubscriberChrome(status){
  const entitled = Boolean(status?.authenticated && status?.entitled)
  const firstName = String(status?.first_name || '').trim()
  qsa('[data-membership-welcome]').forEach(el => {
    el.textContent = entitled && firstName ? `Welcome, ${firstName}` : 'Welcome, subscriber'
  })
  document.body.classList.toggle('tct-member-entitled', entitled)
}

async function refreshSubscribeAccount(statusOverride=null){
  const account = qs('[data-membership-account]')
  if (!account || !supabase) return
  const status = statusOverride || await membershipStatus()
  const emailEl = qs('[data-account-email]', account)
  const statusEl = qs('[data-account-status]', account)
  const signedOut = qs('[data-signed-out]')
  const plans = qs('[data-membership-plans]')
  if (!status?.authenticated) {
    account.classList.add('hidden')
    signedOut?.classList.add('hidden')
    const checkoutSuccess = new URLSearchParams(window.location.search).get('checkout') === 'success'
    plans?.classList.toggle('hidden', checkoutSuccess)
    return
  }
  const session = await authSession()
  account.classList.remove('hidden')
  signedOut?.classList.add('hidden')
  if (emailEl) emailEl.textContent = session?.user?.email || ''
  if (status.entitled) {
    plans?.classList.add('hidden')
    if (statusEl) statusEl.textContent = status.is_admin ? 'Administrator access is active.' : 'Your Treasure Coast Today membership is active.'
  } else {
    plans?.classList.remove('hidden')
    if (statusEl) statusEl.textContent = status.error ? `Membership check failed: ${status.error}` : 'No active membership is attached to this account.'
  }
}

async function finishCheckout(){
  if (!supabase) return
  const params = new URLSearchParams(window.location.search)
  if (params.get('checkout') !== 'success') return
  const sessionId = params.get('session_id') || ''
  const message = qs('[data-membership-message]')
  if (!sessionId) { setMessage(message, 'Stripe returned without a Checkout session reference.', true); return }
  setMessage(message, 'Your payment was successful. Setting up your membership…')
  const { data, error } = await supabase.functions.invoke('checkout-complete', { body: { session_id: sessionId } })
  if (error || !data?.complete) {
    setMessage(message, `Your payment succeeded, but automatic sign-in setup needs another try. ${data?.error || error?.message || ''}`.trim(), true)
    return
  }
  const planMessage = data.plan === 'monthly'
    ? 'Your $1 first month is active.'
    : data.plan === 'annual'
      ? 'Your annual membership is active.'
      : 'Your membership is active.'
  setMessage(message, `${planMessage} We sent a secure sign-in link to ${data.email}. Open it to activate unlimited access on this device.`)
}

async function openPortal(button){
  if (!supabase) return
  button.disabled = true
  const message = qs('[data-membership-message]')
  setMessage(message, 'Opening billing management…')
  const { data, error } = await supabase.functions.invoke('create-portal')
  button.disabled = false
  if (error || !data?.url) { setMessage(message, `Billing management failed: ${data?.error || error?.message || 'Please try again.'}`, true); return }
  window.location.assign(data.url)
}

function removePostArticleNewsletter(){
  const articleRoot = qs('.article-main-column') || qs('.article-wrap') || document
  // Retain the real post-article Kit form. Only remove the obsolete dormant
  // paywall-only placeholder used by older generated pages.
  qsa('[data-tct-paywall-newsletter]', articleRoot).forEach(node => node.remove())
}

function showPaywallNewsletter(){
  const articleRoot = qs('.article-main-column') || qs('.article-wrap') || document
  if (qs('.newsletter-inline-slot--article', articleRoot)) return true
  const slot = qs('[data-tct-paywall-newsletter]', articleRoot)
  if (!slot) return false
  slot.hidden = false
  if (qs(`script[data-uid="${FULL_ARTICLE_NEWSLETTER_UID}"]`, slot)) return true
  const script = document.createElement('script')
  script.async = true
  script.setAttribute('data-uid', FULL_ARTICLE_NEWSLETTER_UID)
  script.src = FULL_ARTICLE_NEWSLETTER_SRC
  slot.appendChild(script)
  return true
}

function placeFullArticleNewsletter(){
  const articleRoot = qs('.article-main-column') || qs('.article-wrap') || document
  const existing = qs('.newsletter-inline-slot--article', articleRoot)
  if (existing) return true
  if (qs('[data-tct-full-article-newsletter]', articleRoot)) return false

  // Fallback for a retained/legacy page that somehow missed the static article
  // newsletter normalization. Keep the signup after all story paragraphs and
  // before any ancillary event-link/share treatment.
  const boundary = qs('.event-link-box', articleRoot) || qs('.article-share', articleRoot)
  const slot = document.createElement('aside')
  slot.className = 'newsletter-inline-slot newsletter-inline-slot--article newsletter-inline-slot--full-article'
  slot.setAttribute('aria-label', 'Subscribe to the Treasure Coast Morning Brief')
  slot.setAttribute('data-tct-full-article-newsletter', 'true')

  if (boundary?.parentElement) {
    boundary.parentElement.insertBefore(slot, boundary)
  } else {
    const articleBodies = qsa('.article-body', articleRoot).filter(node =>
      !node.closest('.tct-member-only') &&
      (!node.classList.contains('tct-protected-content') || node.classList.contains('is-unlocked'))
    )
    const lastBody = articleBodies[articleBodies.length - 1]
    if (!lastBody) return false
    lastBody.insertAdjacentElement('afterend', slot)
  }

  const script = document.createElement('script')
  script.async = true
  script.setAttribute('data-uid', FULL_ARTICLE_NEWSLETTER_UID)
  script.src = FULL_ARTICLE_NEWSLETTER_SRC
  slot.appendChild(script)
  return true
}


function freeArticleBannerDismissKey(slug, period){
  return `${FREE_ARTICLE_BANNER_DISMISS_PREFIX}${period}:${slug}`
}
function removeFreeArticleBanner(){
  const banner = qs('[data-tct-free-article-banner]')
  if (!banner) return
  if (typeof banner._tctCleanup === 'function') banner._tctCleanup()
  banner.classList.remove('is-visible')
  banner.setAttribute('aria-hidden', 'true')
  window.setTimeout(() => banner.remove(), 220)
}
function armFreeArticleBanner(slug, period, paywall){
  if (!slug || !period || qs('[data-tct-free-article-banner]')) return false
  const dismissKey = freeArticleBannerDismissKey(slug, period)
  try { if (sessionStorage.getItem(dismissKey) === '1') return false } catch {}

  const banner = document.createElement('aside')
  banner.className = 'tct-free-article-banner'
  banner.setAttribute('data-tct-free-article-banner', 'true')
  banner.setAttribute('aria-label', 'Free article notice')
  banner.setAttribute('aria-hidden', 'true')
  banner.innerHTML = `
    <div class="tct-free-article-banner-inner">
      <div class="tct-free-article-banner-monogram" aria-hidden="true">TCT</div>
      <div class="tct-free-article-banner-copy">
        <strong>You're reading your free article for this month.</strong>
      </div>
      <a class="tct-free-article-banner-cta" href="/subscribe.html">
        <span>Subscribe for unlimited access</span>
        <small>$1 first month</small>
      </a>
      <button class="tct-free-article-banner-dismiss" type="button" aria-label="Dismiss free article notice">&times;</button>
    </div>`
  document.body.appendChild(banner)

  const dismiss = qs('.tct-free-article-banner-dismiss', banner)
  dismiss?.addEventListener('click', () => {
    try { sessionStorage.setItem(dismissKey, '1') } catch {}
    removeFreeArticleBanner()
  })

  // The banner is informational, not the paywall itself. Surface it early once
  // the full monthly-free article has been delivered: after a short grace period
  // or a small amount of deliberate reading scroll, whichever happens first.
  const armedScrollY = window.scrollY
  let delayElapsed = false
  let reachedEnd = false
  let ticking = false
  let delayTimer = null

  const cleanup = () => {
    if (delayTimer !== null) {
      window.clearTimeout(delayTimer)
      delayTimer = null
    }
    window.removeEventListener('scroll', requestUpdate)
    window.removeEventListener('resize', requestUpdate)
  }
  banner._tctCleanup = cleanup

  const update = () => {
    ticking = false
    if (!banner.isConnected || reachedEnd) return
    const endVisible = Boolean(paywall && paywall.isConnected && paywall.getBoundingClientRect().top <= window.innerHeight - 24)
    if (endVisible) {
      reachedEnd = true
      banner.classList.remove('is-visible')
      banner.setAttribute('aria-hidden', 'true')
      cleanup()
      window.setTimeout(() => banner.remove(), 220)
      return
    }
    const scrolledEnough = Math.abs(window.scrollY - armedScrollY) >= FREE_ARTICLE_BANNER_SCROLL_PX
    const triggerReached = delayElapsed || scrolledEnough
    banner.classList.toggle('is-visible', triggerReached)
    banner.setAttribute('aria-hidden', triggerReached ? 'false' : 'true')
  }
  const requestUpdate = () => {
    if (ticking) return
    ticking = true
    window.requestAnimationFrame(update)
  }
  window.addEventListener('scroll', requestUpdate, { passive:true })
  window.addEventListener('resize', requestUpdate)
  delayTimer = window.setTimeout(() => {
    delayElapsed = true
    requestUpdate()
  }, FREE_ARTICLE_BANNER_DELAY_MS)
  requestUpdate()
  return true
}

function setMeterPaywallState(paywall, period, afterRead=false){
  if (!paywall) return
  const month = monthNameForPeriod(period)
  const status = qs('[data-meter-status]', paywall)
  const brand = qs('[data-paywall-brand]', paywall)
  const headline = qs('[data-paywall-headline]', paywall)
  const copy = qs('[data-paywall-copy]', paywall)
  const reset = qs('[data-meter-reset]', paywall)
  status?.classList.remove('hidden')
  if (status) status.textContent = afterRead ? `Your free article for ${month}` : '1 free article each month'
  if (brand) brand.textContent = 'Treasure Coast Today Membership'
  if (headline) headline.textContent = afterRead
    ? "You've read your free article this month."
    : 'Continue reading Treasure Coast Today for just $1.'
  if (copy) copy.textContent = afterRead
    ? 'Thanks for reading. Get unlimited, ad-free access to every Treasure Coast Today story and support independent local journalism.'
    : "You've read your free article this month. Get unlimited, ad-free access to every Treasure Coast Today story and support independent local journalism."
  if (reset) {
    reset.textContent = resetLabelForPeriod(period)
    reset.classList.toggle('hidden', !reset.textContent)
  }
  paywall.classList.toggle('tct-paywall-metered-after-read', afterRead)
  qs('.tct-paywall-fade', paywall.parentElement || document)?.remove()
}

function placePostReadMeterAfterStory(paywall){
  if (!paywall) return
  const memberOnly = paywall.closest('.tct-member-only')
  const articleRoot = paywall.closest('.article-main-column') || paywall.closest('.article-wrap') || document

  // Legacy protected rows can leave the unlocked continuation inside the same
  // wrapper as the paywall. Normalize that continuation back into the article
  // flow *before* moving the sales treatment, otherwise the card can sit between
  // the public preview and the rest of the now-free story.
  const unlockedTarget = qs('#tct-protected-content.is-unlocked', articleRoot)
  if (memberOnly && unlockedTarget && memberOnly.contains(unlockedTarget)) {
    memberOnly.parentElement?.insertBefore(unlockedTarget, memberOnly)
  }

  // The paywall itself -- not its wrapper -- belongs after all story content.
  // Prefer the stable post-story boundary. This remains correct even if a future
  // article shell contains multiple article-body blocks.
  const boundary = qs('.article-share', articleRoot)
  let placed = false
  if (boundary?.parentElement) {
    boundary.parentElement.insertBefore(paywall, boundary)
    placed = true
  } else {
    const bodies = qsa('.article-body', articleRoot).filter(node => !node.closest('.tct-member-only'))
    const lastBody = bodies[bodies.length - 1]
    if (lastBody) {
      lastBody.insertAdjacentElement('afterend', paywall)
      placed = true
    }
  }

  // The original wrapper is now only scaffolding (fade and/or an empty protected
  // target). Remove it only after the CTA has a proven destination.
  if (placed) memberOnly?.remove()
}

function renderProtectedBody(protectedBody, paywall, access){
  const fullBodyMarker = '<!--tct-full-article-v2-->'
  const preview = qs('.tct-member-preview')
  const memberOnly = paywall?.closest('.tct-member-only')

  if (protectedBody.startsWith(fullBodyMarker) && preview) {
    preview.innerHTML = protectedBody.slice(fullBodyMarker.length).trim()
    preview.classList.remove('tct-member-preview')
    qs('.tct-preview-copy', preview)?.classList.remove('tct-preview-copy')
    if (access === 'member') memberOnly?.remove()
    return true
  }

  // Backward-compatible unlock path for rows written before full-body payload v2.
  const target = qs('#tct-protected-content')
  if (!target) return false
  const holder = document.createElement('div')
  holder.innerHTML = protectedBody
  const continuation = qs('[data-tct-first-paragraph-continuation]', holder)
  const previewParagraph = qs('[data-tct-preview-paragraph]')
  if (continuation && previewParagraph) {
    const solid = qs('.tct-preview-solid', previewParagraph)?.textContent || ''
    const faded = qs('.tct-preview-fade-text', previewParagraph)?.textContent || ''
    const rest = continuation.textContent || ''
    previewParagraph.textContent = `${solid} ${faded} ${rest}`.replace(/\s+/g, ' ').trim()
    previewParagraph.removeAttribute('data-tct-preview-paragraph')
    continuation.remove()
  }
  target.innerHTML = holder.innerHTML
  target.classList.add('is-unlocked')
  if (access === 'monthly_free' && memberOnly && preview) {
    preview.insertAdjacentElement('afterend', target)
  } else if (access === 'member') {
    qs('.tct-paywall-fade')?.remove()
    paywall?.remove()
  }
  return true
}

async function unlockArticle(statusPromise=null){
  const paywall = qs('[data-tct-paywall]')
  if (!paywall || !supabase) return { access:'not_applicable' }
  const slug = paywall.dataset.slug
  const plans = qs('[data-paywall-plans]', paywall)
  const message = qs('.membership-message', paywall)

  // Resolve only the local Auth session before requesting protected content. This
  // restores Supabase's persisted access token but does not wait for the separate
  // membership-status Edge Function. protected-article performs its own server-side
  // entitlement check and is the authority for whether article content is returned.
  const session = await authSession()
  const reservation = reserveMeterArticle(slug)
  const existingMeterToken = String(reservation.meterToken || reservation.state?.meter_token || '')

  // Preserve the browser's same-month/two-tab reservation guard. An anonymous
  // reader whose free article is already reserved cannot send a second blank-token
  // request. An authenticated reader still gets a chance to prove membership.
  if (!reservation.allowed && !session) {
    removeFreeArticleBanner()
    endMemberPrepaint()
    endMeterPrepaint()
    setMessage(message, '')
    plans?.classList.remove('hidden')
    setMeterPaywallState(paywall, reservation.state?.period || currentMeterPeriod(), false)
    showPaywallNewsletter()
    return { access:'free_article_used_local' }
  }

  // The only path that still waits for membership-status is the rare race where
  // another tab has a pending free-article reservation but has not yet received a
  // signed meter token. This keeps the old anti-double-tab protection intact while
  // removing the serial status -> article request from ordinary page loads.
  if (!reservation.allowed && session && !existingMeterToken) {
    const status = statusPromise ? await statusPromise : await membershipStatus()
    if (!status?.authenticated || !status?.entitled) {
      removeFreeArticleBanner()
      endMemberPrepaint()
      endMeterPrepaint()
      setMessage(message, '')
      plans?.classList.remove('hidden')
      setMeterPaywallState(paywall, reservation.state?.period || currentMeterPeriod(), false)
      showPaywallNewsletter()
      return { access:'free_article_used_local' }
    }
  }

  if (session) setMessage(message, 'Unlocking article…')
  const { data, error } = await supabase.functions.invoke('protected-article', {
    body: { slug, meter_token: existingMeterToken },
  })

  // protected-article checks paid/admin entitlement before the monthly meter. A
  // successful member response therefore unlocks immediately without waiting for
  // membership-status, while the separate status request can update account chrome
  // in parallel.
  if (!error && data?.protected_body && data?.access === 'member') {
    removeFreeArticleBanner()
    clearPendingMeterFor(slug)
    setMemberHint(true)
    document.body.classList.add('tct-member-entitled')
    const rendered = renderProtectedBody(String(data.protected_body || ''), paywall, 'member')
    endMemberPrepaint()
    endMeterPrepaint()
    if (rendered) { removePostArticleNewsletter(); placeFullArticleNewsletter() }
    return { access:'member', rendered }
  }

  if (!error && data?.protected_body && data?.access === 'monthly_free') {
    writeMeterState({
      period: String(data.period || reservation.period || currentMeterPeriod()),
      slug,
      meter_token: String(data.meter_token || ''),
      pending: false,
      started_at: Date.now(),
    })
    const rendered = renderProtectedBody(String(data.protected_body || ''), paywall, 'monthly_free')
    endMemberPrepaint()
    endMeterPrepaint()
    setMessage(message, '')
    if (rendered) {
      removePostArticleNewsletter()
      placeFullArticleNewsletter()
      placePostReadMeterAfterStory(paywall)
      const meterPeriod = String(data.period || reservation.period || currentMeterPeriod())
      setMeterPaywallState(paywall, meterPeriod, true)
      armFreeArticleBanner(slug, meterPeriod, paywall)
    }
    return { access:'monthly_free', rendered }
  }

  let errorPayload = null
  try {
    if (error?.context?.clone) errorPayload = await error.context.clone().json()
  } catch {}
  const serverCode = String(data?.code || errorPayload?.code || '')
  if (serverCode === 'FREE_ARTICLE_USED') {
    removeFreeArticleBanner()
    endMemberPrepaint()
    endMeterPrepaint()
    plans?.classList.remove('hidden')
    setMessage(message, '')
    setMeterPaywallState(paywall, String(data?.period || errorPayload?.period || reservation.state?.period || currentMeterPeriod()), false)
    showPaywallNewsletter()
    return { access:'free_article_used' }
  }

  clearPendingMeterFor(slug)
  endMemberPrepaint()
  endMeterPrepaint()
  plans?.classList.remove('hidden')
  showPaywallNewsletter()
  setMessage(message, `We couldn't load this article. ${data?.error || error?.message || ''}`.trim(), true)
  return { access:'error', error:data?.error || error?.message || '' }
}

function revealSignIn(button){
  const root = button.closest('[data-tct-paywall]') || document
  qs('[data-paywall-signin]', root)?.classList.remove('hidden')
  qs('[data-paywall-signin] input[type="email"]', root)?.focus()
}

function revealRequestedSignIn(){
  const params = new URLSearchParams(window.location.search)
  if (params.get('signin') !== '1') return
  const trigger = qs('[data-reveal-signin]')
  if (trigger) revealSignIn(trigger)
}

if (!configured) {
  showPaywallNewsletter()
  endMeterPrepaint()
  qsa('[data-membership-message]').forEach(el => setMessage(el, 'Membership configuration is unavailable. Please try again shortly.', true))
} else {
  qsa('[data-plan]').forEach(button => button.addEventListener('click', () => startCheckout(button)))
  qsa('[data-signin-form]').forEach(form => form.addEventListener('submit', event => { event.preventDefault(); sendMagicLink(form) }))
  qsa('[data-reveal-signin]').forEach(button => button.addEventListener('click', () => revealSignIn(button)))
  qsa('[data-create-portal]').forEach(button => button.addEventListener('click', () => openPortal(button)))
  qsa('[data-sign-out]').forEach(button => button.addEventListener('click', async () => {
    await supabase.auth.signOut()
    setMemberHint(false)
    invalidateAuthSession()
    invalidateMembershipStatus()
    const statusPromise = membershipStatus()
    const articlePromise = unlockArticle(statusPromise)
    const [status, articleResult] = await Promise.all([statusPromise, articlePromise])
    const effectiveStatus = statusWithArticleAuthority(status, articleResult)
    applySubscriberChrome(effectiveStatus)
    await refreshSubscribeAccount(effectiveStatus)
  }))
  revealRequestedSignIn()
  await finishCheckout()

  // Start entitlement chrome and protected-content delivery together. Both share
  // the same local Auth-session restoration, but only protected-article gates the
  // article body. This removes a full sequential Edge Function round trip for
  // normal subscriber and monthly-free article loads.
  const initialStatusPromise = membershipStatus()
  const initialArticlePromise = unlockArticle(initialStatusPromise)
  const [initialStatus, initialArticleResult] = await Promise.all([initialStatusPromise, initialArticlePromise])
  const initialEffectiveStatus = statusWithArticleAuthority(initialStatus, initialArticleResult)
  applySubscriberChrome(initialEffectiveStatus)
  await refreshSubscribeAccount(initialEffectiveStatus)

  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT') setMemberHint(false)
    invalidateAuthSession()
    invalidateMembershipStatus()
    setTimeout(async () => {
      const statusPromise = membershipStatus()
      const articlePromise = unlockArticle(statusPromise)
      const [status, articleResult] = await Promise.all([statusPromise, articlePromise])
      const effectiveStatus = statusWithArticleAuthority(status, articleResult)
      applySubscriberChrome(effectiveStatus)
      await refreshSubscribeAccount(effectiveStatus)
    }, 0)
  })
}

const cancelled = new URLSearchParams(window.location.search).get('checkout') === 'cancelled'
if (cancelled) setMessage(qs('[data-membership-message]'), 'Checkout was cancelled. You were not charged.')
