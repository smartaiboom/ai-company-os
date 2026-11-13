"""Focused, offline safety tests for rework manager quality follow-ups.

No model calls, network, live state, credentials, or stored user projects.
Run: PYTHONPATH=core:companies/video python -B -m unittest tests.test_rework_quality_followup_unit
"""
import json
import unittest
from unittest.mock import patch

from representative_rework import ReworkCompany
from video_mission_one import MissionOneCompany


class DummyStore:
    def __init__(self):
        self.saves = 0

    def save(self, _state):
        self.saves += 1


def model_review(*, action="accept", met=True, evidence="한 문장", check_status="met"):
    return {
        "result": {
            "action": action,
            "rationale": "검토 의견",
            "evidence": "대본 검토",
            "uncertainty": "실제 성과 미검증",
            "checks": [{
                "criterion_id": "fact",
                "status": check_status,
                "evidence": "근거",
                "source": "model_claim",
            }],
            "feedback": "근거 없는 주장을 수정하세요" if action == "revise" else "",
            "operation": None,
            "goal_review": {
                k: {"met": met, "evidence": evidence}
                for k in (
                    "goal_fit", "feedback_applied", "subject_story",
                    "concrete_hook", "claims_supported"
                )
            },
        }
    }


class QualityFollowupTests(unittest.TestCase):
    def setUp(self):
        self.company = object.__new__(ReworkCompany)
        self.company._review_content = json.dumps({"transcript": "한 문장\n두 번째 문장"}, ensure_ascii=False)
        self.company._review_task_id = "writer_001"
        self.company._quality_followup = None
        self.company.store = DummyStore()
        self.company._rework_state = {
            "assignments": [{
                "id": "writer_001", "role": "writer",
                "revisions": 0, "versions": [], "reviews": [],
            }],
            "limits": {"max_revisions_per_task": 1, "max_total_revisions": 1},
            "real_ai": {"attempts": [{"status": "completed", "http_status": 200}]},
        }

    def parse(self, payload):
        # Control only the generic role wire parser. Exercise the actual
        # ReworkCompany semantic decision branch and its persisted metadata.
        with patch("representative_rework.matches", return_value=True), patch.object(
            MissionOneCompany, "_parse_role_content",
            autospec=True,
            side_effect=lambda _self, raw, phase: json.loads(raw)["result"],
        ):
            return self.company._parse_role_content(json.dumps(payload, ensure_ascii=False), "review")

    def test_valid_accept_hands_off_without_quality_override(self):
        result = self.parse(model_review(evidence="한 문장"))
        self.assertEqual(result["action"], "accept")
        self.assertIsNone(self.company._quality_followup)
        self.assertEqual(self.company.store.saves, 0)

    def test_unmet_manager_accept_becomes_bounded_revision(self):
        result = self.parse(model_review(met=False))
        self.assertEqual(result["action"], "revise")
        self.assertIn("goal_fit", result["feedback"])
        self.assertIn("시스템 품질 검증", result["rationale"])
        self.assertEqual(self.company._quality_followup["original_action"], "accept")
        self.assertEqual(self.company._quality_followup["decision"], "revise")

    def test_missing_evidence_becomes_revision_instead_of_accept(self):
        result = self.parse(model_review(evidence="대본에 없는 내용"))
        self.assertEqual(result["action"], "revise")
        self.assertEqual(
            self.company._quality_followup["failed_checks"]["goal_fit"],
            "evidence_not_found",
        )

    def test_unmet_manager_check_cannot_be_accepted(self):
        result = self.parse(model_review(check_status="unmet"))
        self.assertEqual(result["action"], "revise")
        self.assertEqual(
            self.company._quality_followup["failed_checks"]["criterion:fact"],
            "criterion_not_met",
        )

    def test_revision_exhaustion_requires_representative_decision(self):
        self.company._rework_state["assignments"][0]["revisions"] = 1
        result = self.parse(model_review(met=False))
        self.assertEqual(result["action"], "stop")
        self.assertEqual(self.company._quality_followup["decision"], "stop")
        self.assertEqual(self.company._quality_followup["reason"], "manager_accept_conflicted_with_goal_review")

    def test_manager_revision_at_limit_ends_safely(self):
        self.company._rework_state["assignments"][0]["revisions"] = 1
        result = self.parse(model_review(action="revise", met=False))
        self.assertEqual(result["action"], "stop")
        self.assertEqual(self.company._quality_followup["reason"], "revision_limit_reached")

    def test_original_manager_revision_is_preserved_when_available(self):
        result = self.parse(model_review(action="revise", met=False))
        self.assertEqual(result["action"], "revise")
        self.assertIsNone(self.company._quality_followup)



