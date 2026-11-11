"""Existing company planning callbacks and real isolated local rendering."""
from pathlib import Path
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from autonomous_company import CompanyError, MockEmployeeProvider, MockManagerProvider, Store
from production_video import TOOL
from quality_workflow import VideoQualityCompany
from representative_workflow import RepresentativeVideoWorkflow
from tests.test_script_quality import script_callbacks, script_from_beats

AUDIENCE = '한국어 스포츠 입문자'


def plan_job(store, job_id, revision, expected_feedback):
    captions = ['점수 읽기', '홈과 원정', '가상 점수', '팀과 점수', '한 번 더']
    lines = ['점수는 어떻게 읽을까요?', '먼저 홈과 원정을 구분합니다.',
             '가상 점수는 이 대 일입니다.', '팀 이름 옆 점수를 봅니다.', '팀과 점수를 함께 확인하세요.']
    if revision > 1:
        lines[3] = '홈 팀 점수를 먼저 짚습니다.' if revision == 2 else '원정 팀 점수도 짚어 봅니다.'
    beats = [dict(start=a, end=b, narration=line, caption=caption, screen=f'자체 가상 그래픽 {caption}',
                  shot_type='demo' if a == 15 else 'detail', source_ref='자체 가상 점수판',
                  source_status='local_example', fact_status='illustrative')
             for a, b, line, caption in zip((0, 3, 15, 30, 45), (3, 15, 30, 45, 60), lines, captions)]
    value = script_from_beats(beats)
    value.update(target_audience=AUDIENCE, topic=dict(title='가상 점수판 읽기', freshness='evergreen'),
        viewer_problem='점수표의 팀 순서가 헷갈림', promise='가상 점수에서 팀 순서 찾기',
        viewing_reason='한 화면으로 홈·원정 구분', payoff='팀 이름과 숫자 대응')
    manager, employee = script_callbacks(value, value)

    def work(phase, context):
        received = context['quality']['answers']['representative_feedback']
        assert (received and received['feedback']) == expected_feedback
        return employee(phase, context)

    result = VideoQualityCompany(store, MockManagerProvider('fixture-manager', manager),
                                 MockEmployeeProvider('fixture-staff', work)).run(job_id)
    assert result['reason_code'] == 'manager_final_stopped', result['reason_code']
    return dict(tool=TOOL, width=640, height=360, series='가상 스포츠 예시',
        palette=dict(background='#132138', surface='#263955', accent='#72E7D7', text='#FFFFFF'),
        audio_mode='espeak_reference',
        scenes=[dict(title=b['caption'], subtitle=b['caption'], narration=b['narration'],
            seconds=b['end'] - b['start'], graphic=dict(kind='target', labels=[b['caption']]),
            camera='hold', transition='cut') for b in beats])


