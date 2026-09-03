import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'

const config = window.TCT_MEMBERSHIP_CONFIG || {}
const configured = Boolean(config.supabaseUrl && config.supabasePublishableKey)
const supabase = configured ? createClient(config.supabaseUrl, config.supabasePublishableKey) : null
let membershipStatusPromise = null

const MEMBER_HINT_KEY = 'tct_member_entitled_hint'
const METER_STATE_KEY = 'tct_monthly_free_article_v1'
const METER_PENDING_TTL_MS = 120000
const MONTHLY_FREE_NEWSLETTER_UID = '2865b8d821'
const MONTHLY_FREE_NEWSLETTER_SRC = 'https://treasure-coast-today.kit.com/2865b8d821/index.js'

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

async function membershipStatus(){
  if (!supabase) return null
  if (membershipStatusPromise) return membershipStatusPromise
  membershipStatusPromise = (async () => {
    const { data: { session } } = await supabase.auth.getSession()
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
  const { data:{session} } = await supabase.auth.getSession()
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

function placeMonthlyFreeNewsletter(){
  const articleRoot = qs('.article-main-column') || qs('.article-wrap') || document
  if (qs('[data-tct-monthly-free-newsletter]', articleRoot)) return false

  // Keep the Kit form outside .article-body so article typography cannot bleed
  // into the form. Split the unlocked story after paragraph two, but only when
  // the complete article has at least five top-level story paragraphs.
  const articleBody = qsa('.article-body', articleRoot).find(node =>
    !node.closest('.tct-member-only') && !node.classList.contains('tct-protected-content')
  )
  if (!articleBody) return false
  const paragraphs = Array.from(articleBody.children).filter(node => node.tagName === 'P')
  if (paragraphs.length <= 4) return false

  const secondParagraph = paragraphs[1]
  if (!secondParagraph) return false

  const continuation = document.createElement('div')
  continuation.className = articleBody.className
  continuation.classList.add('tct-monthly-free-continuation')
  continuation.setAttribute('data-tct-monthly-free-continuation', 'true')
  while (secondParagraph.nextSibling) continuation.appendChild(secondParagraph.nextSibling)

  const slot = document.createElement('aside')
  slot.className = 'newsletter-inline-slot newsletter-inline-slot--monthly-free'
  slot.setAttribute('aria-label', 'Subscribe to the Treasure Coast Morning Brief')
  slot.setAttribute('data-tct-monthly-free-newsletter', 'true')

  articleBody.insertAdjacentElement('afterend', continuation)
  articleBody.insertAdjacentElement('afterend', slot)

  const script = document.createElement('script')
  script.async = true
  script.setAttribute('data-uid', MONTHLY_FREE_NEWSLETTER_UID)
  script.src = MONTHLY_FREE_NEWSLETTER_SRC
  slot.appendChild(script)
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
  const boundary = qs('.newsletter-inline-slot--article', articleRoot) || qs('.article-share', articleRoot)
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

async function unlockArticle(statusOverride=null){
  const paywall = qs('[data-tct-paywall]')
  if (!paywall || !supabase) return
  const slug = paywall.dataset.slug
  const status = statusOverride || await membershipStatus()
  const plans = qs('[data-paywall-plans]', paywall)
  const message = qs('.membership-message', paywall)

  if (status?.authenticated && status?.entitled) {
    setMessage(message, 'Unlocking article…')
    const { data, error } = await supabase.functions.invoke('protected-article', { body: { slug } })
    if (error || !data?.protected_body) {
      endMemberPrepaint()
      endMeterPrepaint()
      setMessage(message, `We couldn't load the member portion of this article. ${data?.error || error?.message || ''}`.trim(), true)
      return
    }
    renderProtectedBody(String(data.protected_body || ''), paywall, 'member')
    endMemberPrepaint()
    endMeterPrepaint()
    return
  }

  // Non-members get one complete article per calendar month. The browser reserves
  // the slug synchronously before the network request so two ordinary tabs cannot
  // casually claim two different articles at once. The server-signed token remains
  // the authority for subsequent requests.
  const reservation = reserveMeterArticle(slug)
  if (!reservation.allowed) {
    endMemberPrepaint()
    endMeterPrepaint()
    setMessage(message, '')
    plans?.classList.remove('hidden')
    setMeterPaywallState(paywall, reservation.state?.period || currentMeterPeriod(), false)
    return
  }

  const { data, error } = await supabase.functions.invoke('protected-article', {
    body: { slug, meter_token: reservation.meterToken || '' },
  })
  if (!error && data?.protected_body && data?.access === 'member') {
    clearPendingMeterFor(slug)
    setMemberHint(true)
    document.body.classList.add('tct-member-entitled')
    renderProtectedBody(String(data.protected_body || ''), paywall, 'member')
    endMemberPrepaint()
    endMeterPrepaint()
    return
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
      placeMonthlyFreeNewsletter()
      placePostReadMeterAfterStory(paywall)
      setMeterPaywallState(paywall, String(data.period || reservation.period || ''), true)
    }
    return
  }

  let errorPayload = null
  try {
    if (error?.context?.clone) errorPayload = await error.context.clone().json()
  } catch {}
  const serverCode = String(data?.code || errorPayload?.code || '')
  if (serverCode === 'FREE_ARTICLE_USED') {
    endMemberPrepaint()
    endMeterPrepaint()
    plans?.classList.remove('hidden')
    setMessage(message, '')
    setMeterPaywallState(paywall, String(data?.period || errorPayload?.period || reservation.state?.period || currentMeterPeriod()), false)
    return
  }

  clearPendingMeterFor(slug)
  endMemberPrepaint()
  endMeterPrepaint()
  plans?.classList.remove('hidden')
  if (status?.error) {
    setMessage(message, `Membership check failed: ${status.error}`, true)
  } else {
    setMessage(message, `We couldn't load your free article. ${data?.error || error?.message || ''}`.trim(), true)
  }
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
    invalidateMembershipStatus()
    const status = await membershipStatus()
    applySubscriberChrome(status)
    await refreshSubscribeAccount(status)
    await unlockArticle(status)
  }))
  revealRequestedSignIn()
  await finishCheckout()
  const initialStatus = await membershipStatus()
  applySubscriberChrome(initialStatus)
  await refreshSubscribeAccount(initialStatus)
  await unlockArticle(initialStatus)
  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT') setMemberHint(false)
    invalidateMembershipStatus()
    setTimeout(async () => {
      const status = await membershipStatus()
      applySubscriberChrome(status)
      await refreshSubscribeAccount(status)
      await unlockArticle(status)
    }, 0)
  })
}

const cancelled = new URLSearchParams(window.location.search).get('checkout') === 'cancelled'
if (cancelled) setMessage(qs('[data-membership-message]'), 'Checkout was cancelled. You were not charged.')