class OwnerQualityDecisionTests(unittest.TestCase):
    def test_owner_instruction_is_recorded_once_without_restarting_job(self):
        from copy import deepcopy
        from contextlib import nullcontext
        from unittest.mock import Mock
        from autonomous_company import CompanyError, digest
        from studio_server import Studio
        project = {
            "representative": {
                "stage": "plan_revision",
                "rework": {"status": "stopped", "job": "fixture-job",
                           "error": "manager_stopped"}
            }
        }
        saved = []
        workspace = Mock()
        workspace.root = __import__("pathlib").Path("/offline/fixture")
        workspace.lock.side_effect = lambda _pid: nullcontext()
        workspace.load.side_effect = lambda _pid: deepcopy(saved[-1] if saved else project)
        workspace.save.side_effect = lambda value: saved.append(deepcopy(value))
        studio = object.__new__(Studio)
        studio.stores = {"workspace": workspace}
        report = {"decision": "stop", "reason": "revision_limit_reached",
                  "failed_checks": {"goal_fit": "not_met"},
                  "feedback": "원 목표의 흥미로운 장면을 보여주세요."}
        request = {"job": "fixture-job", "report_hash": digest(report),
                   "action": "request_revision", "feedback": "게임 이야기로 수정"}
        with patch("representative_rework.ReworkStore") as store, patch(
            "representative_rework.progress_view",
            return_value={"quality_report": report}
        ):
            store.return_value.load.return_value = {"id": "fixture-job"}
            studio.rework_quality_decide("fixture-project", request)
            self.assertEqual(saved[-1]["representative"]["rework"]["quality_decision"]["action"],
                             "request_revision")
            self.assertTrue(saved[-1]["representative"]["rework"]["quality_decision"]["requires_new_consent"])
            self.assertEqual(saved[-1]["representative"]["rework"]["status"], "stopped")
            with self.assertRaisesRegex(CompanyError, "quality_decision_already_recorded"):
                studio.rework_quality_decide("fixture-project", request)
            wrong = {**request, "report_hash": "wrong"}
            with self.assertRaisesRegex(CompanyError, "quality_report_changed"):
                studio.rework_quality_decide("fixture-project", wrong)
        self.assertEqual(len(saved), 1)

    def test_owner_hold_does_not_grant_execution(self):
        from copy import deepcopy
        from contextlib import nullcontext
        from unittest.mock import Mock
        from autonomous_company import digest
        from studio_server import Studio
        project={"representative":{"stage":"plan_revision","rework":{
            "status":"stopped","job":"fixture-job","error":"manager_stopped"}}}
        store=Mock()
        store.root=__import__("pathlib").Path("/offline/fixture")
        store.lock.side_effect=lambda _pid:nullcontext()
        store.load.return_value=deepcopy(project)
        saved=[]
        store.save.side_effect=lambda value:saved.append(deepcopy(value))
        studio=object.__new__(Studio);studio.stores={"workspace":store}
        report={"decision":"stop","reason":"revision_limit_reached","failed_checks":{}}
        with patch("representative_rework.ReworkStore"), patch(
            "representative_rework.progress_view",return_value={"quality_report":report}
        ):
            studio.rework_quality_decide("fixture-project",{
                "job":"fixture-job","report_hash":digest(report),"action":"hold","feedback":""})
        self.assertEqual(saved[0]["representative"]["rework"]["quality_decision"]["action"],"hold")
        self.assertFalse(saved[0]["representative"]["rework"]["quality_decision"]["requires_new_consent"])
        self.assertEqual(saved[0]["representative"]["rework"]["status"],"stopped")



class LegacyUnvalidatedReviewTests(unittest.TestCase):
    def test_legacy_review_report_requires_completed_but_unvalidated_review(self):
        from copy import deepcopy
        from representative_rework import legacy_quality_report
        job = dict(status='stopped',reason_code='rework_goal_not_met',
                   phase='work',final=None,assignments=[dict(
                       role='writer',versions=[dict(content='{"transcript":"가상 대본"}')],reviews=[])],
                   real_ai=dict(attempts=[dict(
                       id='original-attempt',phase='review',status='completed',
                       http_status=200,role_result_status='unvalidated',
                       transport_started_at='2026-11-13T09:00:00+09:00',
                       finished_at='2026-11-13T09:01:00+09:00')]))
        state=dict(status='stopped',error='rework_goal_not_met')
        before=deepcopy(job)
        report=legacy_quality_report(job,state)
        self.assertEqual(report['source'],'legacy_failure_diagnostic_not_manager_review')
        self.assertEqual(report['original_action'],'unknown_unvalidated')
        self.assertEqual(report['decision'],'stop')
        self.assertEqual(job,before)
        for field,value in [('status','reserved'),('role_result_status','validated'),
                            ('http_status',503),('phase','execute')]:
            changed=deepcopy(job)
            changed['real_ai']['attempts'][-1][field]=value
            self.assertIsNone(legacy_quality_report(changed,state))
        changed=deepcopy(job);changed['assignments'][0]['reviews'].append({'action':'accept'})
        self.assertIsNone(legacy_quality_report(changed,state))
        self.assertIsNone(legacy_quality_report(job,dict(status='running',error='rework_goal_not_met')))



