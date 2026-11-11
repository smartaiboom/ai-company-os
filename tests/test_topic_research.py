from copy import deepcopy
import json
from tempfile import TemporaryDirectory
import unittest

from autonomous_company import CompanyError, MockEmployeeProvider, MockManagerProvider, Store, digest
from quality_feedback import bind_context
from quality_workflow import VideoQualityCompany
from script_quality import CRITERIA, SCRIPT_CONTRACT
from topic_research import EDITORIAL_WEIGHTS, compare_topics, writer_topic_handoff

NOW = '2026-11-11T10:00:00+09:00'
BRIEF = dict(channel='AI 업무 팁', audience='한국어 AI 초보자', language='ko-KR',
    region='KR', aspect='9:16', duration_seconds=60)


def candidate(cid, score, sources=()):
    return dict(id=cid, topic=f'가상 주제 {cid}', title_hook='왜 다를까요?', who_cares='직장인',
        viewer_problem='정보 확인이 어렵다', one_takeaway='원문을 확인한다',
        demonstrable_action='가상 문서에서 근거를 강조', available_visuals_or_missing='화면 녹화 대기',
        risk='실제 결과 미검증', source_ids=list(sources), selection_reason='한 화면으로 시연 가능',
        criteria={k: dict(score=score, reason='fixture rationale') for k in EDITORIAL_WEIGHTS})


def source(sid, scope, kind, value, *, topic_id=None, observed='2026-11-11'):
    return dict(id=sid, source_url=f'https://example.org/{sid}', source_date='2026-11-11',
        accessed_at=NOW, observed_through=observed, window='최근 7일', region='KR',
        sample='공개 표본, 채널 규모 미상', evidence_scope=scope, metric_kind=kind,
        metric_value_or_null=value, topic_id=topic_id, observation='테스트 근거')


class TopicResearchTests(unittest.TestCase):
    def test_growth_points_require_recent_target_growth_not_mixed_units(self):
        sources = [
            source('large', 'general_shorts', 'view_gain', 90000000),
            source('search', 'search_interest', 'search_growth_pct', 4000),
            source('old', 'target_shorts', 'view_growth_pct', 400, topic_id='b', observed='2026-09-01'),
            source('fresh', 'target_shorts', 'view_gain', 12, topic_id='a'),
        ]
        candidates = [candidate('a', 2, ('fresh',)), candidate('b', 2, ('large', 'search', 'old')), candidate('c', 1)]
        decision = compare_topics(BRIEF, sources, candidates, researched_at=NOW)
        self.assertEqual(decision['recommended_id'], 'a')
        self.assertEqual(decision['alternative_ids'], ['b', 'c'])
        self.assertEqual([row['growth_points'] for row in decision['comparisons']], [10, 0, 0])
        self.assertEqual(decision['comparisons'][1]['evidence_status'], 'unverified_candidate')
        self.assertEqual(decision['evidence_snapshot'][2]['freshness'], 'historical')
        self.assertEqual(decision['decision_sha256'], digest({k: v for k, v in decision.items() if k != 'decision_sha256'}))
        sources[-1]['observed_through'] = None
        sources[-1]['metric_value_or_null'] = None
        rows = compare_topics(BRIEF, sources, candidates, researched_at=NOW)['comparisons']
        self.assertTrue(all(row['evidence_status'] == 'unverified_candidate' for row in rows))

    def test_malformed_or_wrong_scope_evidence_is_rejected(self):
        candidates = [candidate('a', 2, ('one',)), candidate('b', 1), candidate('c', 1)]
        valid = source('one', 'target_shorts', 'view_gain', 12, topic_id='a')
        for changes, error in [
            ({'source_url': ''}, 'invalid_text'),
            ({'source_url': 'file:///tmp/source'}, 'invalid_topic_source_url'),
            ({'metric_kind': 'search_growth_pct'}, 'topic_metric_scope_mismatch'),
            ({'region': 'US'}, 'topic_source_target_mismatch'),
            ({'topic_id': 'b'}, 'topic_source_target_mismatch'),
            ({'observed_through': '2026-12-01'}, 'future_topic_source_date'),
        ]:
            with self.subTest(changes=changes), self.assertRaisesRegex(CompanyError, error):
                compare_topics(BRIEF, [{**valid, **changes}], candidates, researched_at=NOW)

    def test_existing_project_versions_recommendation_and_hands_off_owner_choice(self):
        with TemporaryDirectory() as root:
            store = Store(root)
            project = store.create('기존 영상 회사의 대본 이전 주제 조사', opt_in=True)['id']
            bind_context(store, project, dict(answers={'audience': BRIEF['audience']}, constraints={},
                capabilities={'script_contract': SCRIPT_CONTRACT, 'topic_research_required': True}, experiences={'selected': []},
                permissions={'external_calls': False, 'cost_limit': 0}))
            seen = []

            def manager(phase, context):
                return json.dumps(dict(criteria=[dict(id=k, description=v) for k, v in CRITERIA.items()],
                    tasks=[dict(id=role, role=role, title=role, depends_on=deps, criteria_ids=list(CRITERIA),
                                instructions='인수 계약 확인')
                        for role, deps in [('writer', []), ('editor', ['writer'])]],
                    rationale='검토된 주제 인수', uncertainty='작성 전 인수 확인'))

            def handoff_only(phase, context):
                self.assertEqual(context['assignment']['role'], 'writer')
                seen.append(context['quality']['topic_handoff'])
                return json.dumps(dict(content='{}', evidence='인수 확인', uncertainty='대본 미작성'))

            company = VideoQualityCompany(store, MockManagerProvider('mock-handoff', manager),
                MockEmployeeProvider('mock-receipt', handoff_only))
            with self.assertRaisesRegex(CompanyError, 'owner_topic_review_required'):
                company.run(project)
            candidates = [candidate('a', 2), candidate('b', 1), candidate('c', 1)]
            first = company.review_topic_research(project, BRIEF, [], candidates, researched_at=NOW)
            company.review_topic_research(project, BRIEF, [], candidates, researched_at=NOW)
            self.assertEqual(len(store.load(project)['topic_research_history']), 1)
            with self.assertRaisesRegex(CompanyError, 'owner_topic_review_required'):
                company.run(project)
            self.assertEqual(store.load(project)['attempts'], [])
            company.record_topic_review(project, first['decision_sha256'], candidate_id=None, feedback='사례를 더 구체화')
            updated = deepcopy(candidates)
            updated[1]['demonstrable_action'] = '원본 문서의 날짜를 확대'
            second = company.review_topic_research(project, BRIEF, [], updated, researched_at=NOW)
            with self.assertRaisesRegex(CompanyError, 'stale_topic_decision'):
                company.record_topic_review(project, first['decision_sha256'], candidate_id='b', feedback='이 주제 선택')
            history = store.load(project)['topic_research_history']
            self.assertEqual(history[-1]['previous_decision_sha256'], first['decision_sha256'])
            self.assertEqual(history[0]['owner_review']['feedback'], '사례를 더 구체화')
            company.record_topic_review(project, second['decision_sha256'], candidate_id='b', feedback='대안 선택')
            result = company.run(project)
            self.assertEqual(result['status'], 'stopped')
            self.assertEqual(result['assignments'][0]['versions'], [])
            self.assertEqual(result['artifacts'], {})
            self.assertEqual(seen, [writer_topic_handoff(second, 'b')])
