"""Explicit answer audit and optimistic binding; fake model/keys only."""
from copy import deepcopy
from unittest.mock import patch
import app
import manager_decision as md
from tests import test_real_manager_task002_new_authorization as fixture

ANSWER = ('현재 TASK-002 대본은 수정하지 않고 유지합니다. TASK-003 품질 검토에서 사실 확인이 필요한 항목, '
          '의미적 정확성, 초보자 이해도, 실제 영상 제작 가능성을 검토해 주세요. 검토 결과 수정이 필요하다면 '
          '그때 수정 여부를 결정하겠습니다. 이 답변은 TASK-003 또는 다른 실제 AI 호출의 승인이 아닙니다.')


class AuthorizedAnswerTests(fixture.NewAuthorizationTests):
    def prepare_question(self):
        self.prepare_next()
        with patch('manager_decision.urlopen',side_effect=self.transport_next('ask_user')):
            proposal=self.next_once()
        return self.saved(), proposal

    def test_authorized_answer_changes_only_question_answer_and_audit(self):
        p,proposal=self.prepare_question()
        with patch('manager_decision.urlopen') as sender,patch('execution_engine.urlopen') as worker:
            app.respond_manager_decision(p['id'],proposal['id'],md.digest(proposal),'answer',answer=ANSWER,
                expected_project_hash=md.digest(p),user_authorization='가상 사용자의 답변 기록만 승인')
            sender.assert_not_called();worker.assert_not_called()
        q=self.saved()
        self.assertEqual(q['tasks'],p['tasks']);self.assertEqual(q['real_ai'],p['real_ai'])
        self.assertEqual(q['manager_decisions']['proposals'][:2],p['manager_decisions']['proposals'][:2])
        self.assertEqual(q['manager_decisions']['proposals'][-1]['status'],'answered')
        self.assertEqual(q['manager_decisions']['answers'][-1]['answer'],ANSWER)
        self.assertNotIn('purpose',q['manager_decisions']['answers'][-1])
        self.assertTrue(q['manager_decisions']['answers'][-1]['at'].endswith('+09:00'))
        self.assertEqual(q['history'][-1]['user_authorization'],'가상 사용자의 답변 기록만 승인')
        self.assertEqual(q['history'][-1]['answer_hash'],md.digest(ANSWER))
        self.assertEqual(app._manager_decision_input(q,'TASK-002')['data']['user_answers'][-1]['answer'],ANSWER)
        with self.assertRaises(ValueError):md.require_proceed(q,'TASK-003',['TASK-002'])
        with self.assertRaises(ValueError):app.respond_manager_decision(p['id'],proposal['id'],md.digest(proposal),'answer',answer=ANSWER)
        self.assertEqual(self.saved(),q)

    def test_stale_project_or_question_rejects_without_writes(self):
        p,proposal=self.prepare_question()
        q=deepcopy(p);q['user_preferences']['focus']='경합 보존';app.save_project(q)
        with self.assertRaises(ValueError):
            app.respond_manager_decision(p['id'],proposal['id'],md.digest(proposal),'answer',answer=ANSWER,
                expected_project_hash=md.digest(p),user_authorization='가상 승인')
        self.assertEqual(self.saved(),q)
        with self.assertRaises(ValueError):
            app.respond_manager_decision(p['id'],proposal['id'],'stale','answer',answer=ANSWER,user_authorization='가상 승인')
        self.assertEqual(self.saved(),q)
