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
        self.exercise_report()

    def test_confirmed_option_rejection_requires_new_signed_remaining_scope(self):
        self.exercise_report(repair=True)

    def exercise_report(self, *, repair=False):
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
            payloads=[]
            def model(request,timeout):
                wire=json.loads(request.data)
                context=json.loads(wire['contents'][0]['parts'][0]['text'])
                payloads.append(request.data)
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
                    options=wire['generationConfig']['responseJsonSchema']['properties']['decision']['properties']['option']['enum']
                    self.assertIn('sample',options)
                    self.assertNotIn('',options)
                    # 'topic' is a valid key for web search, but not for YouTube.
                    option='topic' if repair and len(payloads)==1 else 'sample'
                    value=dict(decision=dict(tool='youtube_sample',option=option,claims=[],feasibility=''))
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
                if repair:
                    from general_research_report import versions
                    from research_work_scope import envelope
                    with self.assertRaisesRegex(CompanyError,'research_step_invalid'):
                        action('research-run')
                    base,parent,_=versions(studio.workflow,before)
                    old_work=envelope(parent,base)
                    ledger_before=(parent.attempts(),old_work.attempts(),old_work.read('policy.json'))
                    stopped=studio.detail('workspace',pid)['research']
                    self.assertTrue(stopped['continuation_state']['can_contract_repair'])
                    with self.assertRaisesRegex(CompanyError,'owner_policy_unresolved_attempt'):
                        action('research-run')
                    with patch('general_research_continuation.now',return_value='2099-01-01T00:00:00+09:00'):
                        with self.assertRaisesRegex(CompanyError,'research_continuation_blocked'):
                            action('research-checkpoint',route='contract_repair')
                    prepared=action('research-checkpoint',route='contract_repair')
                    self.assertEqual(prepared['status'],'available')
                    self.assertEqual(prepared['work_scope']['limits'],dict(gemini=6,tavily=1,youtube=2))
                    with self.assertRaisesRegex(CompanyError,'owner_policy_required'):
                        action('research-run')
                    with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                        action('research-approve',confirmed=True,review_hash=detail['research']['review_hash'])
                    action('research-approve',confirmed=True,review_hash=prepared['review_hash'])
                    self.assertEqual(ai.call_count,1)
                    child_base,child,_=versions(studio.workflow,before)
                    self.assertLessEqual(envelope(child,child_base).read('policy.json')['expires_at'],
                                         ledger_before[2]['expires_at'])
                    from research_workflow import ResearchStep
                    with patch.object(ResearchStep,'_payload',return_value=json.loads(payloads[0])):
                        with self.assertRaisesRegex(CompanyError,'research_continuation_blocked'):
                            action('research-run')
                    self.assertEqual(ai.call_count,1)
                    self.assertEqual(child.attempts(),{})
                v1=action('research-run')
                if repair:
                    self.assertEqual((parent.attempts(),old_work.attempts(),old_work.read('policy.json')),ledger_before)
                    self.assertNotEqual(payloads[0],payloads[1])
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
                self.assertEqual(next_version['remaining']['gemini'],3 if repair else 4)
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
                self.assertEqual(ai.call_count,6 if repair else 5)

    def test_provider_failure_continuation_uses_only_new_work(self):
        from urllib.error import HTTPError
        from general_research_report import versions
        from research_workflow import execute_research

        key='fake-gemini-credential-123456789'
        env=dict(GEMINI_API_KEY=key,GEMINI_PRODUCTION_PROJECT_API_KEY=key,GEMINI35_MODEL=MODEL,
                 GEMINI35_ENDPOINT=ENDPOINT,GEMINI35_AUTONOMOUS_FREE_ENABLED='1',
                 TAVILY_RESEARCHER_FREE_ONLY='1',TAVILY_API_KEY='fake-tavily-credential-12345',
                 YOUTUBE_DATA_API_KEY='fake-youtube-credential-12345')
        for http in (400,401,403,429,503,None):
            with self.subTest(http=http), TemporaryDirectory() as temp, patch.dict('os.environ',env):
                studio=Studio(Path(temp)/'studio')
                pid=studio.create(dict(goal='모바일 게임 조사',audience='입문자',language='한국어',platform='YouTube Shorts',
                    duration=None,notes='조사만',key='00000000-0000-4000-8000-000000000047'))['id']
                studio.workflow.stage_mission_one(pid)

                def action(name,**body):
                    return studio.action('workspace',pid,name,body)['research']

                def status():
                    return studio.detail('workspace',pid)['research']

                payloads=[]
                def model(request,timeout):
                    payloads.append(request.data)
                    wire=json.loads(request.data)
                    context=json.loads(wire['contents'][0]['parts'][0]['text'])
                    self.assertEqual(request.get_method(),'POST')
                    self.assertEqual(request.full_url,ENDPOINT)
                    self.assertEqual(request.get_header('Content-type'),'application/json')
                    self.assertEqual(request.get_header('X-goog-api-key'),key)
                    self.assertEqual(wire['generationConfig']['maxOutputTokens'],4096)
                    self.assertNotIn('anyOf',json.dumps(wire['generationConfig']['responseJsonSchema']))
                    if len(payloads)==1:
                        value=dict(decision=dict(tool='web_search',option='topic',claims=[],feasibility=''))
                    elif len(payloads)==2:
                        if http is None:
                            raise TimeoutError
                        body=dict(error=dict(status='INVALID_ARGUMENT',
                            message='Schema is too complex. private provider text',
                            details=[dict(fieldViolations=[
                                dict(field='generation_config.response_json_schema.properties.private-field'),
                                dict(field='secret-field')])]))
                        raise HTTPError('https://example.com',http,'fixture',{},Reply(body))
                    elif context['goal']=='Review video research':
                        value=dict(action='hold',note='표본 부족',topics=[
                            dict(title=f'가설 {i}',rationale='추가 확인 필요',length='20초 제안',
                                 visuals='미확인',rights='unverified',source_ids=[]) for i in range(3)])
                    else:
                        self.assertEqual([row['tool'] for row in context['observations']],
                                         ['web_search','youtube_sample'])
                        self.assertNotIn('continuation',context)
                        value=dict(decision=dict(tool='finish',option='',feasibility='권리 미확인',
                            claims=[dict(statement='확인할 자료가 부족합니다.',assessment='unverified',citations=[])]))
                    return Reply(dict(candidates=[dict(finishReason='STOP',content=dict(role='model',
                        parts=[dict(text=json.dumps(value))]))],
                        usageMetadata=dict(promptTokenCount=20,candidatesTokenCount=20,totalTokenCount=40)))

                from web_research import evidence
                lead=evidence('https://example.com/guide','Guide','Generic advice','search_lead')
                with patch('socket.socket.connect',side_effect=AssertionError('no network')), patch(
                    'socket.getaddrinfo',side_effect=AssertionError('no DNS')), patch(
                    'goal_dialogue_live.send_once',side_effect=model), patch(
                    'research_workflow.tavily_search',return_value=[lead]) as tavily, patch(
                    'employee_web_research.send_once',return_value=Reply(dict(items=[]))) as youtube, patch(
                    'research_workflow.execute_research',
                    side_effect=lambda *a,**kw:execute_research(*a,**kw,provenance='offline_fixture')):
                    initial=status()
                    action('research-approve',confirmed=True,review_hash=initial['review_hash'])
                    with self.assertRaisesRegex(CompanyError,'transport_or_response_failed'):
                        action('research-run')
                    project=studio.project('workspace',pid)
                    _,source,_=versions(studio.workflow,project)
                    before={path:path.read_bytes() for path in source.root.iterdir() if path.is_file()}
                    stopped=status()
                    checkpoint=stopped['continuation_state']
                    self.assertEqual(stopped['status'],'stopped')
                    self.assertEqual(checkpoint['sources'],1)
                    self.assertEqual(set(checkpoint['completed']),{'research-0','general-web'})
                    self.assertEqual(checkpoint['response'].get('http_status'),http)
                    for secret in ('private provider text','private-field','secret-field'):
                        self.assertNotIn(secret,json.dumps(stopped))
                    if http==400:
                        self.assertEqual(checkpoint['response']['field_groups'],['response_schema'])
                        self.assertTrue(checkpoint['response']['response_schema_complexity_hint'])
                        self.assertGreater(checkpoint['response']['error_body_bytes'],0)
                    self.assertEqual(checkpoint['can_collect'],http==400)
                    self.assertFalse(checkpoint['can_contract_repair'])
                    with self.assertRaisesRegex(CompanyError,'research_continuation_blocked'):
                        action('research-checkpoint',route='contract_repair')
                    failure_types={400:'request_rejected',401:'authentication_or_permission',
                                   403:'authentication_or_permission',429:'quota_or_billing',
                                   503:'provider_unavailable',None:'transmission_uncertain'}
                    self.assertEqual(stopped['diagnostics']['failure']['failure_type'],failure_types[http])
                    with self.assertRaises(CompanyError):
                        action('research-run')
                    if http==400:
                        ready=action('research-checkpoint',route='collect')
                        self.assertEqual(ready['status'],'available')
                        self.assertEqual(ready['work_scope']['limits'],dict(gemini=2,youtube=2))
                        self.assertEqual(len(payloads),2)
                        with self.assertRaisesRegex(CompanyError,'owner_policy_required'):
                            action('research-run')
                        with self.assertRaisesRegex(CompanyError,'owner_policy_scope_changed'):
                            action('research-approve',confirmed=True,review_hash=initial['review_hash'])
                        action('research-approve',confirmed=True,review_hash=ready['review_hash'])
                        final=action('research-run')
                        self.assertEqual(final['status'],'review')
                        report=final['reports'][0]['report']
                        self.assertEqual(report['staff']['observations'][0]['sources'],[lead])
                        self.assertEqual(report['manager']['action'],'hold')
                        self.assertEqual(report['provenance'],'offline_fixture')
                        self.assertEqual(len(set(payloads)),4)
                        youtube.assert_called_once()
                    else:
                        with self.assertRaisesRegex(CompanyError,'research_continuation_blocked'):
                            action('research-checkpoint',route='collect')
                        self.assertEqual(action('research-checkpoint',route='hold')['continuation_state']['route'],'hold')
                        self.assertEqual(len(payloads),2)
                        youtube.assert_not_called()
                    tavily.assert_called_once()
                    self.assertTrue(all(path.read_bytes()==raw for path,raw in before.items()))

    def test_general_wire_schema_keeps_citation_rules_in_local_validation(self):
        from types import SimpleNamespace
        from research_workflow import step_worker
        from web_research import evidence

        rows=[evidence(f'https://example.com/video/{i}',f'Video {i}',f'Sample {i}','api_metric')
              for i in range(34)]
        observations=[dict(tool='previous_report',option='saved',status='preserved',sources=rows)]
        store=SimpleNamespace(root=Path('/tmp/offline-report-wire'))
        base=dict(mode='general_research_report_v1',target='Research')
        worker=step_worker(store,base,{},10,observations,rounds=11)
        wire=worker._payload(None)['generationConfig']['responseJsonSchema']
        properties=wire['properties']['decision']['properties']
        self.assertEqual(properties['option']['enum'],[''])
        citations=properties['claims']['items']['properties']['citations']
        self.assertEqual(citations['items'],{'type':'string'})
        value=dict(decision=dict(tool='finish',option='',feasibility='권리 확인 필요',
                                 claims=[dict(statement='검증 전',assessment='unverified',
                                              citations=[rows[-1]['id']])]))
        worker.validate_response(value)
        value['decision']['claims'][0]['citations']=['unknown']
        with self.assertRaisesRegex(CompanyError,'research_evidence_invalid'):
            worker.validate_response(value)

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
        wire=worker._payload(None)['generationConfig']['responseJsonSchema']
        self.assertEqual(wire['properties']['decision']['properties']['option']['enum'],['sample'])
        with self.assertRaisesRegex(CompanyError,'research_step_invalid') as invalid:
            worker.validate_response(dict(decision=dict(tool=tool.name,option='mobile games',claims=[],feasibility='')))
        self.assertEqual(invalid.exception.rule,'option_not_allowed')
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

    def test_adaptive_query_choices_have_separate_signed_requests(self):
        from general_research_report import discovery_queries, youtube_tool
        queries=discovery_queries(dict(target='모바일 국내 게임 조사',previous={'manager':{'topics':[{'game':'유효 게임'}]}}))
        self.assertEqual(len(queries),len(set(queries)))
        self.assertGreater(len(queries),3)
        self.assertIn('유효 게임 gameplay shorts', queries)
        tools=[youtube_tool(q,'fixture-credential-not-used',variant=i) for i,q in enumerate(queries)]
        ids=[item['id'] for tool in tools for item in tool.requests]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual({tool.requests[0]['lookback_days'] for tool in tools},{30,60,90})

    def test_mobile_games_require_attributed_dated_metadata_and_distinct_titles(self):
        from general_research_report import manager_schema, validate_manager
        from mobile_game_evidence import game_evidence, planned_queries
        from web_research import evidence

        stamp=now()
        def row(index,title):
            return evidence(f'https://youtu.be/abcdefghij{index}',title,
                            'YouTube Data API views=100; duration_seconds=20. Sample.',
                            'api_metric','youtube_data_api',stamp,stamp)
        minecraft=[row(i,f'Minecraft play {i}') for i in range(5)]
        result=dict(at=stamp,observations=[dict(status='preserved',sources=minecraft)])
        refs=game_evidence(result['observations'],stamp)
        self.assertEqual({entry['game'] for entry in refs.values()},{'마인크래프트'})
        self.assertEqual(manager_schema(result,collection=True,diverse=True)['properties']['action']['enum'],['hold'])
        self.assertFalse(any('Minecraft' in query or '마인크래프트' in query
                             for _,query in planned_queries(result['observations'],stamp)))
        broad=[row(5,'Brawl Stars ranked'),row(6,'Genshin Impact battle'),row(7,'Unknown mobile title'),
               row(8,'Minecraft vs Brawl Stars'),row(5,'Minecraft conflicting title')]
        result['observations'].append(dict(status='observed',sources=broad))
        self.assertEqual(len({entry['game'] for entry in game_evidence(result['observations'],stamp).values()}),2)
        result['observations'][-1]['sources'].pop()
        candidates=[dict(game=game,title=game,rationale='metadata only',length='20초',visuals='unverified',
                         rights='unverified',source_ids=[source['id']])
                    for game,source in zip(('마인크래프트','브롤스타즈','원신'),[minecraft[0],*broad[:2]],strict=True)]
        value=dict(action='use_with_limits',topics=candidates)
        validate_manager(value,result,collection=True,diverse=True)
        candidates[1]['source_ids']=[minecraft[1]['id']]
        with self.assertRaisesRegex(CompanyError,'research_evidence_invalid'):
            validate_manager(value,result,collection=True,diverse=True)
