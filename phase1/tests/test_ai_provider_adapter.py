"""Provider declarations and fake wire format must never unlock live models."""
import json
import os
from copy import deepcopy
from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch
from urllib.request import Request
import ai_provider_adapter as adapter
import ai_safety as safety
import app
import manager_decision as md
from tests.test_real_ai_safety_budget import RealAISafetyBudgetTests, Response
from tests import test_real_manager_decision as real_fixture

GUARDED_URLOPEN = safety.guarded_urlopen


class ProviderAdapterTests(RealAISafetyBudgetTests):
    def setUp(self):
        super().setUp()
        self.enterContext(patch('socket.socket',side_effect=AssertionError('network forbidden')))
        self.enterContext(patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')))

    def test_live_wire_shape_reservation_and_adapter_shared(self):
        p=self.saved(); persisted=[]
        wire=adapter.OpenRouterFreeAdapter()
        def transport(request,**kwargs):
            self.assertEqual(persisted[-1]['real_ai']['attempts'][-1]['status'],'reserved')
            self.assertEqual(request.full_url,'https://openrouter.ai/api/v1/chat/completions')
            self.assertEqual(request.get_method(),'POST')
            self.assertEqual(request.data,self.payload())
            self.assertEqual(request.get_header('Content-type'),'application/json')
            self.assertEqual(request.get_header('Authorization'),'Bearer FICTIONAL')
            self.assertLessEqual(kwargs['timeout'],90)
            return Response()
        with patch('ai_provider_adapter.require_live_adapter',wraps=adapter.require_live_adapter) as select:
            with safety.request_scope(lambda value:persisted.append(deepcopy(value))):
                self.send(p,transport,api_key='FICTIONAL')
            self.assertEqual(select.call_count,1)
        self.assertEqual(p['real_ai']['attempts'][-1]['status'],'completed')
        self.assertTrue(p['real_ai']['attempts'][-1]['reserved_at'].endswith('+09:00'))
        self.assertEqual(len(persisted),2)
        self.assertEqual(wire.spec.model,'openrouter/free')

    def test_future_spec_and_mock_registry_cannot_enable_live_calls(self):
        future=adapter.ProviderSpec('future','paid/model','other_api','https://example.invalid/v1','bearer',8192,'paid',enabled=True)
        registry={'future':future,'openrouter_free':future}
        original=self.saved()
        for model,base,key,body in (
            ('paid/model',safety.BASE_URL,'FICTIONAL',self.payload()),
            ('unknown',safety.BASE_URL,'FICTIONAL',self.payload()),
            ('',safety.BASE_URL,'FICTIONAL',self.payload()),
            (safety.MODEL,'http://openrouter.ai/api/v1','FICTIONAL',self.payload()),
            (safety.MODEL,'https://example.invalid/v1','FICTIONAL',self.payload()),
            (safety.MODEL,safety.BASE_URL,'',self.payload()),
            (safety.MODEL,safety.BASE_URL,None,self.payload()),
            (safety.MODEL,safety.BASE_URL,'FICTIONAL',b'{'),
            (safety.MODEL,safety.BASE_URL,'FICTIONAL',json.dumps({'model':'paid/model','max_tokens':32}).encode()),
            (safety.MODEL,safety.BASE_URL,'FICTIONAL',json.dumps({'model':safety.MODEL,'max_tokens':8192}).encode()),
        ):
            p=deepcopy(original); sender=Mock(); persist=Mock()
            with safety.request_scope(persist), self.assertRaises(ValueError):
                self.send(p,sender,model=model,base_url=base,api_key=key,body=body)
            sender.assert_not_called();persist.assert_not_called();self.assertEqual(p,original)
        with self.assertRaises(ValueError):adapter.require_live_adapter(model=future.model,base_url=future.base_url,api_key='FICTIONAL',provider_id='future')
        self.assertEqual(registry['future'],future)
        with self.assertRaises(FrozenInstanceError):future.enabled=False
        self.assertEqual(adapter.LIVE_PROVIDER_IDS,('openrouter_free',))

    def test_metadata_is_bounded_and_never_retains_unknown_text(self):
        for reason,expected in [('stop','stop'),('length','length'),('content_filter','content_filter'),('error','error'),('PRIVATE','unknown'),(None,'unknown'),([], 'unknown')]:
            r=adapter.response_metadata({'choices':[{'finish_reason':reason,'message':{'content':'PRIVATE'*50000},'private':'PRIVATE'}]})
            self.assertEqual(r.finish.value,expected)
            self.assertLessEqual(r.content_chars,262144)
            self.assertNotIn('PRIVATE',repr(r))
        self.assertFalse(adapter.response_metadata({}).structure_valid)
        self.assertEqual(adapter.classify_transport_error(TimeoutError('PRIVATE')).value,'timeout')
        self.assertEqual(adapter.classify_transport_error(OSError('PRIVATE')).value,'transport')

    def test_offline_substitution_only_no_live_registry(self):
        class OfflineAdapter:
            spec=adapter.ProviderSpec('offline','fictional','mock','https://example.invalid','none',32,'none')
            def build_request(self,body,api_key):return Request('https://example.invalid',data=body,method='POST')
            def response_metadata(self,response):return adapter.response_metadata(response)
        def inspect_wire(selected):
            self.assertEqual(selected.build_request(b'{}','FICTIONAL').data,b'{}')
            return selected.spec.identifier, selected.response_metadata({'choices':[{'finish_reason':'stop','message':{'content':'가상'}}]})
        name,meta=inspect_wire(OfflineAdapter())
        self.assertEqual(name,'offline');self.assertEqual(meta.finish,adapter.FinishClass.STOP)
        name,meta=inspect_wire(adapter.OpenRouterFreeAdapter())
        self.assertEqual(name,'openrouter_free')
        with self.assertRaises(ValueError):adapter.require_live_adapter(model='fictional',base_url='https://example.invalid',api_key='FICTIONAL',provider_id='offline')

    def test_transport_ignores_proxy_environment_and_disallows_redirects(self):
        opener=Mock()
        with patch.dict(os.environ, {'HTTPS_PROXY':'https://example.invalid:8080'}), patch('ai_safety.build_opener',return_value=opener) as build:
            GUARDED_URLOPEN(Request(safety.BASE_URL),timeout=10)
        proxy,redirect=build.call_args.args
        self.assertEqual(proxy.proxies,{})
        self.assertIsInstance(redirect,safety.NoRedirect)
        opener.open.assert_called_once()


class SharedConsumerAdapterTests(real_fixture.RealManagerDecisionTests):
    def test_manager_and_employee_select_same_free_only_adapter(self):
        self.prepare()
        before = deepcopy(self.saved()['real_ai']['attempts'])
        with patch('ai_provider_adapter.require_live_adapter', wraps=adapter.require_live_adapter) as select:
            with patch('manager_decision.urlopen', side_effect=self.transport()):
                proposal = self.run_real()
            app.respond_manager_decision(self.p['id'], proposal['id'], md.digest(proposal), 'approve')
            with app.project_mutation_lock(self.p['id']), safety.request_scope(app.save_project), patch('execution_engine.urlopen', return_value=Response()):
                app.execute_project_task(self.p['id'], 'TASK-002')
            self.assertEqual(select.call_count, 2)
            for call in select.call_args_list:
                self.assertEqual(call.kwargs['model'], 'openrouter/free')
                self.assertEqual(call.kwargs['base_url'], safety.BASE_URL)
        self.assertEqual(self.saved()['real_ai']['attempts'][:len(before)], before)
        self.assertEqual(len(self.saved()['real_ai']['attempts']), len(before)+2)

    def test_manager_still_rejects_every_nonstop_class_without_correction(self):
        self.prepare()
        context=md.decision_input(self.saved(),'TASK-001')
        value=self.model_decision(context)
        for reason in ('length','content_filter','error','PRIVATE',None,[]):
            with self.subTest(reason=reason),self.assertRaises(md.DecisionDiagnosticError) as error:
                md.validate_provider_response({'choices':[{'finish_reason':reason,'message':{'content':json.dumps(value,ensure_ascii=False)}}]},context)
            self.assertEqual((error.exception.stage,error.exception.code),('provider_response','finish_reason'))
            self.assertNotIn('PRIVATE',str(error.exception))
