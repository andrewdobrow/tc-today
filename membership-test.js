import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'

const config = window.TCT_MEMBERSHIP_CONFIG || {}
const warning = document.querySelector('#config-warning')
const signedOut = document.querySelector('#signed-out')
const signedIn = document.querySelector('#signed-in')
const plans = document.querySelector('#plans')
const accountEmail = document.querySelector('#account-email')
const statusBox = document.querySelector('#membership-status')

function setWarning(message) {
  warning.textContent = message
  warning.classList.toggle('hidden', !message)
}

if (!config.supabaseUrl || !config.supabasePublishableKey) {
  setWarning('Membership browser configuration is missing. Set the GitHub repository variables TCT_SUPABASE_URL and TCT_SUPABASE_PUBLISHABLE_KEY, then run Update Treasure Coast Today once.')
  signedOut.classList.add('hidden')
  throw new Error('Missing membership browser configuration')
}

const supabase = createClient(config.supabaseUrl, config.supabasePublishableKey)

async function refreshUI() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) {
    signedOut.classList.remove('hidden')
    signedIn.classList.add('hidden')
    plans.classList.add('hidden')
    return
  }

  signedOut.classList.add('hidden')
  signedIn.classList.remove('hidden')
  accountEmail.textContent = session.user.email || 'Signed in'
  statusBox.textContent = 'Checking entitlement…'

  const { data, error } = await supabase.functions.invoke('membership-status')
  if (error) {
    statusBox.textContent = `Membership check failed: ${error.message}`
    plans.classList.remove('hidden')
    return
  }

  if (data.is_admin) {
    statusBox.textContent = 'ADMIN ACCESS — full membership entitlement without a Stripe subscription.'
    plans.classList.add('hidden')
  } else if (data.entitled) {
    const status = data.subscription?.status || 'active'
    statusBox.textContent = `MEMBER ACCESS — Stripe subscription status: ${status}`
    plans.classList.add('hidden')
  } else {
    statusBox.textContent = 'No active membership yet. Choose a sandbox plan below.'
    plans.classList.remove('hidden')
  }
}

document.querySelector('#magic-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const email = document.querySelector('#magic-email').value.trim()
  setWarning('Sending sign-in link…')
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${window.location.origin}/membership-test.html` },
  })
  setWarning(error ? `Sign-in link failed: ${error.message}` : 'Sign-in link sent. Check your email, then return here through the link.')
})

document.querySelector('#password-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  const email = document.querySelector('#password-email').value.trim()
  const password = document.querySelector('#password').value
  setWarning('Signing in…')
  const { error } = await supabase.auth.signInWithPassword({ email, password })
  setWarning(error ? `Password sign-in failed: ${error.message}` : '')
  if (!error) await refreshUI()
})

document.querySelector('#sign-out').addEventListener('click', async () => {
  await supabase.auth.signOut()
  setWarning('')
  await refreshUI()
})

document.querySelectorAll('.plan-button').forEach((button) => {
  button.addEventListener('click', async () => {
    const plan = button.dataset.plan
    button.disabled = true
    setWarning(`Starting ${plan} sandbox checkout…`)
    const { data, error } = await supabase.functions.invoke('create-checkout', { body: { plan } })
    button.disabled = false
    if (error || !data?.url) {
      setWarning(`Checkout failed: ${error?.message || data?.error || 'No Checkout URL returned.'}`)
      return
    }
    window.location.assign(data.url)
  })
})

supabase.auth.onAuthStateChange(() => {
  // Defer so auth callbacks do not recursively compete with session persistence.
  setTimeout(refreshUI, 0)
})

const checkoutState = new URLSearchParams(window.location.search).get('checkout')
if (checkoutState === 'success') setWarning('Stripe returned successfully. Waiting for the webhook-backed membership record…')
if (checkoutState === 'cancelled') setWarning('Sandbox checkout was cancelled. No membership change was made.')

await refreshUI()
