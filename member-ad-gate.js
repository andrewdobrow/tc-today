/* TCT: do not initialize Mediavine for paid-through legacy subscribers.
 * This is a client-side ad-loading gate, not an entitlement authority.
 * Authentication and subscription status remain verified by Supabase.
 */
(function () {
  'use strict'
  const gateScript = document.currentScript
  const mediavineUrl = gateScript?.getAttribute('data-tct-mediavine-src') || ''
  let started = false

  function startAds() {
    if (started || !mediavineUrl) return
    started = true
    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.async = true
    script.setAttribute('data-noptimize', '1')
    script.setAttribute('data-cfasync', 'false')
    script.src = mediavineUrl
    document.head.appendChild(script)
  }

  function possibleSignedInReader() {
    // Supabase JS persists signed-in sessions as sb-<project-ref>-auth-token.
    // Do not inspect/read/export token contents. An unverified member hint
    // delays ads only until the server makes the final entitlement decision.
    try {
      if (localStorage.getItem('tct_member_entitled_hint') === '1') return true
      for (let i = 0; i < localStorage.length; i++) {
        if (/^sb-[a-z0-9]+-auth-token$/i.test(String(localStorage.key(i) || ''))) return true
      }
    } catch (_) {
      // If storage is inaccessible, wait for membership.js rather than
      // risk loading ads ahead of verification for a paid reader.
      return true
    }
    return false
  }

  function arrivingFromSignIn() {
    try {
      const search = new URLSearchParams(location.search)
      const fragment = new URLSearchParams(location.hash.replace(/^#/, ''))
      return search.has('code') || search.has('token_hash') ||
        fragment.has('access_token') || fragment.has('refresh_token')
    } catch (_) {
      return false
    }
  }

  // A reader who signs in after ads were already loaded needs a fresh page.
  // Static Mediavine placements cannot be reliably un-initialized in place.
  function reloadOnceForNewMember() {
    try {
      if (sessionStorage.getItem('tct_ad_free_reload_once') === '1') return
      sessionStorage.setItem('tct_ad_free_reload_once', '1')
    } catch (_) { /* location.reload() still safe: one reload per document */ }
    location.reload()
  }

  window.TCTMemberAdGate = Object.freeze({
    resolve(status) {
      const entitled = Boolean(status?.authenticated && status?.entitled)
      if (entitled) {
        if (started) reloadOnceForNewMember()
        return
      }
      // An entitlement-service outage is not an authoritative denial.
      // Keep pending signed-in readers ad-free until their status is known.
      if (status?.authenticated && status?.error) return
      startAds()
    },
    get hasStarted() { return started },
  })

  if (!possibleSignedInReader() && !arrivingFromSignIn()) {
    try { sessionStorage.removeItem('tct_ad_free_reload_once') } catch (_) {}
    startAds()
  }
})()
