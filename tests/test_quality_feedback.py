"""Offline contract/integration scenarios. Authored fixture judgments are NOT AI inference."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_company import Store, CompanyError, MockManagerProvider, MockEmployeeProvider, digest
from quality_feedback import ExperienceJournal, bind_context
from quality_workflow import VideoQualityCompany, capabilities, inspect_plan, checklist


class VideoFixtures:
    """Deliberately poor first drafts and authored corrections, only for offline tests."""
    def __init__(self, *, fail=False, interrupt=False, always_revise=False):
        self.contexts=[]; self.fail=fail; self.interrupt=interrupt; self.always_revise=always_revise
        self.manager=MockManagerProvider('offline-video-manager-fixture', self.manage)
        self.employee=MockEmployeeProvider('offline-video-employee-fixture', self.work)

    def manage(self, phase, c):
        self.contexts.append((phase,deepcopy(c)))
        if phase == 'plan':
            value=dict(criteria=[dict(id='plan',description='60초 대본/샷/음성 지시서; 실제 제작과 게시 품질은 미평가')],
                rationale='초보자에게 AI에 질문하는 한 가지 방법을 실제 입력 예로 설명; 10개 기능 나열은 과밀하여 제외.',
                uncertainty='모의 전략. 사실/시청/청취·권리는 검증하지 않음. 외부 전송 불허.', tasks=[
                dict(id='script',title='한국어 대본',role='writer',depends_on=[],criteria_ids=['plan'],
                     instructions='초보자 대상 한 메시지: 목적과 조건을 함께 적기. 0~3초 질문 후크→입력 사례→시연→마무리. 총60초.'),
                dict(id='shots',title='장면별 소스 계획',role='editor',depends_on=['script'],criteria_ids=['plan'],
                     instructions='인수 대본 문장에 대응하는 60초 샷; 6초 소스10개, 화면녹화 시연 포함. 수동 소스 확보 대기.'),
                dict(id='speech',title='음성 지시',role='voice',depends_on=['script','shots'],criteria_ids=['plan'],
                     instructions='대본과 장면 인수; 쉬운 한국어 발음, 친근한 톤과 속도. MeloTTS 한계 기록. 청취 미평가.')])
        elif phase == 'review':
            role=c['assignment']['role'];result=c['result']
            # Authored scenario evaluation, not a keyword-based production manager.
            bland=role=='writer' and result['revision']==1
            defects=deepcopy(c['plan_inspection']['defects'])
            if bland:
                defects.append(dict(issue='bland_opening',owner='writer',severity='major',
                    evidence='segments[0]의 인사와 주제 소개가20초; 첫3초에 얻을 가치 없음 (fixture 평가)',
                    correction='첫3초에 구체적 실패 질문; 목적+조건 입력 사례로 교체',expected_metric='후크 구간3초'))
            revise=bool(defects) or self.always_revise
            value=dict(action='revise' if revise else 'accept',rationale='fixture 검토; 감각 품질 합격 아님',
                evidence=json.dumps(defects,ensure_ascii=False) if defects else '60초 계획 형식과 수정 기록 확인',
                uncertainty='텍스트와 계획만 확인; 실제 영상·음성 미평가',
                checks=[dict(criterion_id='plan',status='unmet' if revise else 'met',
                             evidence='제출된 계획 버전 비교',source='model_claim')],
                feedback=json.dumps(defects or [{'correction':'fixture 재수정 요청'}],ensure_ascii=False) if revise else '',operation=None)
        else:
            value=dict(action='deliver',content='대본·샷·음성 계획 패키지. 실제 영상은 미완료.',
                rationale='계획 검토 후 외부 소스 대기',uncertainty='영상/음성/권리 미평가',
                checks=[dict(criterion_id='plan',status='met',evidence='계획 인수 완료',source='model_claim')],
                task_refs=[dict(task_id=r['task_id'],revision=r['revision'],result_hash=digest(r)) for r in c['results']])
        return json.dumps(value,ensure_ascii=False)

    def work(self, phase, c):
        self.contexts.append((phase,deepcopy(c)))
        if self.interrupt: raise KeyboardInterrupt()
        if self.fail: raise TimeoutError()
        role=c['assignment']['role'];revised=bool(c['revision_feedback'])
        experiences=c['quality']['experiences']['selected']
        friendly=bool(experiences)
        if role=='writer':
            if not revised:
                value=dict(segments=[dict(seconds=20,text=t) for t in (
                    '안녕하세요. 오늘은 인공지능에 대해 알아보겠습니다.',
                    '인공지능에는 많은 기능이 있습니다.', '여러분도 사용해 보세요.')])
            else:
                intro='AI 답이 막막하세요? 조건을 함께 적어 봐요.' if friendly else 'AI 답이 모호한가요? 목적과 조건을 적으세요.'
                value=dict(segments=[dict(seconds=s,text=t) for s,t in [
                    (3,intro),(12,'질문을 구체적으로 적는 한 가지 방법을 보여 드릴게요.'),
                    (15,'저녁 메뉴를 알려 줘 대신 냉장고에 두부와 달걀이 있어요. 두 사람이 먹을 메뉴 하나를 제안해 줘라고 적어 보세요.'),
                    (15,'화면에서 두 질문을 비교해 보세요. 실제 답변과 조리 가능성은 직접 확인해야 해요.'),
                    (10,'목적, 가진 재료, 인원처럼 필요한 조건을 더해 보세요. 개인 정보는 넣지 마세요.'),
                    (5,'오늘 질문 하나에 조건을 더해 볼까요?')]])
        elif role=='editor':
            script=json.loads(c['previous_results'][0]['content'])
            count=10 if revised else 3;duration=6 if revised else 20
            value=dict(shots=[dict(seconds=duration,source_seconds=6,source_id=f'planned-{i}' if revised else 'same-clip',
                narration=script['segments'][min(i*len(script['segments'])//count,len(script['segments'])-1)]['text'],
                source_status='planned') for i in range(count)])
        else:
            value=dict(instructions=('30~40대 주부에게 친근하게, 분당 약260음절을 시작점으로 실측 조정' if friendly
                                     else '성인 초보자에게 차분하고 또렷하게; 속도는 발화 길이 실측 후 조정')+
                       '. MeloTTS는 기계적인 억양 가능, 자연스러움은 청취 전 unassessed.',
                       pronunciation='AI는 에이아이, 전문 용어는 쉬운 한국어로. 새 TTS 실행 없음.')
        return json.dumps(dict(content=json.dumps(value,ensure_ascii=False),
                               evidence='offline authored fixture; upstream hashes in handoff_refs',
                               uncertainty='실제 생성/시청/청취 없음'),ensure_ascii=False)


class QualityFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch('socket.socket.connect',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))
        self.journal=ExperienceJournal(self.root/'experiences');self.jid=self.journal.create()
        self.selection=dict(selected=[],excluded=[])

    def feedback(self):
        return self.journal.record(self.jid,'30~40대 주부용이면 친근한 말투가 좋겠다. 화면이 계속 반복된다.',dict(
            project='fixture-first',domain='video',target_segment='30~40대 주부',issue='같은 화면 반복',
            positive_preference='친근한 말투',proposed_correction='추가 샷과 친근한 대본·음성 지시',
            evidence='사용자 예시 문장; 실제 시청 검증 아님',source='user_example_in_instruction',
            confidence=.8,verification='hypothesis'),provenance='offline_fixture')

    def run_company(self, name, *, selection=None, model=None, **limits):
        store=Store(self.root/name);p=store.create('초보자용60초 세로영상: AI 질문 한 가지 방법',opt_in=True,**limits)
        context=dict(answers={'audience':'30~40대 주부'},constraints={'duration':60,'aspect':'9:16'},
            capabilities=capabilities(),experiences=selection or self.selection,
            permissions={'external_calls':False,'cost_limit':0})
        bind_context(store,p['id'],context)
        model=model or VideoFixtures();company=VideoQualityCompany(store,model.manager,model.employee)
        return store,company,p,model

    def test_full_revision_feedback_reuse_and_nonapplication(self):
        store,company,p,model=self.run_company('first')
        result=company.run(p['id'])
        self.assertEqual(result['status'],'external_clip_pending');self.assertFalse(result['artifacts'])
        writer,editor,voice=result['assignments']
        self.assertEqual([t['revisions'] for t in result['assignments']],[1,1,0])
        before=json.loads(writer['versions'][0]['content']);after=json.loads(writer['versions'][1]['content'])
        self.assertEqual(before['segments'][0]['seconds'],20);self.assertEqual(after['segments'][0]['seconds'],3)
        self.assertNotEqual(before,after)
        self.assertTrue(editor['plan_inspections'][0]['defects']);self.assertFalse(editor['plan_inspections'][1]['defects'])
        handoffs=[c for phase,c in model.contexts if phase=='execute' and c['previous_results']]
        self.assertEqual(handoffs[0]['previous_results'][0],writer['versions'][-1])
        self.assertEqual(handoffs[0]['handoff_refs'][0]['result_hash'],digest(writer['versions'][-1]))
        calls=len(result['attempts']);self.assertEqual(len(company.run(p['id'])['attempts']),calls)
        entry=self.feedback()
        same=self.journal.select(self.jid,domain='video',target_segment='30~40대 주부')
        other=self.journal.select(self.jid,domain='video',target_segment='초등학생')
        self.assertEqual(same['selected'][0]['id'],entry['id']);self.assertFalse(other['selected'])
        outputs=[]
        for name,selection in [('similar',same),('different',other)]:
            st,co,pr,mo=self.run_company(name,selection=selection)
            outputs.append(co.run(pr['id']))
        self.assertIn('막막하세요',outputs[0]['assignments'][0]['versions'][-1]['content'])
        self.assertIn('친근하게',outputs[0]['assignments'][2]['versions'][-1]['content'])
        self.assertEqual(outputs[1]['assignments'][0]['versions'][-1]['content'],writer['versions'][-1]['content'])
        self.assertNotEqual(outputs[0]['assignments'][2]['versions'][-1]['content'],voice['versions'][-1]['content'])
        self.assertIsNone(result['quality_checklist']['total'])
        sample=dict(provenance='offline fixtures, NOT live AI judgment',first=result,
                    feedback=entry,applied=same,not_applied=other,similar=outputs[0],different=outputs[1])
        target=os.environ.get('QUALITY_SAMPLE_OUTPUT')
        if target:
            path=Path(target);self.assertTrue(path.is_absolute() and path.is_relative_to('/tmp'))
            path.write_text(json.dumps(sample,ensure_ascii=False,indent=2))

    def test_revision_withdrawal_and_scope(self):
        e=self.feedback();fields={k:e[k] for k in ('project','domain','target_segment','issue','positive_preference',
            'proposed_correction','evidence','source','confidence','verification')}
        fields['positive_preference']='차분한 말투'
        new=self.journal.record(self.jid,'친근함 대신 차분하게',fields,provenance='user_structured',replaces=e['id'])
        self.assertEqual(new['version'],2)
        self.assertEqual(len(self.journal.select(self.jid,domain='video',target_segment='30~40대 주부')['selected']),1)
        self.assertFalse(self.journal.select(self.jid,domain='software',target_segment='30~40대 주부')['selected'])
        self.journal.withdraw(self.jid,new['id'],'사용자 철회')
        self.assertFalse(self.journal.select(self.jid,domain='video',target_segment='30~40대 주부')['selected'])
        self.assertEqual(len(self.journal.store.load(self.jid)['experiences']),2)

    def test_budget_revision_limit_and_failed_operation_do_not_retry(self):
        for name,model,limits,reason in [
            ('budget',VideoFixtures(),{'max_calls':2},'mock_budget_exhausted'),
            ('revisions',VideoFixtures(always_revise=True),{},'revision_limit'),
            ('failure',VideoFixtures(fail=True),{},'mock_provider_failed')]:
            with self.subTest(name=name):
                st,co,p,mo=self.run_company(name,model=model,**limits)
                result=co.run(p['id']);self.assertEqual(result['reason_code'],reason)
                calls=len(result['attempts']);self.assertEqual(len(co.run(p['id'])['attempts']),calls)
                self.assertFalse(result['artifacts'])

    def test_interruption_and_context_rebinding_blocked(self):
        st,co,p,mo=self.run_company('interrupted',model=VideoFixtures(interrupt=True))
        with self.assertRaises(KeyboardInterrupt):co.run(p['id'])
        self.assertEqual(co.run(p['id'])['reason_code'],'uncertain_operation')
        with self.assertRaises(CompanyError):bind_context(st,p['id'],st.load(p['id'])['quality_context'])

    def test_permissions_and_live_provider_rejected(self):
        st,co,p,mo=self.run_company('gates')
        context=deepcopy(st.load(p['id'])['quality_context']);context['permissions']['external_calls']=True
        with self.assertRaisesRegex(CompanyError,'offline_permissions_required'):bind_context(st,p['id'],context)
        with self.assertRaisesRegex(CompanyError,'mock_providers_only'):VideoQualityCompany(st,object(),mo.employee)
        self.assertFalse(capabilities()['external_api_enabled'])
        self.assertTrue(all(i['score'] is None for i in checklist()['items']))

    def test_untrusted_plan_cannot_be_accepted_or_scored(self):
        st,co,p,mo=self.run_company('dishonest')
        original=mo.manage
        def dishonest(phase,c):
            value=json.loads(original(phase,c))
            if phase=='review' and c['assignment']['role']=='editor':
                value['action']='accept';value['checks'][0]['status']='met'
            return json.dumps(value)
        mo.manager=MockManagerProvider('dishonest-fixture',dishonest)
        result=VideoQualityCompany(st,mo.manager,mo.employee).run(p['id'])
        self.assertEqual(result['reason_code'],'known_plan_defects');self.assertFalse(result['artifacts'])
        with self.assertRaises(CompanyError):inspect_plan('writer',{'segments':[dict(seconds=float('nan'),text='x')]})
