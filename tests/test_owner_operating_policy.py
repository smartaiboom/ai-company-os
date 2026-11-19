from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, digest
from owner_operating_policy import OwnerOperatingPolicy


class OwnerOperatingPolicyTests(TestCase):
    def test_scope_cost_key_expiry_revocation_and_unresolved_reservations(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)/'delegation'
            policy=OwnerOperatingPolicy(root,{'project':'fixture','provider':'fixture'})
            unit={'id':'voice:scene-2','model':'fixture-v1','max_cost_usd':0}
            second={**unit,'id':'voice:scene-3'}
            proposal=policy.proposal([unit,second])
            self.assertFalse(root.exists())
            with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                policy.approve(proposal,'wrong','fixture-key')
            policy.approve(proposal,digest(proposal),'fixture-key')
            for out_of_scope in ({**unit,'model':'different-model'}, {**unit,'max_cost_usd':1},
                                 {**unit,'id':'voice:scene-4'}):
                with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                    policy.reserve('fixture-key',out_of_scope,'payload')
            with self.assertRaisesRegex(CompanyError,'owner_policy_key_changed'):
                policy.reserve('another-key',unit,'payload')
            with patch('owner_operating_policy.now',return_value='2099-01-01T00:00:00+09:00'):
                with self.assertRaisesRegex(CompanyError,'owner_policy_expired'):
                    policy.reserve('fixture-key',unit,'payload')
            reservation=policy.reserve('fixture-key',unit,'payload-1')
            with self.assertRaisesRegex(CompanyError,'owner_policy_unresolved_attempt'):
                policy.reserve('fixture-key',second,'payload-2')
            policy.finish(reservation,'completed')
            with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                policy.reserve('fixture-key',unit,'payload-1')
            policy.revoke()
            with self.assertRaisesRegex(CompanyError,'owner_policy_revoked'):
                policy.reserve('fixture-key',second,'payload-2')
            self.assertEqual(list(policy.attempts()),[unit['id']])
