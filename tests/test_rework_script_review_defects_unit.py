"""Offline regression: natural-language manager feedback must not fail on missing machine issue IDs.

Run: PYTHONPATH=core:companies/video python -B -m unittest tests.test_rework_script_review_defects_unit
No Gemini calls, credentials, workspace mutation or external services.
"""
import unittest
from unittest.mock import patch

from representative_rework import ReworkCompany
from quality_workflow import VideoProviderQualityCompany


class ReviewDefectFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.company=object.__new__(ReworkCompany)
        self.state={
            'quality_inputs': {'target_segment': '게임 쇼츠 시청자'},
            'rework_plan': {'duration_seconds': 25},
            'events': [],
        }
        self.task={'id':'task_writer_v3','role':'writer',
                   'versions':[{'content':'{"transcript":"테스트 대본"}'}]}
        self.inspection={'defects':[
            dict(issue='caption_width',evidence='너무 긴 자막',correction='자막을 짧게 수정'),
            dict(issue='timeline_gap_or_overlap',evidence='장면 시간',correction='장면 시간을 연결'),
        ]}
        self.manager_feedback='자막을 줄이고 장면 길이를 조정하세요.'

    def _validate(self,review):
        with patch('script_quality.inspect_script',return_value=self.inspection) as inspect,\
                patch.object(VideoProviderQualityCompany,'_validate_review_decision') as parent:
            self.company._validate_review_decision(self.state,self.task,review)
        parent.assert_called_once_with(self.state,self.task,review)
        return inspect

    def test_revise_preserves_manager_intent_and_attaches_only_missing_defects(self):
        review={'action':'revise','feedback':self.manager_feedback}
        inspect=self._validate(review)
        inspect.assert_called_once()
        self.assertTrue(review['feedback'].startswith(self.manager_feedback))
        self.assertIn('[시스템 자동 검출 항목',review['feedback'])
        for defect in self.inspection['defects']:
            self.assertIn(defect['issue'],review['feedback'])
            self.assertIn(defect['correction'],review['feedback'])
        event=self.state['events'][-1]
        self.assertEqual(event['event'],'system_script_defects_attached')
        self.assertFalse(event['approved_by_manager'])
        self.assertEqual(len(event['appended_defects']),2)

    def test_accept_is_not_automatically_repaired_or_changed(self):
        review={'action':'accept','feedback':''}
        inspect=self._validate(review)
        inspect.assert_not_called()
        self.assertEqual(review['action'],'accept')
        self.assertEqual(self.state['events'],[])

    def test_revise_with_complete_machine_ids_keeps_original_review(self):
        feedback='caption_width, timeline_gap_or_overlap: 수정하세요'
        review={'action':'revise','feedback':feedback}
        self._validate(review)
        self.assertEqual(review['feedback'],feedback)
        self.assertEqual(self.state['events'],[])

    def test_stop_remains_stop_without_extra_feedback(self):
        review={'action':'stop','feedback':'대표 판단 필요'}
        inspect=self._validate(review)
        inspect.assert_not_called()
        self.assertEqual(review['action'],'stop')
        self.assertEqual(self.state['events'],[])


if __name__=='__main__':
    unittest.main()
