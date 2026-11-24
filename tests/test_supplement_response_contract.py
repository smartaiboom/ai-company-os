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
