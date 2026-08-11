import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'

const config = window.TCT_MEMBERSHIP_CONFIG || {}
const configured = Boolean(config.supabaseUrl && config.supabasePublishableKey)
const supabase = configured ? createClient(config.supabaseUrl, config.supabasePublishableKey) : null

const MEMBER_HINT_KEY = 'tct_member_entitled_hint'
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

async function membershipStatus(){
  if (!supabase) return null
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
}

async function refreshSubscribeAccount(){
  const account = qs('[data-membership-account]')
  if (!account || !supabase) return
  const status = await membershipStatus()
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
  setMessage(message, 'Your 7-day free trial has started. Setting up your membership…')
  const { data, error } = await supabase.functions.invoke('checkout-complete', { body: { session_id: sessionId } })
  if (error || !data?.complete) {
    setMessage(message, `Your payment succeeded, but automatic sign-in setup needs another try. ${data?.error || error?.message || ''}`.trim(), true)
    return
  }
  setMessage(message, `Your 7-day free trial is active. We sent a secure sign-in link to ${data.email}. Open it to activate unlimited access on this device.`)
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

async function unlockArticle(){
  const paywall = qs('[data-tct-paywall]')
  if (!paywall || !supabase) return
  const slug = paywall.dataset.slug
  const status = await membershipStatus()
  const signin = qs('[data-paywall-signin]', paywall)
  const plans = qs('[data-paywall-plans]', paywall)
  const message = qs('.membership-message', paywall)
  if (!status?.authenticated) {
    signin?.classList.add('hidden')
    plans?.classList.remove('hidden')
    return
  }
  if (!status.entitled) {
    endMemberPrepaint()
    setMessage(message, status.error ? `Membership check failed: ${status.error}` : 'This signed-in account does not have an active membership.', Boolean(status.error))
    plans?.classList.remove('hidden')
    return
  }
  setMessage(message, 'Unlocking article…')
  const { data, error } = await supabase.functions.invoke('protected-article', { body: { slug } })
  if (error || !data?.protected_body) {
    // If protected content cannot be retrieved, restore the visible shell so the
    // member sees the error instead of being stranded on an apparently truncated article.
    endMemberPrepaint()
    setMessage(message, `We couldn't load the member portion of this article. ${data?.error || error?.message || ''}`.trim(), true)
    return
  }
  const protectedBody = String(data.protected_body || '')
  const fullBodyMarker = '<!--tct-full-article-v2-->'
  const preview = qs('.tct-member-preview')
  const memberOnly = paywall.closest('.tct-member-only')

  if (protectedBody.startsWith(fullBodyMarker) && preview) {
    preview.innerHTML = protectedBody.slice(fullBodyMarker.length).trim()
    preview.classList.remove('tct-member-preview')
    qs('.tct-preview-copy', preview)?.classList.remove('tct-preview-copy')
    memberOnly?.remove()
    endMemberPrepaint()
    return
  }

  // Backward-compatible unlock path for rows written before full-body payload v2.
  const target = qs('#tct-protected-content')
  if (target) {
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
  }
  qs('.tct-paywall-fade')?.remove()
  paywall.remove()
  endMemberPrepaint()
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
  qsa('[data-membership-message]').forEach(el => setMessage(el, 'Membership configuration is unavailable. Please try again shortly.', true))
} else {
  qsa('[data-plan]').forEach(button => button.addEventListener('click', () => startCheckout(button)))
  qsa('[data-signin-form]').forEach(form => form.addEventListener('submit', event => { event.preventDefault(); sendMagicLink(form) }))
  qsa('[data-reveal-signin]').forEach(button => button.addEventListener('click', () => revealSignIn(button)))
  qsa('[data-create-portal]').forEach(button => button.addEventListener('click', () => openPortal(button)))
  qsa('[data-sign-out]').forEach(button => button.addEventListener('click', async () => { await supabase.auth.signOut(); setMemberHint(false); await refreshSubscribeAccount(); await unlockArticle() }))
  revealRequestedSignIn()
  await finishCheckout()
  await refreshSubscribeAccount()
  await unlockArticle()
  supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT') setMemberHint(false)
    setTimeout(async () => { await refreshSubscribeAccount(); await unlockArticle() }, 0)
  })
}

const cancelled = new URLSearchParams(window.location.search).get('checkout') === 'cancelled'
if (cancelled) setMessage(qs('[data-membership-message]'), 'Checkout was cancelled. You were not charged.')
