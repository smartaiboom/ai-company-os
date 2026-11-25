from unittest import TestCase

from autonomous_company import CompanyError
from task_replanning import approach_key, completion_record, completion_snapshot, verify_judgment


class GroundedJudgmentTests(TestCase):
    def setUp(self):
        self.snapshot = completion_snapshot([
            dict(id='invoice_corroboration', state='unmet', target=2, observed=1, source_ids=['receipt-1']),
        ], ['document_search'])
        self.facts = dict(snapshot_sha256=self.snapshot['sha256'], criteria={
            'invoice_corroboration': dict(state='unmet', observed=1, source_ids=['receipt-1']),
        })

    def test_fact_counts_states_and_citations_are_bound(self):
        verify_judgment(self.facts, self.snapshot)
        for changes in (dict(observed=2), dict(state='met'), dict(source_ids=['invented'])):
            with self.subTest(changes=changes), self.assertRaisesRegex(CompanyError, 'judgment_facts_mismatch'):
                row = {**self.facts['criteria']['invoice_corroboration'], **changes}
                verify_judgment({**self.facts, 'criteria': {'invoice_corroboration':row}}, self.snapshot)

    def test_early_completion_is_reviewable_but_false_success_is_blocked(self):
        value = dict(stop_reason='manager_review', explanation='The referenced invoice needs another source.')
        record = completion_record(value,self.snapshot,[dict(tool='document_search',status='empty')])
        self.assertTrue(record['reviewer_attention'])
        self.assertEqual(record['remaining'],['invoice_corroboration'])
        with self.assertRaisesRegex(CompanyError,'judgment_premature_completion'):
            completion_record({**value,'stop_reason':'criteria_met'},self.snapshot,[])
        unavailable = completion_snapshot([
            dict(id='invoice_corroboration',state='unmet',target=2,observed=1,source_ids=['receipt-1']),
        ], [])
        self.assertFalse(completion_record({**value,'stop_reason':'access_limited'},unavailable,[])['reviewer_attention'])

    def test_approach_identity_compares_the_actual_action(self):
        previous = dict(tool='document_search',option=' invoice  registry ',expected_gain='primary record')
        self.assertEqual(approach_key(previous),approach_key({**previous,'expected_gain':'better explanation'}))
        self.assertNotEqual(approach_key(previous),approach_key({**previous,'option':'archive index'}))
