/**
 * global-teardown.production.ts
 *
 * Runs after all production tests complete.
 * Deletes the throw-away test account created by auth.setup.ts so the
 * production Supabase project doesn't accumulate stale test users.
 */
import * as fs from 'fs'
import * as path from 'path'

const META_FILE    = path.join(__dirname, '.auth/prod-test-meta.json')
const SUPABASE_URL = (process.env.SUPABASE_URL  ?? 'https://vigtvsdwbkspkqohvjna.supabase.co').replace(/\/$/, '')
const SERVICE_KEY  = process.env.SUPABASE_SERVICE_KEY ?? ''

export default async function globalTeardown() {
  if (!fs.existsSync(META_FILE)) {
    console.log('Teardown: no meta file found, skipping cleanup')
    return
  }

  let userId: string
  let email: string
  try {
    const meta = JSON.parse(fs.readFileSync(META_FILE, 'utf-8'))
    userId = meta.userId
    email  = meta.email
  } catch {
    console.warn('Teardown: could not parse meta file, skipping cleanup')
    return
  }

  if (!SERVICE_KEY) {
    console.warn('Teardown: SUPABASE_SERVICE_KEY not set — test user NOT deleted:', email)
    return
  }

  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${SERVICE_KEY}`,
        'apikey': SERVICE_KEY,
      },
    })

    if (res.ok) {
      console.log(`Teardown: deleted test user ${email} (${userId})`)
    } else {
      console.warn(`Teardown: delete returned ${res.status} for ${email}: ${await res.text()}`)
    }
  } catch (err) {
    console.warn('Teardown: failed to delete test user:', err)
  }

  // Remove meta file regardless of delete outcome
  fs.unlinkSync(META_FILE)
}
