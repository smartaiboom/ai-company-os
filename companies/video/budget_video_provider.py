"""Explicit new-project budget mode using the existing signed Gemini/video engine."""
from copy import deepcopy
import hmac

from autonomous_company import Store, require, exact, text, digest, now
from autonomous_free import FreeStore
from autonomous_gemini35 import Gemini35Store, MODEL
from quality_provider import QualityProviderStore, validate_inputs
from quality_workflow import VideoProviderQualityCompany
from script_quality import SCRIPT_CONTRACT
from project_budget_ledger import ProjectBudgetLedger
from video_budget import BudgetedVideoTransport
from video_mission_one import DATA_POLICY
from goal_dialogue_live import send_once


def _binding(project, key):
    require(isinstance(key,str) and 16<=len(key)<=4096 and key.isascii()
            and all(32<ord(c)<127 for c in key),'budget_provider_key_missing')
    return hmac.digest(key.encode(),('budget_video_v1:'+project).encode(),'sha256').hex()


class BudgetVideoStore(QualityProviderStore):
    mode = policy = 'budget_video_gemini35_v1'
    marker_name = '.budget-video-gemini35-v1'
    _limits = staticmethod(FreeStore._limits)

    def create(self, goal, *, inputs):
        validate_inputs(inputs)
        require(inputs['domain']=='video' and inputs['capabilities']==dict(script_contract=SCRIPT_CONTRACT), 'budget_video_script_path_only')
        p = Gemini35Store.create(self, goal, max_calls=None, internal_tool_review=False)
        p.update(quality_inputs=deepcopy(inputs), feedback_proposals=[])
        self.save(p)
        return p

    def prepare_budget(self, project, *, key, account_project):
        text(account_project, 200)
        p = self.load(project)
        body = self.prepare(project, valid_hours=1, confirm_free_account=True)
        body['budget_binding'] = dict(account_project=account_project, billing_disabled=True,
            credential_binding=_binding(project, key), data_policy=DATA_POLICY,
            cutroom=p['quality_inputs']['answers']['representative_project'])
        return body

    def _check_contract(self, p, body):
        proof = body.get('budget_binding', {})
        exact(proof, ('account_project','billing_disabled','credential_binding','data_policy','cutroom'))
        text(proof['account_project'],200)
        require(proof['billing_disabled'] is True and proof['data_policy']==DATA_POLICY
                and proof['cutroom']==p['quality_inputs']['answers']['representative_project']
                and isinstance(proof['credential_binding'],str) and len(proof['credential_binding'])==64,
                'budget_provider_scope_invalid')
        super()._check_contract(p, {k:v for k,v in body.items() if k!='budget_binding'})

    def budget_scope(self, p):
        grant = self.grant(p)
        proof = grant['body']['budget_binding']
        return dict(purpose=p['goal'], data_policy=proof['data_policy'], free_only=True,
            consent_id=grant['id'], consent_expires_at=grant['body']['expires_at'],
            services={'text':dict(provider='gemini', model=MODEL, account_project=proof['account_project'],
                                 operation='generateContent', unit='request_attempt')})


class BudgetVideoCompany(VideoProviderQualityCompany):
    store_type = BudgetVideoStore
    allowed_video_roles = ('writer','editor')

    def ledger(self):
        return ProjectBudgetLedger(self.store.root.parent/'project_budgets')

    def _quality_transport_allowed(self, p):
        proof = self.store.grant(p)['body']['budget_binding']
        cutroom = Store(self.store.root.parent).load(proof['cutroom'])
        require(cutroom['representative'].get('budget_job')==p['id'] and cutroom['goal']==p['goal'], 'budget_cutroom_binding_changed')
        require(hmac.compare_digest(proof['credential_binding'],_binding(p['id'],self.config.api_key)),
                'budget_provider_key_mismatch')
        return True

    def _request_json(self, p, **kwargs):
        scope = self.store.budget_scope(p)
        def verify(expected):
            self._check_provider_config()
            self._quality_transport_allowed(p)
            require(digest(self.store.budget_scope(p))==digest(expected),'budget_provider_scope_invalid')
            return True
        ledger = self.ledger()
        require(digest(ledger._load(p['id'])['scope'])==digest(scope),'budget_scope_changed_new_consent_required')
        if ledger.view(p['id'])['resources']['text']['remaining'] < 1:
            # Estimate the remaining calls from the AI's adopted tasks, not a product-wide cap.
            needed = (sum(2 if t['state'] in ('pending','revision_requested') else
                          1 if t['state']=='awaiting_ai_review' else 0 for t in p['assignments'])+1
                      if p['phase']=='work' else 1)
            ledger.request(p['id'],{'text':needed},reason='관리자 작업계획의 남은 실행·검토 예산',
                progress=f"{sum(t['state']=='accepted_by_ai_manager' for t in p['assignments'])}개 업무 수락, {p['phase']} 단계 보존",
                cost_impact='동일 무료 모델·동일 전송 동의; 실제 금액 미확인',
                failure_risk='추정량이며 수정·실패도 소모; 자동 재시도 없음',
                plan_hash=digest(p['plan'] or p['quality_inputs']))
        transport = BudgetedVideoTransport(ledger,p['id'],scope,verify)
        request = super()._request_json
        return transport.send(digest(self._operation_identity(kwargs['task_id'])), 'text',
                              lambda:request(p,**kwargs))

    def _open_transport(self, request, timeout):
        return send_once(request, timeout)

    def _run(self, project_id, *, expected_state_hash, resume=False):
        # Only an unsent budget stop can continue. Never reset a failed/reserved provider attempt.
        with self.store.lock(project_id):
            p = self.store.load(project_id)
            require(p['storage_hash']==expected_state_hash,'stale_start_or_resume')
            if p['status']=='stopped' and p.get('reason_code')=='budget_approval_required':
                require(resume is True and not p['active_operation'] and all(
                    a['status']=='completed' and a['role_result_status']=='validated' for a in p['real_ai']['attempts']),
                    'budget_continue_forbidden')
                require(self.ledger().view(p['id'])['resources']['text']['remaining']>0,'budget_approval_required')
                p['status']='running'
                p.pop('reason_code',None)
                p['events'].append(dict(at=now(),event='budget_explicit_continue'))
                self.store.save(p)
                expected_state_hash=p['storage_hash']
            else:
                require(p['status'] in ('ready','needs_user_review'), 'budget_continue_forbidden')
        return super()._run(project_id,expected_state_hash=expected_state_hash,resume=resume)