def run_cycle(root):
    store = Store(root)
    flow = RepresentativeVideoWorkflow(store)
    pid = flow.create('가상 스포츠 점수판을 읽는 1분 영상', audience=AUDIENCE,
                      constraints=dict(aspect='16:9', duration_seconds=60, audio_required=True))

    def must_block(code, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except CompanyError as exc:
            assert exc.code == code, (code, exc.code)
        else:
            raise AssertionError(code)

    def plan(revision, feedback=None):
        spec = plan_job(store, flow.start_planning(pid), revision, feedback)
        fields = dict(summary='가상의 점수판 읽기', sources=[], risks='가상 예시 및 로봇식 참조 음성',
                      changes=feedback or '첫 기획안')
        bad = {**spec, 'scenes': [{**spec['scenes'][0], 'narration': '승인할 대본과 다른 발화'}, *spec['scenes'][1:]]}
        must_block('representative_render_script_mismatch', flow.report_plan, pid, **fields, render_spec=bad)
        return flow.report_plan(pid, **fields, render_spec=spec)

    def decide(stage, report, action, feedback='', **kwargs):
        return flow.decide(pid, stage, version=report['version'], sha256=report['sha256'],
            action=action, feedback=feedback, provenance='offline_fixture', **kwargs)

    def make(report, **kwargs):
        return flow.produce(pid, version=report['version'], sha256=report['sha256'], changes='검증용 로컬 작업', **kwargs)

    p1 = plan(1)
    must_block('representative_stage_mismatch', make, p1)
    decide('plan', p1, 'request_revision', '홈 팀 점수를 먼저 짚어 주세요.')
    p2 = plan(2, '홈 팀 점수를 먼저 짚어 주세요.')
    must_block('stale_representative_report', decide, 'plan', p1, 'approve')
    decide('plan', p2, 'approve')
    must_block('representative_stage_mismatch', decide, 'plan', p2, 'approve')
    must_block('stale_representative_report', make, p1)
    v1 = make(p2)
    decide('video', v1, 'request_revision', '카메라를 가까이 이동해 주세요.')
    v2 = make(p2, cameras=['push_in'] * 5)
    assert v1['artifact_sha256'] != v2['artifact_sha256']
    must_block('stale_representative_report', decide, 'video', v1, 'approve')
    decide('video', v2, 'request_revision', '원정 팀 점수도 대본에 넣어 주세요.', changes_plan=True)
    must_block('representative_stage_mismatch', make, p2)
    p3 = plan(3, '원정 팀 점수도 대본에 넣어 주세요.')
    decide('plan', p3, 'approve')
    must_block('stale_representative_report', make, p2)
    v3 = make(p3)
    artifact = Path(root)/v3['artifact']
    renamed = artifact.with_suffix('.held')
    artifact.rename(renamed)
    must_block('representative_artifact_missing', decide, 'video', v3, 'approve')
    renamed.rename(artifact)
    with artifact.open('ab') as stream:
        stream.write(b'x')
    must_block('representative_artifact_changed', decide, 'video', v3, 'approve')
    with artifact.open('r+b') as stream:
        stream.truncate(artifact.stat().st_size - 1)
    decide('video', v3, 'approve', '가상 영상 검증 완료')
    result = store.result(pid)['representative']
    assert result['stage'] == 'completed' and result['final_video']['sha256'] == v3['sha256']
    assert result['final_video']['render_receipt']['audio']
    assert all((Path(root)/v['artifact']).is_file() for v in result['video_versions'])
    assert result['experiences'][0]['extraction_source'] == 'offline_fixture'
    assert result['experiences'][0]['verification'] == 'hypothesis'
    assert len(result['video_versions']) == len(result['plan_versions']) == 3
    return pid, result


class RepresentativeWorkflowTests(unittest.TestCase):
    def test_full_cycle_with_real_local_mp4_and_audio(self):
        with TemporaryDirectory() as root, patch('socket.socket.connect', side_effect=AssertionError('offline')):
            run_cycle(root)

    def test_failed_render_reservation_and_fresh_manual_attempt(self):
        with TemporaryDirectory() as root:
            store = Store(root)
            flow = RepresentativeVideoWorkflow(store)
            pid = flow.create('가상 스포츠 점수판', audience=AUDIENCE)
            spec = plan_job(store, flow.start_planning(pid), 1, None)
            plan = flow.report_plan(pid, summary='가상 예시', sources=[], risks='기술 시안', changes='초안',
                                    render_spec=spec)
            flow.decide(pid, 'plan', version=plan['version'], sha256=plan['sha256'], action='approve',
                        provenance='offline_fixture')
            for error in (CompanyError('test_render_failure'), KeyboardInterrupt()):
                with patch('representative_workflow.render', side_effect=error) as render_mock:
                    with self.assertRaises(type(error)):
                        flow.produce(pid, version=plan['version'], sha256=plan['sha256'], changes='로컬 제작')
                    render_mock.assert_called_once()
            state = store.load(pid)['representative']
            self.assertEqual(state['stage'], 'production')
            self.assertEqual([a['status'] for a in state['render_attempts']], ['failed', 'reserved'])
            self.assertFalse(state['video_versions'])
            with self.assertRaisesRegex(CompanyError, 'representative_render_uncertain'):
                flow.produce(pid, version=plan['version'], sha256=plan['sha256'], changes='미확정 중복 금지')
