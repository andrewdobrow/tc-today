import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { webcrypto, generateKeyPairSync } from 'node:crypto'

const code = readFileSync(new URL('../supabase/functions/push-dispatch/index.ts', import.meta.url), 'utf8')
  .replace(/^import \{ createClient \} from 'npm:@supabase\/supabase-js@\^2'\s*/, '')
const secret = 'c'.repeat(64)
const token = 'ac'.repeat(32)
const slug = '2026-10-11-stuart-city-council-review'
const { privateKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' })
const p8base64 = Buffer.from(privateKey.export({ type: 'pkcs8', format: 'pem' })).toString('base64')

function environment({ live = false, devices = [], articleLive = true, appleStatus = 200, envOverrides = {} } = {}) {
  const dbRows = new Map()
  const calls = { apple: [], head: [], registrations: [], inserts: [], updates: [] }
  const query = (table) => {
    const filters = []
    let limit = null
    let updates = null
    let selectCols = ''
    function retrieve() {
      if (table === 'ios_push_dispatches') {
        const candidates = [...dbRows.values()].filter(row => filters.every(([name, value]) => row[name] === value))
        return { data: candidates[0] ?? null, error: null }
      }
      return { data: devices.filter(row => filters.every(([name, value]) => row[name] === value))
        .filter(row => !!row.apns_token)
        .slice(0, limit === null ? undefined : limit + 1), error: null }
    }
    const obj = {
      select(cols) { selectCols = cols; return obj },
      eq(name, value) { filters.push([name, value]); return obj },
      not() { return obj },
      range(_start, end) { limit = end; return obj },
      maybeSingle() { return Promise.resolve(retrieve()) },
      insert(value) {
        calls.inserts.push({ table, value })
        if (dbRows.has(value.slug)) return Promise.resolve({ error: { code: '23505' } })
        dbRows.set(value.slug, { ...value })
        return Promise.resolve({ error: null })
      },
      update(value) { updates = value; return obj },
      then(resolve, reject) {
        if (updates) {
          calls.updates.push({ table, value: updates })
          if (table === 'ios_push_dispatches') {
            const row = dbRows.get(filters.find(([n])=>n==='slug')?.[1]); if (row) Object.assign(row, updates)
          }
          return Promise.resolve({ error: null }).then(resolve, reject)
        }
        return Promise.resolve(retrieve()).then(resolve, reject)
      }
    }
    return obj
  }
  let handler
  const environmentVars = {
    SUPABASE_URL: 'https://project.supabase.co',
    SUPABASE_SERVICE_ROLE_KEY: 'server-only-placeholder',
    TCT_PUSH_DISPATCH_KEY: secret,
    TCT_PUSH_SENDING_ENABLED: live ? 'true' : 'false',
    TCT_APNS_KEY_ID: 'ABCDEFGHIJ',
    TCT_APNS_TEAM_ID: 'ZYXWVUTSRQ',
    TCT_APNS_P8_BASE64: p8base64,
    ...envOverrides,
  }
  const fakeFetch = async (url, options={}) => {
    if (String(url).startsWith('https://treasurecoast.today/')) {
      calls.head.push({ url, options })
      return { status: articleLive ? 200 : 404, url: String(url) }
    }
    assert.match(String(url), /^https:\/\/api\.push\.apple\.com\/3\/device\//)
    calls.apple.push({ url, options })
    if (appleStatus === 200) return { status: 200 }
    return { status: appleStatus, json: async () => ({ reason: appleStatus === 410 ? 'Unregistered' : 'BadDeviceToken' }) }
  }
  const context = vm.createContext({
    createClient: () => ({ from: query }),
    Deno: { env: { get(name) { return environmentVars[name] } }, serve(fn) { handler = fn } },
    fetch: fakeFetch,
    crypto: webcrypto, Response, TextEncoder, Uint8Array, Set,
    URL, btoa, atob, Date, AbortSignal, console,
  })
  vm.runInContext(code, context)
  async function request(args, opts={}) {
    const body = JSON.stringify({ action: 'preview', audience: 'martin', slug, title: 'Stuart City Council', body: 'A local government update.', ...args })
    const response = await handler(new Request('https://example.test/', {
      method: opts.method ?? 'POST',
      headers: { 'content-type': 'application/json', 'x-tct-push-dispatch-key': opts.key ?? secret },
      body: (opts.method ?? 'POST') === 'POST' ? body : undefined,
    }))
    return { status: response.status, body: await response.json() }
  }
  return { request, calls, dbRows, environmentVars }
}
const oneDevice = () => ({ installation_id: 'aaa', apns_token: token, environment:'production', enabled:true, breaking:true, martin:true, st_lucie:false, indian_river:false })

test('unauthorized requests never disclose registry or send', async () => {
  const system = environment({ devices: [oneDevice()] })
  const response = await system.request({}, { key: '0'.repeat(64) })
  assert.equal(response.status, 401)
  assert.equal(system.calls.head.length, 0)
  assert.equal(system.calls.apple.length, 0)
})
test('non-POST request rejected', async () => {
  const { request } = environment()
  assert.equal((await request({}, {method:'GET'})).status,405)
})
test('preview is safe, with audience filter, no ledger, and live sending off', async () => {
  const system = environment({devices:[oneDevice()]})
  const response = await system.request({})
  assert.equal(response.status,200)
  assert.equal(response.body.eligible_devices,1)
  assert.equal(response.body.sending_enabled,false)
  assert.equal(system.dbRows.size,0)
  assert.equal(system.calls.apple.length,0)
})
test('disabled sender and missing confirmation do not reserve a dispatch', async () => {
  let system= environment({devices:[oneDevice()]})
  assert.equal((await system.request({action:'send',confirm:'SEND'})).status,403)
  assert.equal(system.dbRows.size,0)
  system= environment({devices:[oneDevice()],live:true})
  assert.equal((await system.request({action:'send',confirm:'NO'})).status,400)
  assert.equal(system.dbRows.size,0)
})
test('nonexistent story cannot be sent', async () => {
  const system = environment({live:true,devices:[oneDevice()],articleLive:false})
  assert.equal((await system.request({action:'send',confirm:'SEND'})).status,422)
  assert.equal(system.dbRows.size,0)
})
test('accepted APNs delivery uses production endpoint, Apple JWT and app slug; second send blocked', async () => {
  const system = environment({live:true,devices:[oneDevice()]})
  const response = await system.request({action:'send',confirm:'SEND'})
  assert.equal(response.status,200)
  assert.equal(response.body.accepted_by_apns,1)
  assert.equal(response.body.ledger_saved,true)
  assert.equal(system.dbRows.get(slug).status,'completed')
  const apple = system.calls.apple[0]
  assert.match(apple.url,/^https:\/\/api\.push\.apple\.com/)
  assert.equal(apple.options.headers['apns-topic'],'com.treasurecoast.today.ios')
  assert.equal(JSON.parse(apple.options.body).slug,slug)
  const [header,payload,sig] = apple.options.headers.authorization.substring(7).split('.')
  assert.equal(JSON.parse(Buffer.from(header,'base64url')).alg, 'ES256')
  assert.equal(JSON.parse(Buffer.from(payload,'base64url')).iss, 'ZYXWVUTSRQ')
  assert.equal(Buffer.from(sig,'base64url').length,64)
  const again = await system.request({action:'send',confirm:'SEND',audience:'breaking'})
  assert.equal(again.status,409)
  assert.equal(system.calls.apple.length,1)
})
test('permanent APNs rejection deactivates invalid token', async () => {
  const system = environment({live:true,devices:[oneDevice()],appleStatus:410})
  const response = await system.request({action:'send',confirm:'SEND'})
  assert.equal(response.status,200)
  assert.equal(response.body.rejected_by_apns,1)
  assert.equal(system.dbRows.get(slug).status,'partial')
  assert.equal(system.calls.updates.some(x=>x.table==='ios_push_devices' && x.value.enabled===false), true)
})
test('bad APNs private key prevents reservation or send', async () => {
  const system = environment({live:true,devices:[oneDevice()],envOverrides:{TCT_APNS_P8_BASE64:'invalid'}})
  const response=await system.request({action:'send',confirm:'SEND'})
  assert.equal(response.status,503)
  assert.equal(system.dbRows.size,0)
})
test('too many matching devices stops instead of sending only a subset', async () => {
  const devices = Array.from({length:51},(_,i)=>({...oneDevice(),installation_id:`id-${i}`,apns_token:(i.toString(16).padStart(2,'0')).repeat(32)}))
  const system=environment({live:true,devices})
  const response=await system.request({action:'send',confirm:'SEND'})
  assert.equal(response.status,409)
  assert.equal(system.calls.apple.length,0)
  assert.equal(system.dbRows.size,0)
})
test('invalid slug and audience never reach API or database', async () => {
  const system=environment({live:true,devices:[oneDevice()]})
  assert.equal((await system.request({slug:'https://evil.example/path'})).status,400)
  assert.equal((await system.request({audience:'everyone'})).status,400)
  assert.equal(system.calls.head.length,0)
  assert.equal(system.dbRows.size,0)
})
