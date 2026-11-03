"""Goal-to-delivery with zero user business approvals and no live transport."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import autonomous_company as company
from tests.support.autonomous_company_fixtures import FictionalModels


class AutonomousCompanyTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.root=Path(self.temp)/'mock-company'
        self.store=company.Store(self.root)
        for name in ('socket.socket','socket.getaddrinfo','ai_safety.request_json','ai_safety.guarded_urlopen',
                     'manager_decision.urlopen','execution_engine.urlopen','manager_plan.urlopen','semantic_review.urlopen',
                     'app.respond_manager_decision','app.review_task_result','app.configure_semantic','app.execute_project_task'):
            self.enterContext(patch(name,side_effect=AssertionError('live/manual API forbidden')))

    def create(self,models,**limits):
        goal='지역 도서관 이용 안내를 작성하세요' if models.domain=='library' else '소형 매장 재고 인수인계 안내를 작성하세요'
        p=self.store.create(goal,opt_in=True,**limits)
        return p,company.Company(self.store,models.manager,models.employee)

    def test_two_domains_goal_to_files_without_user_approvals(self):
        plans=[]
        for domain in ('library','stock'):
            models=FictionalModels(domain,revise=domain=='stock');p,runner=self.create(models)
            result=runner.run(p['id']);self.assertEqual(result['status'],'delivered')
            self.assertEqual(result['user_business_approval_requests'],0);self.assertFalse(result['real_calls_allowed'])
            self.assertNotIn('real_ai',result)
            self.assertEqual(len({t['role'] for t in result['assignments']}),2)
            self.assertTrue(all(t['state']=='accepted_by_ai_manager' for t in result['assignments']))
            self.assertTrue(all(a['status']=='completed' for a in result['attempts']))
            self.assertTrue(all(a['reserved_at'].endswith('+09:00') for a in result['attempts']))
            self.assertTrue(any(e['event']=='ai_manager_decision' for e in result['events']))
            raw=json.dumps(result,ensure_ascii=False)
            for field in ('reviewed_by','approved_by','pending_user_decision'):self.assertNotIn(field,raw)
            self.assertEqual(result['plan']['adopted_by'],'ai_manager')
            final_path=self.root/result['artifacts']['final.md']['path']
            content=final_path.read_text();self.assertIn(result['final']['content'],content)
            self.assertIn('mock-only',content)
            plans.append(result['plan'])
            context=next(ctx for phase,ctx in models.contexts if phase=='execute' and ctx['previous_results'])
            self.assertEqual(context['previous_results'][0],result['assignments'][0]['versions'][-1])
            if domain=='stock':
                first=result['assignments'][0];self.assertEqual(first['revisions'],1)
                self.assertEqual([r['action'] for r in first['reviews']],['revise','accept'])
                self.assertEqual(len(first['versions']),2)
                self.assertIn('마감 담당자',context['previous_results'][0]['content'])
                self.assertNotIn('담당자 누락',context['previous_results'][0]['content'])
            count=len(models.calls);before=self.store.path(p['id']).read_bytes()
            runner.run(p['id']);self.assertEqual(len(models.calls),count);self.assertEqual(self.store.path(p['id']).read_bytes(),before)
            code='import sys,json;from autonomous_company import Store;print(json.dumps(Store(sys.argv[1]).result(sys.argv[2])))'
            read=subprocess.run([sys.executable,'-B','-c',code,str(self.root),p['id']],capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(read.stdout)['final'],result['final'])
        self.assertNotEqual(plans[0]['criteria'],plans[1]['criteria'])
        self.assertNotEqual(plans[0]['tasks'],plans[1]['tasks'])

    def test_unknown_facts_repetition_budget_and_provider_failure_stop(self):
        cases=[(FictionalModels(unknown=True),{},'manager_stopped'),
               (FictionalModels(always_revise=True),{},'revision_limit'),
               (FictionalModels(),{'max_calls':2},'mock_budget_exhausted'),
               (FictionalModels(fail=True),{},'mock_provider_failed')]
        for models,limits,code in cases:
            with self.subTest(code=code):
                p,runner=self.create(models,**limits);result=runner.run(p['id'])
                self.assertEqual(result['status'],'stopped');self.assertEqual(result['reason_code'],code)
                self.assertFalse(result['artifacts']);self.assertEqual(result['user_business_approval_requests'],0)
                count=len(models.calls);runner.run(p['id']);self.assertEqual(len(models.calls),count)
                self.assertNotIn('PRIVATE',json.dumps(result))
                if code=='revision_limit':self.assertEqual(result['assignments'][0]['revisions'],1)
                if code=='manager_stopped':self.assertEqual(result['assignments'][0]['reviews'][0]['checks'][0]['status'],'unknown')

    def test_interruption_leaves_reserved_and_resume_never_reinvokes(self):
        models=FictionalModels();p,runner=self.create(models)
        def interrupted(phase,context):raise KeyboardInterrupt()
        worker=company.MockEmployeeProvider(models.employee.name,interrupted)
        with self.assertRaises(KeyboardInterrupt):company.Company(self.store,models.manager,worker).run(p['id'])
        saved=self.store.load(p['id']);self.assertEqual(saved['attempts'][-1]['status'],'reserved')
        calls=len(models.calls)
        resumed=runner.run(p['id']);self.assertEqual(resumed['reason_code'],'uncertain_operation')
        self.assertEqual(resumed['attempts'][-1]['status'],'reserved');self.assertEqual(len(models.calls),calls)
        self.assertFalse(resumed['artifacts'])

    def test_opt_in_namespace_and_live_provider_rejection(self):
        with self.assertRaises(company.CompanyError):self.store.create('목표')
        self.assertFalse(self.root.exists())
        models=FictionalModels()
        with self.assertRaises(company.CompanyError):company.Company(self.store,object(),models.employee)
        legacy=Path(self.temp)/'legacy';legacy.mkdir();path=legacy/'legacy.json';path.write_text('{"id":"legacy","real_ai":{}}')
        before=path.read_bytes()
        with self.assertRaises(company.CompanyError):company.Store(legacy).create('목표',opt_in=True)
        with self.assertRaises(company.CompanyError):company.Store(legacy).load('legacy')
        self.assertEqual(path.read_bytes(),before)
        p,runner=self.create(models)
        with self.store.lock(p['id']):
            with self.assertRaises(company.CompanyError):runner.run(p['id'])
        self.assertEqual(len(models.calls),0)

    def test_invalid_plan_fake_user_approval_and_accepting_unknown_are_rejected(self):
        for mode in ('cycle','fake_user','unknown_accept','business_question'):
            models=FictionalModels()
            def reply(phase,ctx):
                value=json.loads(models.manager_response(phase,ctx))
                if phase=='plan':
                    if mode=='cycle':value['tasks'][0]['depends_on']=[value['tasks'][-1]['id']]
                    if mode=='fake_user':value['approved_by']='사용자'
                elif phase=='review':
                    if mode=='unknown_accept':value['checks'][0]['status']='unknown'
                    if mode=='business_question':value['action']='ask_user'
                return json.dumps(value,ensure_ascii=False)
            p,_=self.create(models);runner=company.Company(self.store,company.MockManagerProvider(models.manager.name,reply),models.employee)
            result=runner.run(p['id']);self.assertEqual(result['status'],'stopped')
            self.assertFalse(result['artifacts']);self.assertEqual(result['user_business_approval_requests'],0)

    def test_only_operational_permission_can_request_user_intervention(self):
        models=FictionalModels();p,_=self.create(models)
        def reply(phase,ctx):
            value=json.loads(models.manager_response(phase,ctx))
            if phase=='review':value.update(action='needs_operational_permission',operation='external_data')
            return json.dumps(value,ensure_ascii=False)
        result=company.Company(self.store,company.MockManagerProvider(models.manager.name,reply),models.employee).run(p['id'])
        self.assertEqual(result['status'],'needs_operational_permission');self.assertEqual(result['reason_code'],'external_data')
        self.assertEqual(result['user_business_approval_requests'],0);self.assertFalse(result['artifacts'])

    def test_read_only_result_page_no_business_approval_forms(self):
        import app
        manual=Path(self.temp)/'manual';manual.mkdir()
        self.enterContext(patch.object(app,'PROJECTS_DIR',manual))
        self.enterContext(patch.object(app,'AUTONOMOUS_MOCK_ROOT',self.root))
        models=FictionalModels();p,runner=self.create(models);result=runner.run(p['id'])
        before=self.store.path(p['id']).read_bytes()
        pages=[];handler=app.Handler.__new__(app.Handler);handler.send_html=lambda content,status=200:pages.append((content,status))
        handler.path='/autonomous/mock/'+p['id'];handler.do_GET()
        self.assertEqual(pages[-1][1],200);self.assertIn(result['final']['content'],pages[-1][0])
        self.assertIn('mock-only',pages[-1][0]);self.assertNotIn('<form',pages[-1][0])
        handler.home();self.assertIn('/autonomous/mock/'+p['id'],pages[-1][0])
        self.assertEqual(self.store.path(p['id']).read_bytes(),before)
        handler.path='/autonomous/mock/not-a-project';handler.do_GET();self.assertEqual(pages[-1][1],404)

    def test_state_artifact_tampering_and_concurrent_writer_do_not_trigger_replay(self):
        models=FictionalModels();p,runner=self.create(models);result=runner.run(p['id'])
        path=self.root/result['artifacts']['final.md']['path'];path.write_text('tampered')
        calls=len(models.calls)
        with self.assertRaises(company.CompanyError):runner.run(p['id'])
        self.assertEqual(len(models.calls),calls)
        p,runner=self.create(models)
        old=self.store.load(p['id']);other=self.store.load(p['id']);other['goal']='다른 새 목표';self.store.save(other)
        with self.assertRaises(company.CompanyError):self.store.save(old)
        self.assertEqual(self.store.load(p['id'])['goal'],'다른 새 목표')
        raw=json.loads(self.store.path(p['id']).read_text());raw['limits']['max_calls']=999
        self.store.path(p['id']).write_text(json.dumps(raw))
        with self.assertRaises(company.CompanyError):runner.run(p['id'])

    def test_completed_but_unapplied_interruption_is_not_recalled(self):
        models=FictionalModels();p,runner=self.create(models)
        save=self.store.save
        def interrupt_after_response(project):
            save(project)
            if project['attempts'] and project['attempts'][-1]['status']=='completed':raise KeyboardInterrupt()
        with patch.object(self.store,'save',side_effect=interrupt_after_response):
            with self.assertRaises(KeyboardInterrupt):runner.run(p['id'])
        count=len(models.calls);result=runner.run(p['id'])
        self.assertEqual(result['reason_code'],'uncertain_operation')
        self.assertEqual(len(models.calls),count)
        self.assertEqual(result['attempts'][-1]['status'],'completed')

    def test_clean_checkpoint_resume_continues_without_replanning(self):
        models=FictionalModels();p,runner=self.create(models);commit=runner._commit
        def checkpoint(project,event,**details):
            commit(project,event,**details)
            if event=='ai_manager_decision' and details.get('phase')=='plan':raise KeyboardInterrupt()
        with patch.object(runner,'_commit',side_effect=checkpoint):
            with self.assertRaises(KeyboardInterrupt):runner.run(p['id'])
        saved=self.store.load(p['id']);self.assertEqual(saved['phase'],'work');self.assertIsNone(saved['active_operation'])
        result=runner.run(p['id']);self.assertEqual(result['status'],'delivered')
        self.assertEqual(models.calls.count(('manager','plan')),1)
        self.assertEqual(len(result['attempts']),6)

    def test_missing_lock_support_fails_closed(self):
        models=FictionalModels();p,runner=self.create(models)
        with patch.object(company,'fcntl',None):
            with self.assertRaises(company.CompanyError):runner.run(p['id'])
        self.assertEqual(models.calls,[])
        self.assertEqual(self.store.load(p['id'])['status'],'ready')

    def test_same_manager_provider_produces_different_goal_criteria(self):
        models=FictionalModels();runner=company.Company(self.store,models.manager,models.employee);plans=[]
        for goal in ('도서관 초보 이용 안내','매장 재고 업무 인수인계'):
            p=self.store.create(goal,opt_in=True);result=runner.run(p['id'])
            self.assertEqual(result['status'],'delivered');plans.append(result['plan'])
        self.assertNotEqual(plans[0]['criteria'],plans[1]['criteria'])
        self.assertEqual(plans[0]['provider'],plans[1]['provider'])

    def test_manager_can_stop_infeasible_plan_without_employee_or_business_question(self):
        models=FictionalModels();p,_=self.create(models)
        reply={'action':'stop','rationale':'제공 자료로 목표를 달성할 근거가 부족합니다.',
               'uncertainty':'현장 자료와 도구가 없습니다.','operation':None}
        manager=company.MockManagerProvider(models.manager.name,lambda phase,ctx:json.dumps(reply,ensure_ascii=False))
        runner=company.Company(self.store,manager,models.employee);result=runner.run(p['id'])
        self.assertEqual(result['reason_code'],'manager_plan_stopped');self.assertEqual(len(result['attempts']),1)
        self.assertEqual(models.calls,[]);self.assertEqual(result['events'][-1]['decision'],reply)
        self.assertIn(reply['rationale'],company.render(result));self.assertFalse(result['artifacts'])
