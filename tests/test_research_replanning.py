from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
import json

from autonomous_company import CompanyError, Store, digest
from autonomous_gemini35 import ENDPOINT, MODEL
from research_replanning import failed_history, stores
from research_workflow import action, recovery_store, research_store, reviewed_handoff, status
from tests.test_web_research import Reply
from web_research import evidence


ENV = dict(TAVILY_RESEARCHER_FREE_ONLY='1', GEMINI35_AUTONOMOUS_FREE_ENABLED='1',
           GEMINI35_MODEL=MODEL, GEMINI35_ENDPOINT=ENDPOINT, TAVILY_API_KEY='fixture-tavily-key',
           GEMINI_API_KEY='fixture-gemini-key', GEMINI_PRODUCTION_PROJECT_API_KEY='fixture-gemini-key')


class ReplanningTests(TestCase):
    def test_failed_history_to_manager_and_separately_approved_investigation(self):
        for scenario in ('reinvestigate', 'alternative', 'hold', 'ask_owner', 'insufficient', 'key_changed',
                         'scope_changed', 'expired', 'revoked', 'provider_error', 'timeout', 'research_timeout'):
            with self.subTest(scenario=scenario), TemporaryDirectory() as tmp, ExitStack() as stack:
                store = Store(Path(tmp))
                project = store.create('Research target', opt_in=True)
                workflow = SimpleNamespace(store=store)
                base = dict(target='Check the release date', stage='research_planning')
                queries = {'game':'Public release dates'}
                source = research_store(store.root,project,base)
                recovery = recovery_store(source)
                page = evidence('https://example.org/releases','Release','Released Monday.',
                                'public_page','publisher')
                metric = evidence('https://other.example/media','API measurement','Published Tuesday.',
                                  'api_metric','platform')
                stack.enter_context(patch.dict('os.environ', ENV, clear=False))
                stack.enter_context(patch('research_workflow.context', return_value=(base,queries,None,None)))
                stack.enter_context(patch('research_workflow.cached_publishers', return_value=([page],[])))
                stack.enter_context(patch('research_workflow.cached_youtube', return_value=[metric]))
                stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('network disabled')))
                search = stack.enter_context(patch('research_workflow.tavily_search'))
                send = stack.enter_context(patch('goal_dialogue_live.send_once'))
                bad = dict(tool='web_search',option='unknown',claims=[],feasibility='')
                send.side_effect = [Reply(bad), Reply(bad)]

                def perform(name, **body):
                    return action(workflow, project['id'], name, body)

                def current():
                    return status(workflow, project)

                def deny(name, reason):
                    with self.assertRaisesRegex(CompanyError, reason):
                        perform(name)

                perform('research-approve', confirmed=True, review_hash=current()['review_hash'])
                deny('research-run', 'research_step_invalid')
                perform('research-recovery-approve', confirmed=True, review_hash=current()['recovery']['review_hash'])
                deny('research-recovery-run', 'research_step_invalid')
                previous = source.attempts(), recovery.attempts()
                links, failures, observations = failed_history(source)
                self.assertEqual(len(links), 2)
                self.assertEqual([failure['usage']['gemini']['reserved'] for failure in failures], [1,1])
                self.assertEqual(observations, [])
                offer = current()['replan']
                self.assertEqual(offer['status'], 'manager_available')
                self.assertEqual(offer['limits']['combined_gemini'], 6)
                self.assertIsNone(offer['decision'])
                deny('research-replan-run', 'owner_policy_required')
                deny('research-reinvestigate-run', 'owner_policy_required')
                deny('research-recovery-run','owner_policy_exhausted')
                intent = 'prefer_reinvestigation'
                perform('research-replan-approve', confirmed=True, owner_intent=intent,
                        review_hash=offer['review_hashes'][intent])
                self.assertEqual(send.call_count, 2)
                self.assertEqual(current()['replan']['status'], 'manager_active')
                terminal = scenario in ('alternative','hold','ask_owner')
                selected = [] if terminal else ['publisher_page','youtube_metrics']
                decision = dict(action=scenario if terminal else 'reinvestigate', tools=selected,
                                reason='Check archived sources', next_step='Compare dates',
                                success_criteria='Two independent sources for a claim')

                def respond_manager(request, timeout):
                    wire = json.loads(request.data)
                    sent = json.loads(wire['contents'][0]['parts'][0]['text'])
                    self.assertEqual(sent['owner_intent'], intent)
                    self.assertEqual(sent['failures'], failures)
                    approved = stores(source)[0].read('policy.json')
                    self.assertEqual(digest(wire), approved['proposal']['units'][0]['payload_sha256'])
                    deny('research-replan-run','project_busy')
                    if scenario == 'provider_error':
                        error = HTTPError(ENDPOINT,503,'fixture',{},BytesIO())
                        stack.callback(error.close)
                        raise error
                    if scenario == 'timeout':
                        raise TimeoutError()
                    return Reply(dict(decision=decision))

                send.side_effect = respond_manager
                if scenario in ('provider_error','timeout'):
                    deny('research-replan-run','transport_or_response_failed')
                    deny('research-replan-run','owner_policy_exhausted')
                    self.assertEqual(current()['replan']['status'],'manager_stopped')
                else:
                    perform('research-replan-run')
                    self.assertEqual(current()['replan']['decision'], decision)
                    if terminal:
                        self.assertEqual(current()['replan']['status'],'manager_decided')
                        deny('research-reinvestigate-run','replan_blocked')
                    else:
                        fresh = current()['replan']
                        self.assertEqual(fresh['status'],'research_available')
                        self.assertEqual(fresh['proposal']['max_search_credits'],0)
                        deny('research-reinvestigate-run','owner_policy_required')
                        perform('research-reinvestigate-approve',confirmed=True,review_hash=fresh['review_hash'])
                        self.assertEqual(current()['replan']['status'],'research_active')
                        expected = {
                            'key_changed':('owner_policy_key_changed',patch.dict('os.environ', {'TAVILY_API_KEY':'updated-fixture-key'})),
                            'scope_changed':('owner_policy_scope_changed',patch.dict(queries, {'game':'Different query'})),
                            'expired':('owner_policy_expired',patch('owner_operating_policy.now',return_value='2099-01-01T00:00:00+09:00')),
                        }
                        if scenario in expected:
                            reason, change = expected[scenario]
                            with change:
                                deny('research-reinvestigate-run',reason)
                        elif scenario == 'revoked':
                            perform('research-replan-revoke')
                            self.assertEqual(current()['replan']['status'],'revoked')
                            deny('research-reinvestigate-run','owner_policy_revoked')
                        elif scenario == 'research_timeout':
                            send.side_effect = TimeoutError()
                            deny('research-reinvestigate-run','transport_or_response_failed')
                            deny('research-reinvestigate-run','owner_policy_exhausted')
                            self.assertEqual(current()['replan']['status'],'research_stopped')
                            self.assertEqual(send.call_count,4)
                        else:
                            steps = iter(('publisher_page','youtube_metrics','finish'))
                            insufficient = scenario == 'insufficient'

                            def respond_research(request, timeout):
                                sent = json.loads(json.loads(request.data)['contents'][0]['parts'][0]['text'])
                                if sent['goal'] == 'Review video research':
                                    citations = sent['evidence']['claims'][0]['citations']
                                    self.assertEqual([ref['quote'] for ref in citations],
                                                     [] if insufficient else [page['excerpt'],metric['excerpt']])
                                    return Reply(dict(action='hold' if insufficient else 'use_with_limits',
                                                      note='Scope and rights checked for research handoff.'))
                                step = 'finish' if insufficient else next(steps)
                                if step == 'finish':
                                    return Reply(dict(tool='finish',option='',feasibility='Check further dates.',
                                        claims=[dict(statement='Dates need comparison',
                                                     assessment='unverified' if insufficient else 'conflicting',
                                                     citations=[] if insufficient else [page['id'],metric['id']])]))
                                self.assertNotIn('web_search',[item['name'] for item in sent['tools']])
                                return Reply(dict(tool=step,option='saved',claims=[],feasibility=''))

                            send.side_effect = respond_research
                            perform('research-reinvestigate-run')
                            self.assertEqual(current()['replan']['status'],'review')
                            self.assertEqual(bool(reviewed_handoff(source)),not insufficient)
                            deny('research-reinvestigate-run','owner_policy_exhausted')
                            self.assertEqual(send.call_count,5 if insufficient else 7)
                self.assertEqual((source.attempts(), recovery.attempts()), previous)
                search.assert_not_called()

    def test_common_contract_for_nonvideo_fixture(self):
        from task_replanning import ACTIONS, context, schema, validate

        prompt = context('Count stock','inventory',[dict(response_received=True)], [],
                         [dict(name='inventory')], 'fixture-v1', {'calls':1}, 'review_options')
        self.assertEqual(prompt['goal'],'Count stock')
        contract = schema(['inventory'])
        for action in ACTIONS:
            validate(dict(action=action,tools=['inventory'] if action=='reinvestigate' else [],
                          reason='Previous observation failed',next_step='Check stock',success_criteria='Count verified'),
                     contract)
        for tools in (['invented'], ['inventory','inventory'], []):
            with self.assertRaisesRegex(CompanyError,'replan_invalid'):
                validate(dict(action='reinvestigate', tools=tools, reason='Fixture',
                              next_step='Test', success_criteria='Count verified'),contract)
