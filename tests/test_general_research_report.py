from datetime import datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError, now
from autonomous_gemini35 import ENDPOINT, MODEL
from studio_server import Studio


class Reply(BytesIO):
    status=200

    def __init__(self,value):
        super().__init__(json.dumps(value,ensure_ascii=False).encode())


class GeneralResearchTests(TestCase):
    def test_existing_job_report_revision_and_approval_without_production(self):
        with TemporaryDirectory() as temp:
            studio=Studio(Path(temp)/'studio')
            goal='모바일 게임 쇼츠 주제 3개와 조회수·길이 조사. 승인 후에도 대본과 영상 제작 금지.'
            pid=studio.create(dict(goal=goal,audience='입문자',language='한국어',platform='YouTube Shorts',
                duration=None,notes='조사·기획만',key='00000000-0000-4000-8000-000000000044'))['id']
            job=studio.workflow.stage_mission_one(pid)
            before=studio.project('workspace',pid)
            def action(name,**body):
                return studio.action('workspace',pid,name,body)['research']
            key='fake-gemini-credential-123456789'
            env=dict(GEMINI_API_KEY=key,GEMINI_PRODUCTION_PROJECT_API_KEY=key,GEMINI35_MODEL=MODEL,
                GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1',
                TAVILY_RESEARCHER_FREE_ONLY='1',TAVILY_API_KEY='fake-tavily-credential-12345',
                YOUTUBE_DATA_API_KEY='fake-youtube-credential-12345')
            date=(datetime.fromisoformat(now())-timedelta(days=1)).isoformat()
            def youtube(request,timeout):
                if '/search?' in request.full_url:
                    return Reply(dict(items=[dict(id=dict(videoId='abcdefghijk'))]))
                self.assertIn('/videos?',request.full_url)
                return Reply(dict(items=[dict(id='abcdefghijk',snippet=dict(title='게임 예시',publishedAt=date,
                    categoryId='20'),contentDetails=dict(duration='PT23S'),statistics=dict(viewCount='1234'))]))
            def model(request,timeout):
                context=json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
                self.assertEqual(context['target'],goal)
                if context['version']==2:
                    self.assertEqual(context['previous']['feedback'],'길이 선정 근거를 명확히 해 주세요.')
                if context['goal']=='Review video research':
                    row=context['evidence']['observations'][0]['sources'][0]
                    value=dict(action='use_with_limits',note='공개 표본 관측이며 Shorts 여부는 미확인',
                        topics=[dict(title=f'주제 {i}',rationale='공개 표본을 참고한 기획 가설',
                            length='23초 제안',visuals='직접 제작 설명 자료 검토',rights='unverified',
                            source_ids=[row['id']]) for i in range(3)])
                elif context['tools'] and 'youtube_sample' in [tool['name'] for tool in context['tools']]:
                    value=dict(decision=dict(tool='youtube_sample',option='sample',claims=[],feasibility=''))
                else:
                    value=dict(decision=dict(tool='finish',option='',feasibility='사용권은 별도 확인',
                        claims=[dict(statement='확인된 표본 범위가 제한적입니다.',assessment='unverified',citations=[])]))
                return Reply(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                    parts=[dict(text=json.dumps(value,ensure_ascii=False))]))],
                    usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=20,totalTokenCount=40)))
            from research_workflow import execute_research
            def simulated(*args,**kwargs):
                return execute_research(*args,**kwargs,provenance='offline_fixture')
            with patch('research_workflow.execute_research',side_effect=simulated),patch.dict('os.environ',env),patch('socket.socket.connect',side_effect=AssertionError('no external network')),patch(
                'socket.getaddrinfo',side_effect=AssertionError('no DNS')),patch('goal_dialogue_live.send_once',side_effect=model) as ai,patch(
                'employee_web_research.send_once',side_effect=youtube) as yt:
                detail=studio.detail('workspace',pid)
                self.assertFalse(detail['mission']['supported'])
                self.assertEqual(detail['research']['status'],'available')
                with self.assertRaisesRegex(CompanyError,'owner_policy_required'):
                    action('research-run')
                with self.assertRaisesRegex(CompanyError,'general_report_only'):
                    studio.action('workspace',pid,'mission-report',dict(job=job))
                action('research-approve',confirmed=True,review_hash=detail['research']['review_hash'])
                v1=action('research-run')
                self.assertEqual(v1['status'],'review')
                report=v1['reports'][0]['report']
                self.assertIn('views=1234',report['staff']['observations'][0]['sources'][0]['excerpt'])
                self.assertEqual(len(report['manager']['topics']),3)
                self.assertEqual(report['duration_sample'],[23])
                self.assertEqual(report['provenance'],'offline_fixture')
                with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                    action('research-run')
                with self.assertRaisesRegex(CompanyError,'general_report_changed'):
                    action('research-report-review',version=1,sha256='0'*64,action='approve',feedback='')
                next_version=action('research-report-review',version=1,sha256=report['sha256'],action='revise',
                                    feedback='길이 선정 근거를 명확히 해 주세요.')
                self.assertEqual(next_version['version'],2)
                self.assertEqual(next_version['proposal']['max_search_credits'],0)
                self.assertEqual(next_version['status'],'active')
                self.assertEqual(next_version['remaining']['gemini'],4)
                self.assertNotIn('review_hash',next_version)
                v2=action('research-run')
                self.assertEqual(v2['reports'][0]['report'],report)
                revised=v2['reports'][-1]['report']
                done=action('research-report-review',version=2,sha256=revised['sha256'],action='approve',feedback='')
                self.assertEqual(done['status'],'approved_report')
                with self.assertRaisesRegex(CompanyError,'general_report_only'):
                    studio.action('workspace',pid,'production-render',{})
                self.assertEqual(studio.project('workspace',pid),before)
                self.assertEqual(yt.call_count,2)
                self.assertEqual(ai.call_count,5)

    def test_branch_distinguishes_missing_evidence_from_rewording(self):
        from general_research_report import evidence_branch, manager_schema
        from web_research import evidence
        lead=evidence('https://example.com/guide','제작 안내','Short video guide','search_lead')
        feedback='최근 인기 게임과 실제 영상 조회수, 영상 길이, 관측 날짜 및 사용 조건을 확인해 주세요.'
        plan=evidence_branch(feedback,[dict(sources=[lead])],now())
        self.assertEqual(plan['route'],'collect')
        self.assertEqual(set(plan['missing']),{'recent_examples','rights_conditions','video_metrics'})
        self.assertEqual(evidence_branch('기존 문장 요약과 가독성을 개선해 주세요.',[],now())['route'],'rewrite')
        self.assertTrue(evidence_branch('조금 더 보완해 주세요.',[],now())['uncertain'])
        result=dict(observations=[dict(status='preserved',sources=[lead])])
        self.assertEqual(manager_schema(result,collection=True)['properties']['action']['enum'],['hold'])

    def test_new_evidence_step_schema_and_validation_reject_early_finish(self):
        from general_research_report import youtube_tool
        from research_workflow import step_worker
        from types import SimpleNamespace
        from web_research import evidence
        row=evidence('https://example.com/guide','Guide','Generic advice','search_lead')
        prior=[dict(tool='previous_report',option='saved',status='preserved',sources=[row])]
        tool=youtube_tool('mobile games','fixture-key-123456789')
        store=SimpleNamespace(root=Path('/tmp/offline-guard-schema'))
        base=dict(mode='general_research_report_v1',target='Research',revision_plan={'route':'collect'})
        worker=step_worker(store,base,{tool.name:tool},1,prior)
        self.assertEqual(worker.contract['schema']['properties']['decision']['properties']['tool']['enum'],['youtube_sample'])
        finish=dict(decision=dict(tool='finish',option='',claims=[
            dict(statement='New evidence missing',assessment='unverified',citations=[])],feasibility='Rights unknown'))
        with self.assertRaisesRegex(CompanyError,'research_new_evidence_required'):
            worker.validate_response(finish)
        after=prior+[dict(tool=tool.name,option='sample',status='empty',sources=[])]
        step_worker(store,base,{tool.name:tool},2,after).validate_response(finish)
        step_worker(store,{k:v for k,v in base.items() if k!='revision_plan'},{},1,prior).validate_response(finish)

    def test_work_scope_checks_total_expiry_key_and_changed_tools(self):
        from autonomous_company import digest
        from owner_operating_policy import OwnerOperatingPolicy
        from research_work_scope import proposal, check_stage, charge

        with TemporaryDirectory() as tmp:
            work=OwnerOperatingPolicy(Path(tmp)/'work',{'project':'fixture'})
            gemini=dict(id='research-1',model=MODEL,endpoint=ENDPOINT,
                        data_types=['approved_report'],max_cost_usd=0)
            stage=dict(units=[gemini])
            offer=proposal(work,stage)
            work.approve(offer,digest(offer),'fixture')
            with self.assertRaisesRegex(CompanyError,'owner_policy_key_changed'):
                check_stage(work,'other-key',stage)
            changed=dict(units=[{**gemini,'data_types':['private_media']}])
            with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                check_stage(work,'fixture',changed)
            with patch('owner_operating_policy.now',return_value='2099-01-01T00:00:00+09:00'):
                with self.assertRaisesRegex(CompanyError,'owner_policy_expired'):
                    check_stage(work,'fixture',stage)
            charge(work,'fixture',gemini,digest('a'),lambda check:check())
            self.assertEqual(check_stage(work,'fixture',stage)[1]['gemini'],2)
            def failed(_check):
                raise TimeoutError
            with self.assertRaises(TimeoutError):
                charge(work,'fixture',gemini,digest('b'),failed)
            with self.assertRaisesRegex(CompanyError,'owner_policy_unresolved_attempt'):
                check_stage(work,'fixture',stage)

        with TemporaryDirectory() as tmp:
            work=OwnerOperatingPolicy(Path(tmp)/'work',{'project':'fixture'})
            offer=proposal(work,stage)
            work.approve(offer,digest(offer),'fixture')
            for i in range(3):
                charge(work,'fixture',gemini,digest(i),lambda check:check())
            with self.assertRaisesRegex(CompanyError,'owner_policy_exhausted'):
                check_stage(work,'fixture',stage)
