"""Static safety contracts for the isolated v0.7 iOS push-device backend."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT/'supabase/migrations/202610110001_ios_push_device_registry.sql').read_text()
HANDLER = (ROOT/'supabase/functions/push-device/index.ts').read_text()
CONFIG_SCRIPT = (ROOT/'scripts/configure_ios_push.ps1').read_text()
WF = (ROOT/'.github/workflows/deploy-ios-push-device.yml').read_text()

class PushDeviceContracts(unittest.TestCase):
    def test_inert_database_registry(self):
        self.assertIn('create table if not exists public.ios_push_devices', SQL)
        self.assertIn('alter table public.ios_push_devices enable row level security', SQL)
        self.assertIn('revoke all on public.ios_push_devices from anon, authenticated', SQL)
        self.assertNotIn('create trigger', SQL.lower())
        self.assertNotIn('subscriptions', SQL.lower())
        self.assertNotIn('stripe', SQL.lower())

    def test_app_secret_is_hashed_and_ownership_checked(self):
        self.assertIn("crypto.subtle.digest('SHA-256'", HANDLER)
        self.assertIn('sameHash(existing.registration_secret_hash, digest)', HANDLER)
        self.assertIn('existing && !sameHash', HANDLER)
        self.assertIn('if (action === \'disable\')', HANDLER)
        self.assertIn('apns_token: null', HANDLER)

    def test_input_validation_and_send_disabled(self):
        self.assertIn('text.length > 4096', HANDLER)
        self.assertIn('tokenRe.test(input.apns_token)', HANDLER)
        self.assertIn("input.environment !== 'sandbox'", HANDLER)
        self.assertIn('readPreferences(input.preferences)', HANDLER)
        self.assertIn('digest: false', HANDLER)
        self.assertNotIn('api.push.apple.com', HANDLER)
        self.assertNotIn('APNS_PRIVATE_KEY', HANDLER)

    def test_deploys_only_one_function(self):
        self.assertIn('[functions.push-device]', CONFIG_SCRIPT)
        self.assertIn('verify_jwt = false', CONFIG_SCRIPT)
        self.assertIn('supabase functions deploy push-device --use-api', WF)
        self.assertNotIn('functions deploy --use-api --project-ref', WF)
        self.assertNotIn('supabase db push', WF)

if __name__ == '__main__': unittest.main()