class StoppedScriptReviewAuditTests(unittest.TestCase):
    def test_saved_manager_revision_is_reported_read_only(self):
        from copy import deepcopy
        from representative_rework import script_review_recovery_audit
        writer=dict(id='task_writer_v3',role='writer',criteria_ids=['hook'],
                    versions=[dict(content='{"transcript":"예시 대본"}')],
                    reviews=[dict(action='revise',feedback='자막을 줄이세요.')])
        job=dict(id='qualityprovider-offline',status='stopped',phase='work',
            reason_code='script_feedback_missing_defect',assignments=[writer],
            rework_plan=dict(duration_seconds=25),
            quality_inputs=dict(target_segment='게임 시청자'),
            real_ai=dict(attempts=[
                dict(id='review',phase='review',task_id='task_writer_v3',
                     status='completed',http_status=200,role_result_status='json_parsed',
                     transport_started_at='2026-11-13T13:31:52+09:00',
                     finished_at='2026-11-13T13:31:56+09:00',
                     response_hash='evidence-hash')]))
        state=dict(status='stopped',error='script_feedback_missing_defect')
        before=deepcopy(job)
        inspection=dict(defects=[dict(issue='caption_width',
            evidence='긴 자막',correction='2줄로 줄임')])
        with patch('script_quality.inspect_script',return_value=inspection):
            report=script_review_recovery_audit(job,state)
        self.assertEqual(report['status'],'saved_review_reusable_as_unvalidated_input')
        self.assertEqual(report['missing_issue_ids'],['caption_width'])
        self.assertFalse(report['review_committed'])
        self.assertFalse(report['callable_retry_allowed'])
        self.assertEqual(report['new_requests'],0)
        self.assertEqual(job,before)

    def test_uncertain_review_transport_is_not_marked_reusable(self):
        from copy import deepcopy
        from representative_rework import script_review_recovery_audit
        writer=dict(id='task_writer_v3',role='writer',criteria_ids=['hook'],
                    versions=[dict(content='{}')],
                    reviews=[dict(action='revise',feedback='수정')])
        job=dict(status='stopped',phase='work',
                 reason_code='script_feedback_missing_defect',assignments=[writer],
                 real_ai=dict(attempts=[dict(phase='review',task_id='task_writer_v3',
                        status='reserved',role_result_status='json_parsed')]))
        report=script_review_recovery_audit(job,dict(status='stopped',error='script_feedback_missing_defect'))
        self.assertEqual(report['status'],'incomplete_evidence')
        self.assertFalse(report['review_available'])



class ReuseProofAuditTests(unittest.TestCase):
    def test_verified_plan_and_writer_allow_only_a_new_recovery_proposal(self):
        from copy import deepcopy
        from representative_rework import script_review_recovery_audit
        def attempt(phase,task_id,status):
            return dict(phase=phase,task_id=task_id,status='completed',
                http_status=200,role_result_status=status,response_hash='hash-'+phase,
                transport_started_at='2026-11-13T13:31:42+09:00',
                finished_at='2026-11-13T13:31:47+09:00')
        job=dict(id='qualityprovider-offline',status='stopped',phase='work',
            reason_code='script_feedback_missing_defect',final=None,
            plan=dict(tasks=[]),sessions=[dict(id='session-1')],
            quality_inputs=dict(target_segment='게임 시청자'),
            rework_plan=dict(duration_seconds=25),
            assignments=[dict(role='writer',id='task_writer_v3',criteria_ids=['hook'],
                versions=[dict(content='{"transcript":"예시 대본"}')],
                reviews=[dict(action='revise',feedback='자막을 줄이세요')])],
            real_ai=dict(attempts=[attempt('plan',None,'validated'),
                attempt('execute','task_writer_v3','validated'),
                attempt('review','task_writer_v3','json_parsed')]))
        state=dict(status='stopped',error='script_feedback_missing_defect')
        before=deepcopy(job)
        inspection=dict(defects=[dict(issue='caption_width',correction='자막 수정',evidence='긴 문장')])
        with patch('script_quality.inspect_script',return_value=inspection):
            report=script_review_recovery_audit(job,state)
        self.assertTrue(report['reusable_plan'])
        self.assertTrue(report['reusable_writer'])
        self.assertTrue(report['safe_for_recovery_proposal'])
        self.assertFalse(report['callable_retry_allowed'])
        self.assertFalse(report['review_committed'])
        self.assertEqual(job,before)

        job['real_ai']['attempts'][1]['role_result_status']='json_parsed'
        with patch('script_quality.inspect_script',return_value=inspection):
            invalid=script_review_recovery_audit(job,state)
        self.assertFalse(invalid['reusable_writer'])
        self.assertFalse(invalid['safe_for_recovery_proposal'])



