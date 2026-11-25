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

    def test_development_scope_reserves_distinct_requests_within_signed_templates(self):
        with TemporaryDirectory() as directory:
            policy=OwnerOperatingPolicy(Path(directory)/'scope',{'project':'fixture'})
            template=dict(id='model',model='fixture',endpoint='https://example.test',data_types=['public'],max_cost_usd=0)
            proposal=dict(policy.proposal([template]),mode='development_scope')
            key='fixture-key'
            policy.approve(proposal,digest(proposal),key)
            first={**template,'id':'model:1'}
            second={**template,'id':'model:2'}
            for change in (dict(endpoint='https://elsewhere.test'),dict(data_types=['private']),
                           dict(max_cost_usd=1),dict(id='unknown:1'),dict(model='other')):
                with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                    policy.reserve(key,{**first,**change},digest(change))
            reservation=policy.reserve(key,first,digest('first'))
            with self.assertRaisesRegex(CompanyError,'owner_policy_unresolved_attempt'):
                policy.reserve(key,second,digest('second'))
            policy.finish(reservation,'completed')
            with self.assertRaisesRegex(CompanyError,'owner_policy_replay'):
                policy.reserve(key,second,digest('first'))
            reservation=policy.reserve(key,second,digest('second'))
            policy.finish(reservation,'failed_or_uncertain')
            with self.assertRaisesRegex(CompanyError,'owner_policy_unresolved_attempt'):
                policy.reserve(key,{**template,'id':'model:3'},digest('third'))
            self.assertEqual(set(policy.attempts()),{'model:1','model:2'})

    def test_quality_followup_requires_explicit_opt_in_and_completed_bound_report(self):
        from research_quality_loop import followup_offer, offer

        with TemporaryDirectory() as directory:
            root=Path(directory)
            person='same-project'
            source=OwnerOperatingPolicy(root/'source',{'project':person,'input_sha256':'old'})
            target=OwnerOperatingPolicy(root/'target',{'project':person,'input_sha256':'new'})
            prior=dict(sha256='finished-report',staff={'observations':[]},manager={'action':'hold'})
            legacy=OwnerOperatingPolicy(root/'legacy',{'project':person,'input_sha256':'legacy'})
            legacy_offer=offer(legacy,{'sha256':'starting-report'})
            legacy.approve(legacy_offer,digest(legacy_offer),'fixture-key')
            self.assertIsNone(followup_offer(target,prior,legacy,'fixture-key'))
            proposal=dict(offer(source,{'sha256':'starting-report'}),followup_scope='same_project')
            source.approve(proposal,digest(proposal),'fixture-key')
            with self.assertRaisesRegex(CompanyError,'research_continuation_blocked'):
                followup_offer(target,prior,source,'fixture-key')
            source.write('quality-outcome.json',dict(reason='hold'))
            source.write('manager-review.json',dict(result_sha256=digest(prior['staff']),decision=prior['manager']))
            authorized,expiry=followup_offer(target,prior,source,'fixture-key')
            self.assertEqual(authorized['units'],proposal['units'])
            self.assertEqual(authorized['prior_report_sha256'],'finished-report')
            self.assertEqual(authorized['development_parent_input_sha256'],'old')
            self.assertEqual(expiry,source.read('policy.json')['expires_at'])
            with self.assertRaisesRegex(CompanyError,'owner_policy_key_changed'):
                followup_offer(target,prior,source,'other-key')
            with self.assertRaisesRegex(CompanyError,'research_continuation_blocked'):
                followup_offer(target,{**prior,'staff':{'observations':['changed']}},source,'fixture-key')
            source.revoke()
            with self.assertRaisesRegex(CompanyError,'owner_policy_revoked'):
                followup_offer(target,prior,source,'fixture-key')
