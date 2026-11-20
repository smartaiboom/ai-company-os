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
                         'scope_changed', 'expired', 'revoked', 'provider_error', 'timeout', 'research_timeout',
                         'supervise', 'supervise_early', 'supervise_empty', 'supervise_stall', 'supervise_timeout',
                         'supervise_signature', 'supervise_key', 'supervise_expired', 'supervise_revoked',
                         'supervise_official', 'supervise_search_official', 'supervise_batch', 'supervise_batch_fail'):
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
                inputs = stack.enter_context(patch('research_workflow.context', return_value=(base,queries,None,None)))
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
                            insufficient = scenario == 'insufficient' or scenario.startswith('supervise')

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
                            if scenario.startswith('supervise'):
                                fetch = None
                                if scenario == 'supervise_early':
                                    stack.enter_context(patch('research_workflow.cached_publishers', return_value=([], [])))
                                    stack.enter_context(patch('research_workflow.cached_youtube', return_value=[]))
                                if scenario.endswith('official') or scenario.startswith('supervise_batch'):
                                    import publisher_discovery as publisher
                                    from owner_operating_policy import OwnerOperatingPolicy
                                    saved = OwnerOperatingPolicy(store.root/'approved-publisher', {'scope':'fixture'})
                                    entries = [dict(id='robots-pages',kind='robots',url='https://www.klei.com/robots.txt'),
                                               dict(id='rights',kind='page',url='https://www.klei.com/creation-guidelines')]
                                    scope = {**saved.proposal([publisher.get_unit(entry) for entry in entries]),
                                             'profile':'klei','profile_rules':publisher.PROFILES['klei'],'entries':entries}
                                    saved.approve(scope,digest(scope),'fixture')
                                    inputs.return_value = (base,queries,object(),{})
                                    stack.enter_context(patch('research_workflow.cached_commons', return_value=[]))
                                    stack.enter_context(patch('publisher_discovery.store_for',return_value=saved))
                                    fetched = dict(status=200,text='<title>Rights policy</title><p>Released for editorial use.</p>')
                                    if scenario == 'supervise_batch_fail':
                                        from decision_recovery import ProviderFailure
                                        fetched = ProviderFailure('publisher_http_failure')
                                    fetch = stack.enter_context(patch('publisher_discovery.fetch_public',side_effect=[
                                        dict(status=200,text='User-agent: *\nDisallow: /private/'), fetched]))
                                self.exercise_supervision(scenario, source, current, perform, deny, send, search,
                                                          page, metric, fetch)
                self.assertEqual((source.attempts(), recovery.attempts()), previous)
                self.assertEqual(search.call_count, int(scenario in ('supervise_empty','supervise_search_official','supervise_batch','supervise_batch_fail')))

    def exercise_supervision(self, scenario, source, current, perform, deny, send, search, page, metric, fetch=None):
        from research_supervision import supervision_store

        held = stores(source)[1]
        previous = held.attempts(), held.read('manager-review.json')
        offer = current()['supervision']
        self.assertEqual(offer['proposal']['historical_usage']['gemini'],5)
        self.assertEqual(offer['proposal']['limits']['gemini'],5)
        self.assertEqual(offer['proposal']['limits']['official_gets'],2 if fetch else 0)
        if fetch:
            fetch.assert_not_called()
        deny('research-supervision-run','owner_policy_required')
        perform('research-supervision-approve',confirmed=True,review_hash=offer['review_hash'])
        self.assertEqual(send.call_count,5)
        self.assertEqual(current()['supervision']['status'],'active')
        if scenario == 'supervise_signature':
            path = supervision_store(source).root/'policy.json'
            document = json.loads(path.read_text())
            Store.atomic(path, {**document, 'signature':'0'*64})
            deny('research-supervision-run','owner_policy_signature')
            self.assertEqual(send.call_count,5)
            return
        if scenario == 'supervise_key':
            with patch.dict('os.environ', {'TAVILY_API_KEY':'changed-fixture-key'}):
                deny('research-supervision-run','owner_policy_key_changed')
            self.assertEqual(send.call_count,5)
            return
        if scenario == 'supervise_expired':
            with patch('owner_operating_policy.now', return_value='2099-01-01T00:00:00+09:00'):
                deny('research-supervision-run','owner_policy_expired')
            self.assertEqual(send.call_count,5)
            return
        if scenario == 'supervise_revoked':
            perform('research-supervision-revoke')
            deny('research-supervision-run','owner_policy_revoked')
            self.assertEqual(send.call_count,5)
            return
        staff = []
        reviews = []
        search.return_value = [evidence('https://www.klei.com/creation-guidelines','Policy','A search lead.',
                                       'search_lead')] if scenario in ('supervise_search_official','supervise_batch','supervise_batch_fail') else []
        report = dict(tool='finish', option='', claims=[dict(statement='Dates remain uncertain',
                      assessment='unverified', citations=[])], feasibility='Check further dates.')

        def supported(prompt):
            official = next((row for row in prompt['evidence_catalog'].values() if row['origin']=='Klei Entertainment'),page)
            return {**report,'claims':[dict(statement='A release and listing date are documented.',
                         assessment='supported', citations=[official['id'],metric['id']])]}

        def respond(request, timeout):
            wire = json.loads(request.data)
            prompt = json.loads(wire['contents'][0]['parts'][0]['text'])
            self.assertEqual(prompt['assignment']['manager_success_criteria'], 'Two independent sources for a claim')
            deny('research-supervision-run','project_busy')
            if prompt['goal']=='Review achievement of the assigned goal':
                reviews.append(prompt)
                accepted = (scenario in ('supervise','supervise_batch','supervise_search_official')
                            or scenario == 'supervise_official' and len(reviews) == 2)
                revise = scenario in ('supervise_stall','supervise_official') and len(reviews)==1
                action = 'accept' if accepted else 'revise' if revise else 'hold'
                permitted = wire['generationConfig']['responseJsonSchema']['properties']['decision']['properties']['action']['enum']
                self.assertEqual('accept' in permitted,accepted)
                if len(reviews) == 2 or scenario=='supervise_search_official':
                    self.assertNotIn('revise',permitted)
                if accepted:
                    sources = (page,metric)
                    if fetch:
                        sources = (next(row for row in prompt['evidence_catalog'].values()
                                        if row['origin']=='Klei Entertainment'),metric)
                        self.assertIn('Released for editorial use.',sources[0]['excerpt'])
                    self.assertEqual(prompt['staff_report']['claims'][0]['citations'],[
                        dict(source=row['id'], quote=row['excerpt']) for row in sources])
                return Reply(dict(decision=dict(action=action,rationale='Checked observation scope.',
                    feedback='Compare both sources directly.',confirmation='Check the dates.',
                    checks=[dict(criterion_id='objective',status='met' if accepted else 'unmet',
                                 source='model_claim',evidence='Based on stored observations.')])))

            staff.append(prompt)
            if len(staff) == 1:
                operation = offer['proposal']['units'][0]
                self.assertEqual(digest(wire), operation['payload_sha256'])
                if scenario == 'supervise_timeout':
                    raise TimeoutError()
                if scenario == 'supervise_early':
                    self.assertEqual(prompt['evidence_catalog'], {})
                    return Reply(report)
                self.assertIn(metric['id'],prompt['evidence_catalog'])
                self.assertNotIn('youtube_metrics',[tool['name'] for tool in prompt['tools']])
                if scenario in ('supervise_empty','supervise_search_official'):
                    return Reply(dict(tool='web_search',option='game',claims=[],feasibility=''))
                if scenario.startswith('supervise_batch'):
                    return Reply(dict(tool='batch',option='',claims=[],feasibility='',selections=[
                        dict(tool='web_search',option='game',reason='Collect independent leads.'),
                        dict(tool='official-page-rights',option='approved',reason='Read the already approved policy.')]))
                if scenario == 'supervise_official':
                    return Reply(dict(tool='official-page-rights',option='approved',claims=[],feasibility=''))
                return Reply(supported(prompt) if scenario == 'supervise' else report)
            if scenario == 'supervise_empty':
                return Reply({**report,'tool':'hold','unavailable':[
                    dict(tool=tool['name'],reason='Cannot establish the requested date.')
                    for tool in prompt['tools']]})
            if scenario == 'supervise_stall':
                self.assertTrue(prompt['report_only'])
                return Reply(report)
            if scenario == 'supervise_batch':
                self.assertTrue(any(row['scope']=='search_lead' for row in prompt['evidence_catalog'].values()))
                return Reply(supported(prompt))
            if scenario == 'supervise_search_official':
                if len(staff)==2:
                    return Reply(dict(tool='official-page-rights',option='approved',claims=[],feasibility=''))
                self.assertTrue(prompt['report_only'])
                self.assertEqual(prompt['tools'],[])
                return Reply(supported(prompt))
            if not prompt['report_only']:
                return Reply(report)
            self.assertEqual(prompt['tools'],[])
            self.assertEqual(prompt['manager_revision']['action'],'revise')
            return Reply(supported(prompt))

        send.side_effect = respond
        failures = dict(supervise_early='research_step_invalid',supervise_timeout='transport_or_response_failed',
                        supervise_batch_fail='publisher_http_failure')
        if scenario in failures:
            deny('research-supervision-run',failures[scenario])
            stopped = current()['supervision']
            self.assertEqual(stopped['status'],'stopped')
            self.assertEqual(send.call_count,6)
            if scenario=='supervise_batch_fail':
                self.assertEqual([item['state'] for item in stopped['choices']],['observed','failed'])
                self.assertIn('general-web',supervision_store(source).attempts())
        else:
            perform('research-supervision-run')
            current_state = current()['supervision']
            achieved = scenario in ('supervise','supervise_official','supervise_batch','supervise_search_official')
            if fetch:
                self.assertEqual(fetch.call_count,2)
                self.assertEqual(current_state['remaining']['official_gets'],0)
                self.assertTrue(any(item['requests'] for item in current_state['choices']))
            self.assertEqual(current_state['status'],'achieved' if achieved else 'incomplete')
            self.assertEqual(bool(reviewed_handoff(source)),achieved)
            if scenario == 'supervise_empty':
                self.assertEqual(current_state['choices'][0]['state'],'empty')
                self.assertEqual(current_state['remaining']['tavily'],0)
            if scenario == 'supervise_stall':
                self.assertFalse(reviews[-1]['progress_since_revision'])
            self.assertEqual(len(reviews),2 if scenario in ('supervise_official','supervise_stall') else 1)
            if scenario=='supervise_batch':
                self.assertEqual(send.call_count,8)
            if scenario=='supervise_search_official':
                self.assertEqual(send.call_count,9)
        deny('research-supervision-run','owner_policy_exhausted')
        self.assertEqual((held.attempts(), held.read('manager-review.json')),previous)

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

    def test_supervision_contract_nonvideo_and_exhausted_tools(self):
        from staff_supervision import review_schema, run, validate_review
        from role_json_schema import matches
        from web_research import step_context, step_schema, validate_supervised_step

        inventory = [dict(id='stock', description='Count independently verified inventory items.')]
        events = []

        def staff(index, previous):
            events.append(('staff', index, previous and previous['action']))
            return index == 0

        def supervisor(index, previous):
            events.append(('manager', index, previous and previous['action']))
            return dict(action='revise' if index == 0 else 'hold')

        self.assertEqual(run(staff, supervisor)['action'], 'hold')
        self.assertEqual(events, [('staff',0,None),('manager',0,None),('staff',2,'revise'),('manager',1,'revise')])
        context, runtime = step_context({}, [], False)
        hold = dict(tool='hold', option='', feasibility='No source could confirm inventory.',
                    claims=[dict(statement='Count unknown.', assessment='unverified', citations=[])], unavailable=[])
        self.assertTrue(matches(hold, step_schema(context, supervised=True)))
        validate_supervised_step(hold, *runtime)
        value = dict(action='hold', rationale='No inventory evidence.', feedback='Obtain a new count.',
                     confirmation='Compare two recorded counts.',
                     checks=[dict(criterion_id='stock', status='unknown', evidence='No source', source='model_claim')])
        contract = review_schema(inventory, can_accept=False, can_revise=False)
        self.assertTrue(matches(value, contract))
        self.assertFalse(matches({**value, 'action':'revise'}, contract))
        validate_review(value, inventory)

    def test_preserved_sources_and_batch_dependency_contract(self):
        from web_research import Tool, preserved_observations, step_context, validate_supervised_step

        fresh = evidence('https://archive.example/fresh','Inventory','Earlier measurement',
                         'api_metric','archive','2026-11-19T09:00:00+09:00')
        stale = evidence('https://archive.example/stale','Old','Old count','api_metric',
                         'archive','2026-10-01T09:00:00+09:00')
        lead = evidence('https://archive.example/lead','Lead','Needs confirmation','search_lead',
                        observed_at='2026-11-19T09:00:00+09:00')
        local = Tool('inventory','Reusable archive',{'saved':'records'},
                     lambda *_:self.fail('Preserved evidence executes no tool'),preserved=(fresh,stale,lead))
        archived, notes = preserved_observations({'inventory':local},at='2026-11-20T09:00:00+09:00')
        self.assertEqual(archived[0]['sources'],[fresh])
        self.assertEqual(archived[0]['status'],'preserved')
        self.assertEqual({key:notes[0][key] for key in ('preserved','stale','excluded')},
                         dict(preserved=1,stale=1,excluded=1))
        a = Tool('official-a','Page A',{'approved':'a'},None,requests=({'id':'robots'},))
        b = Tool('official-b','Page B',{'approved':'b'},None,requests=({'id':'robots'},))
        _, runtime = step_context({a.name:a,b.name:b}, archived, False)
        batch = dict(tool='batch',option='',claims=[],feasibility='',selections=[
            dict(tool=a.name,option='approved',reason='Explicit path A.'),
            dict(tool=b.name,option='approved',reason='Explicit path B.')])
        with self.assertRaisesRegex(CompanyError,'research_step_invalid') as error:
            validate_supervised_step(batch,*runtime)
        self.assertEqual(error.exception.rule,'batch_dependency')
        with self.assertRaisesRegex(CompanyError,'research_step_invalid'):
            validate_supervised_step({**batch,'selections':batch['selections']+[batch['selections'][0]]},*runtime)

    def test_supervised_gemini_wire_schema_is_simple_but_local_rules_stay_strict(self):
        from research_supervision import worker_for
        from web_research import Tool

        store = SimpleNamespace(root=Path('/tmp/research-shape-fixture'))
        tool = Tool('catalog','Read facts',{'approved':'public record'},lambda _: [])
        worker = worker_for(store, {}, {tool.name:tool}, [], 0, None, {})
        wire = worker._payload(None)['generationConfig']
        encoded = json.dumps(wire['responseJsonSchema'])
        self.assertEqual(wire['responseMimeType'],'application/json')
        self.assertNotIn('anyOf',encoded)
        self.assertNotIn('enum',encoded)
        valid = dict(decision=dict(tool='catalog',option='approved',claims=[],feasibility=''))
        forged = dict(decision={**valid['decision'],'option':'unapproved'})
        provider_decision = wire['responseJsonSchema']['properties']['decision']
        self.assertEqual(provider_decision['properties']['option'], {'type':'string'})
        self.assertNotIn('selections',provider_decision['required'])
        worker.validate_response(valid)
        self.assertEqual(worker.contract['input']['hold_unavailable_tools'], ['catalog'])
        hold = dict(decision=dict(tool='hold',option='',feasibility='Count needs confirmation.',
                    claims=[dict(statement='Inventory unconfirmed.',assessment='unverified',citations=[])],
                    unavailable=[dict(tool='catalog',reason='Catalog omits this item.')]))
        worker.validate_response(hold)
        with self.assertRaisesRegex(CompanyError,'research_step_invalid') as rejected:
            worker.validate_response(dict(decision={**hold['decision'],'unavailable':[]}))
        self.assertEqual(rejected.exception.rule,'missing_hold_reason')
        with self.assertRaisesRegex(CompanyError,'research_step_invalid'):
            worker.validate_response(forged)

        final = worker_for(store, {}, {tool.name:tool}, [], 2, None, {})
        with self.assertRaisesRegex(CompanyError,'research_step_invalid'):
            final.validate_response(valid)