class ScriptRecoverySeedTests(unittest.TestCase):
    def test_old_job_is_not_mutated_and_new_job_starts_with_writer_revision(self):
        from copy import deepcopy
        from autonomous_company import digest
        from representative_rework import seed_recovered_script_job
        inspection=dict(defects=[dict(issue='caption_width',correction='자막을 줄이세요',evidence='긴 자막')])
        old=dict(id='qualityprovider-old',plan=dict(source='provider_model_claim',criteria=[]),
            rework_plan=dict(duration_seconds=25),
            quality_inputs=dict(target_segment='게임 시청자'),
            real_ai=dict(attempts=[dict(phase='plan'),dict(phase='execute'),dict(phase='review')]),
            assignments=[
                dict(id='writer',role='writer',state='awaiting_ai_review',revisions=0,
                     versions=[dict(content='{"transcript":"게임 사건 대본"}',revision=1)],
                     reviews=[dict(action='revise',feedback='긴 자막을 줄이세요')]),
                dict(id='editor',role='editor',state='pending',revisions=0,
                     versions=[],reviews=[]),
            ])
        audit=dict(safe_for_recovery_proposal=True,inspection_hash=digest(inspection))
        before=deepcopy(old)
        new=dict(plan=None,assignments=[],phase='plan')
        with patch('script_quality.inspect_script',return_value=inspection):
            seed_recovered_script_job(new,old,audit)
        self.assertEqual(old,before)
        self.assertEqual(new['phase'],'work')
        self.assertEqual(new['plan'],old['plan'])
        self.assertEqual(new['assignments'][0]['state'],'revision_requested')
        self.assertEqual(new['assignments'][0]['versions'][0]['reused_from_job'],old['id'])
        self.assertEqual(new['assignments'][0]['reviews'][0]['source'],
                         'system_recovery_instruction_from_unvalidated_manager_review')
        self.assertFalse(new['assignments'][0]['reviews'][0]['approved_by_manager'])
        self.assertIn('caption_width',new['assignments'][0]['reviews'][0]['feedback'])
        self.assertEqual(new['assignments'][1]['state'],'pending')
        self.assertFalse(new['script_recovery']['manager_acceptance'])
        self.assertFalse(new['script_recovery']['source_request_replayed'])

    def test_recovered_job_preflight_accepts_only_proven_unstarted_state(self):
        from copy import deepcopy
        from representative_rework import ReworkStore
        from autonomous_company import digest,CompanyError
        prior=dict(content='{"transcript":"게임 사건 대본"}',revision=1)
        review=dict(action='revise',feedback='수정')
        plan=dict(source='provider_model_claim')
        recovery=dict(source_job='qualityprovider-old',
            original_plan_hash=digest(plan),original_writer_hash=digest(prior),
            original_review_hash=digest(review),inspection_hash='inspection',
            manager_acceptance=False,source_request_replayed=False)
        parent=dict(job='qualityprovider-old',recovery_scope='validated_plan_writer_reuse_new_job',
            previous_plan_hash=digest(plan),previous_writer_hash=digest(prior),
            previous_review_hash=digest(review),inspection_hash='inspection')
        job=dict(simulation=False,status='ready',phase='work',reason_code=None,
            real_ai=dict(attempts=[]),attempts=[],sessions=[],active_operation=None,
            run_started_at=None,next_request_at=None,providers=None,
            artifacts={},final=None,plan=plan,script_recovery=recovery,
            rework_reference=dict(previous_failed_attempt=parent),
            events=[dict(event='operating_scope_approved')],
            assignments=[dict(role='writer',state='revision_requested',revisions=0,
                versions=[dict(**prior,reused_from_job='qualityprovider-old')],
                reviews=[dict(source='system_recovery_instruction_from_unvalidated_manager_review',
                    approved_by_manager=False,original_review_hash=digest(review),feedback='수정')]),
                dict(role='editor',state='pending',revisions=0,versions=[],reviews=[])])
        store=object.__new__(ReworkStore)
        with patch.object(ReworkStore,'valid_mode',return_value=True):
            store.require_unstarted(job)
            invalid=deepcopy(job)
            invalid['real_ai']['attempts'].append(dict(phase='plan',status='completed'))
            with self.assertRaises(CompanyError):
                store.require_unstarted(invalid)
            tampered=deepcopy(job)
            tampered['assignments'][0]['reviews'][0]['approved_by_manager']=True
            with self.assertRaises(CompanyError):
                store.require_unstarted(tampered)


if __name__ == "__main__":
    unittest.main()
