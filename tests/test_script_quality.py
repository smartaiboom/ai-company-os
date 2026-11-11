import json
import socket
from copy import deepcopy
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from autonomous_company import MockEmployeeProvider, MockManagerProvider, Store, digest
from quality_feedback import bind_context
from quality_workflow import VideoQualityCompany
from script_quality import CRITERIA, SCRIPT_CONTRACT, inspect_script, script_editor_handoff
from voice_quality import AUDIENCE


def script_from_beats(beats):
    return dict(contract=SCRIPT_CONTRACT, target_audience=AUDIENCE,
        topic=dict(title='약속 안내 문자에 들어갈 조건', freshness='evergreen'),
        viewer_problem='받는 사람과 시각이 빠진 약속 안내 문자는 바로 쓰기 어렵다.',
        promise='누구에게, 언제 어디서, 어떤 말투로 보낼지 한 요청에 적는다.',
        viewing_reason='모호한 요청과 전송 전 확인할 문자 예시를 한 화면에서 비교한다.',
        hook_0_3s=beats[0]['narration'], payoff='날짜·시간·장소를 화면에서 원문과 나란히 대조한다.',
        narrative_beats=beats, close=beats[-1]['narration'],
        transcript='\n'.join(beat['narration'] for beat in beats), target_duration=60,
        estimation_method='장면 배분과 공백 제외 초당 6자 상한. 실제 발화 시간 미측정.',
        unknowns=['화면 녹화와 실제 낭독 시간이 아직 없다.'],
        provenance=dict(author='codex-authored candidate', model=None, mock=True))


def script_callbacks(draft, revision, *, accept_defective=False, editor_transform=None):
    """Explicit authored callbacks; the engine itself owns attempts and revision state."""
    def checks(ids, issues=(), final=False):
        return [dict(criterion_id=criterion,
            status='unknown' if final else ('unmet' if criterion in issues else 'met'),
            source='model_claim', evidence='오프라인 계약 검사 범위. 재미·유지율은 미평가.')
            for criterion in ids]

    def manager(phase, context):
        if phase == 'plan':
            return json.dumps(dict(criteria=[dict(id=k, description=v) for k, v in CRITERIA.items()],
                tasks=[dict(id=role, role=role, title=role, depends_on=deps, criteria_ids=ids,
                            instructions='고정 장면 반복을 줄이고 시연 근거와 수정본을 연결한다.')
                    for role, deps, ids in [('writer', [], list(CRITERIA)),
                                            ('editor', ['writer'], ['editability'])]],
                rationale='초보자에게 재사용 가능한 요청 한 가지', uncertainty='실제 시청 평가 대기'))
        if phase == 'review':
            defects = context.get('plan_inspection', {}).get('defects', [])
            revise = bool(defects) and not accept_defective
            return json.dumps(dict(action='revise' if revise else 'accept',
                rationale='결함은 수정 후 다시 검사한다.' if revise else '텍스트 인수 범위를 확인했다.',
                evidence=json.dumps(defects, ensure_ascii=False) if defects else '현재 버전의 인수 검사 통과',
                uncertainty='사용자 매력·유지율 평가 없음', operation=None,
                feedback='\n'.join(f"{d['issue']} [{d['severity']}/{d['owner']}] {d['evidence']} → {d['correction']}"
                                   for d in defects) if revise else '',
                checks=checks([c['id'] for c in context['criteria']], {d['criterion'] for d in defects} if revise else ())))
        return json.dumps(dict(action='stop', content='수정 대본과 편집 인수 기록 보존',
            rationale='사용자 검토 대기', uncertainty='실제 촬영·낭독 없음', checks=checks(CRITERIA, final=True),
            task_refs=[dict(task_id=r['task_id'], revision=r['revision'], result_hash=digest(r))
                       for r in context['results']]))

    def employee(phase, context):
        if context['assignment']['role'] == 'writer':
            if context['revision_feedback']:
                assert json.loads(context['version_history'][-1]['content']) == draft
                assert 'missing_demo' in context['revision_feedback']
                value = revision
            else:
                value = draft
        else:
            value = script_editor_handoff(context['previous_results'][0])
            if editor_transform:
                editor_transform(value)
        return json.dumps(dict(content=json.dumps(value, ensure_ascii=False),
            evidence='Codex-authored callback', uncertainty='미확보 소스 및 청취 평가 대기'), ensure_ascii=False)

    return manager, employee


