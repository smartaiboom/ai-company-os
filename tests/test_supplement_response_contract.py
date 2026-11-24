from unittest import TestCase

from decision_recovery import DecisionViolation
from research_supplement import normalize_plan, validate_plan_assignment


class SupplementResponseContractTests(TestCase):
    def setUp(self):
        self.plan=dict(action='reinvestigate',tools=['youtube','web'],reason='근거 부족',
                       next_step='영상을 교차 확인합니다.',success_criteria='게임별 출처를 연결합니다.')

    def test_repairs_only_unambiguous_root_and_duplicate_tools(self):
        result=normalize_plan({**self.plan,'tools':['youtube','web','youtube']})
        self.assertEqual(result,{'decision':self.plan})
        validate_plan_assignment(result)

    def test_shape_rejects_unknown_fields_tools_and_missing_required_fields(self):
        missing={key:value for key,value in self.plan.items() if key!='next_step'}
        for value in (missing,{**self.plan,'tools':['forbidden']},{**self.plan,'private_value':'private content'}):
            with self.subTest(value=value), self.assertRaises(DecisionViolation) as exc:
                normalize_plan({'decision':value})
            self.assertEqual(exc.exception.rule,'supplement_plan_shape')
            self.assertNotIn('private',str(exc.exception.safe_shape))

    def test_assignment_rejects_meaning_changes_even_after_normalization(self):
        for changes in (dict(action='hold'),dict(tools=[]),dict(success_criteria=' ')):
            with self.subTest(changes=changes), self.assertRaises(DecisionViolation) as exc:
                validate_plan_assignment(normalize_plan({**self.plan,**changes}))
            self.assertEqual(exc.exception.code,'supplement_response_semantics')

    def test_reconsideration_requires_a_specific_covered_approval_issue(self):
        from research_supplement import scope_correction
        plan=dict(action='hold',blocker='approval_only',requested_tools=['youtube'])
        scope=dict(approval='active',configured_tools=['youtube','official_listing'],
                   reconsideration_remaining=True,gemini_remaining=11,collection_actions_remaining=8,
                   listing_candidate_present=False)
        self.assertTrue(scope_correction(plan,scope)['eligible'])
        for changes in (dict(approval='expired'),dict(gemini_remaining=3),dict(collection_actions_remaining=0),
                        dict(reconsideration_remaining=False),dict(configured_tools=[])):
            self.assertFalse(scope_correction(plan,{**scope,**changes})['eligible'])
        self.assertFalse(scope_correction({**plan,'blocker':'owner_judgment'},scope)['eligible'])
        self.assertFalse(scope_correction({**plan,'requested_tools':['official_listing']},scope)['eligible'])

    def test_staff_action_rejection_records_only_a_fixed_rule(self):
        from research_supplement import action_option
        for kind,option,rule in (
                ('finish','details','supplement_finish_option_not_empty'),
                ('official_listing','invented','supplement_listing_not_observed'),
                ('youtube',' a game','supplement_query_whitespace'),
                ('web','https://example.invalid','supplement_query_not_public_keywords')):
            with self.subTest(kind=kind), self.assertRaises(DecisionViolation) as exc:
                action_option(dict(tool=kind,option=option),{})
            self.assertEqual(exc.exception.rule,rule)