def run_script_case(store, project_id, draft, revision, **kwargs):
    manager, employee = script_callbacks(draft, revision, **kwargs)
    return VideoQualityCompany(store, MockManagerProvider('codex-script-manager', manager),
                               MockEmployeeProvider('codex-script-writer-editor', employee)).run(project_id)


def bind_script_case(store, experiences=None):
    project = store.create('AI 초보자에게 ChatGPT 활용법을 소개하는 1분 영상', opt_in=True,
        max_calls=8, max_revisions_per_task=1, max_total_revisions=1)
    bind_context(store, project['id'], dict(answers=dict(audience=AUDIENCE),
        constraints=dict(new_media=False, priority='script_quality'),
        capabilities=dict(script_contract=SCRIPT_CONTRACT),
        experiences=experiences or dict(selected=[]), permissions=dict(external_calls=False, cost_limit=0)))
    return project['id']


class ScriptQualityTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('offline')))
        self.store = Store(self.root)
        self.project = bind_script_case(self.store)

        def beat(start, end, text, shot):
            return dict(start=start, end=end, narration=text, caption='약속 안내', screen='예시 화면',
                shot_type=shot, source_ref='가상 문자 예시', source_status='pending', fact_status='illustrative')
        self.draft = script_from_beats([beat(0, 3, '약속은 몇 시죠?', 'card'),
                                       beat(3, 30, '조건을 써요.', 'card'),
                                       beat(30, 60, '조건을 써요.', 'card')])
        self.revision = script_from_beats([beat(0, 3, '약속은 몇 시죠?', 'detail'),
                                          beat(3, 30, '시간과 장소를 요청에 적어요.', 'demo'),
                                          beat(30, 60, '보내기 전에 한 번 더 확인해요.', 'detail')])

    def test_revision_and_editor_receive_only_accepted_version(self):
        result = run_script_case(self.store, self.project, self.draft, self.revision)
        self.assertEqual(result['reason_code'], 'manager_final_stopped')
        self.assertEqual(len(result['attempts']), 8)
        self.assertEqual(result['artifacts'], {})
        writer, editor = result['assignments']
        self.assertEqual([r['action'] for r in writer['reviews']], ['revise', 'accept'])
        before, after = writer['plan_inspections']
        self.assertEqual(after['previous_artifact_hash'], before['artifact_hash'])
        self.assertEqual(after['resolved_issue_types'], ['missing_demo', 'repeated_narration'])
        self.assertEqual(after['defects'], [])
        self.assertEqual(after['audience_appeal'], 'unassessed')
        handoff = json.loads(editor['versions'][0]['content'])
        self.assertEqual(handoff['writer_ref']['revision'], 2)
        self.assertEqual(handoff['writer_ref']['result_hash'], digest(writer['versions'][1]))

    def test_defective_accept_and_stale_editor_reference_fail_closed(self):
        result = run_script_case(self.store, self.project, self.draft, self.revision, accept_defective=True)
        self.assertEqual(result['reason_code'], 'known_script_defects')
        self.assertEqual(result['assignments'][1]['versions'], [])
        project = bind_script_case(self.store)
        result = run_script_case(self.store, project, self.draft, self.revision,
            editor_transform=lambda value: value['writer_ref'].update(revision=1))
        self.assertEqual(result['reason_code'], 'script_editor_handoff_mismatch')

    def test_caption_timing_and_freshness_are_checked_without_appeal_score(self):
        value = deepcopy(self.revision)
        value['narrative_beats'][1].update(start=4, caption='길' * 30)
        value['topic']['freshness'] = 'current'
        result = inspect_script(value, AUDIENCE, mock=True)
        self.assertEqual({d['issue'] for d in result['defects']},
            {'timeline_gap_or_overlap', 'caption_width', 'current_claim_unflagged'})
        self.assertEqual(result['retention'], 'unassessed')
