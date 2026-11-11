"""Opt-in durable budgets for new projects. No implicit budget or transport consent.

Legacy project_budget and mission grants are deliberately not migrated.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
import hmac

from autonomous_company import Store, require, exact, text, parse, fcntl
from autonomous_live import LiveStore
from project_budget import digest, now


class ProjectBudgetLedger:
    _sign = LiveStore._sign
    marker_name = '.project-budget-ledger-v1'

    def __init__(self, root):
        from pathlib import Path
        self.root = Path(root).resolve()

    def _path(self, project):
        return Store(self.root).path(project)

    def _marker(self):
        p = self.root/self.marker_name
        require(p.is_file() and not p.is_symlink() and p.read_text() == '1', 'invalid_budget_store')

    @contextmanager
    def _lock(self, project):
        self._marker()
        require(fcntl is not None, 'cross_process_lock_unavailable')
        path = self._path(project).with_suffix('.lock')
        require(not path.is_symlink(), 'invalid_budget_path')
        with path.open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                require(False, 'budget_busy')
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    @staticmethod
    def _scope(scope):
        exact(scope, ('purpose', 'data_policy', 'free_only', 'consent_id', 'consent_expires_at', 'services'))
        require(scope['free_only'] is True, 'paid_budget_path_forbidden')
        for key in ('purpose', 'data_policy', 'consent_id'):
            text(scope[key], 2000)
        require(isinstance(scope['services'], dict) and bool(scope['services']), 'invalid_budget_services')
        for resource, spec in scope['services'].items():
            text(resource, 100)
            exact(spec, ('provider', 'model', 'account_project', 'operation', 'unit'))
            for value in spec.values():
                text(value, 300)
            # Request attempts are not tokens, quota units or currency.
            require(spec['unit'] == 'request_attempt', 'unsupported_budget_unit')
        ProjectBudgetLedger._future(scope['consent_expires_at'])

    @staticmethod
    def _future(value):
        try:
            expiry = datetime.fromisoformat(value)
            valid = expiry.utcoffset() == timedelta(hours=9) and expiry > datetime.fromisoformat(now())
        except (ValueError, TypeError):
            valid = False
        require(valid, 'budget_or_consent_expired')

    def _load(self, project):
        self._marker()
        path = self._path(project)
        require(path.stat().st_size <= 4194304, 'budget_state_too_large')
        record = parse(path.read_text())
        exact(record, ('body', 'signature'))
        require(hmac.compare_digest(str(record['signature']), self._sign(record['body'])), 'budget_ledger_tampered')
        state = record['body']
        require(state['project'] == project and state['version'] == 1, 'budget_project_mismatch')
        return state

    def _save(self, state):
        state['updated_at'] = now()
        Store.atomic(self._path(state['project']), dict(body=state, signature=self._sign(state, create=True)))

    def create(self, project, *, scope):
        self._scope(scope)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        marker = self.root/self.marker_name
        if not marker.exists():
            require(not any(self.root.iterdir()), 'budget_store_not_isolated')
            with marker.open('x') as handle:
                handle.write('1')
        with self._lock(project):
            require(not self._path(project).exists(), 'budget_already_exists')
            self._save(dict(version=1, project=project, scope=deepcopy(scope), requests=[], approvals=[], attempts=[]))

    @staticmethod
    def _summary(state):
        result = {}
        for resource, spec in state['scope']['services'].items():
            approved = sum(e['amounts'].get(resource, 0) for e in state['approvals'])
            attempts = [a for a in state['attempts'] if a['resource'] == resource]
            result[resource] = dict(unit=spec['unit'], approved=approved, consumed=len(attempts),
                remaining=approved-len(attempts), unresolved=sum(a['status'] in ('reserved','uncertain') for a in attempts))
        return dict(project=state['project'], resources=result, requests=deepcopy(state['requests']),
                    cost=dict(status='unknown', amount=None, currency=None))

    def view(self, project):
        return self._summary(self._load(project))

    @staticmethod
    def _amounts(state, amounts):
        require(isinstance(amounts, dict) and bool(amounts) and set(amounts) <= set(state['scope']['services'])
                and all(type(n) is int and n > 0 for n in amounts.values()), 'invalid_budget_amounts')

    def _request(self, state, amounts, *, reason, progress, cost_impact, failure_risk, plan_hash, valid_hours, automatic=False):
        self._amounts(state, amounts)
        for value in (reason, progress, cost_impact, failure_risk, plan_hash):
            text(value, 2000)
        require(type(valid_hours) is int and 1 <= valid_hours <= 168, 'invalid_budget_validity')
        self._scope(state['scope'])
        pending = next((r for r in state['requests'] if r['status']=='pending'), None)
        if pending:
            try:
                self._future(pending['expires_at'])
            except ValueError:
                pending['status'] = 'expired'
            else:
                return deepcopy(pending)
        if automatic:
            rejected = next((r for r in reversed(state['requests'])
                if r['status']=='rejected' and r['plan_hash']==plan_hash), None)
            if rejected:
                return deepcopy(rejected)
        import uuid
        request = dict(id=uuid.uuid4().hex, status='pending', amounts=deepcopy(amounts), reason=reason,
            progress=progress, cost_impact=cost_impact, failure_risk=failure_risk, plan_hash=plan_hash,
            approval_binding=digest(dict(scope=state['scope'], approvals=state['approvals'])),
            created_at=now(), expires_at=(datetime.fromisoformat(now())+timedelta(hours=valid_hours)).isoformat())
        state['requests'].append(request)
        self._save(state)
        return deepcopy(request)

    def request(self, project, amounts, *, reason, progress, cost_impact, failure_risk, plan_hash, valid_hours=24):
        """Manager estimate only. The engine never treats this as granted capacity."""
        with self._lock(project):
            return self._request(self._load(project), amounts, reason=reason, progress=progress,
                cost_impact=cost_impact, failure_risk=failure_risk, plan_hash=plan_hash, valid_hours=valid_hours)

    def decide(self, project, request_id, *, review_hash, action, owner_confirmed=False):
        require(owner_confirmed is True and action in ('approve', 'reject'), 'explicit_budget_decision_required')
        with self._lock(project):
            state = self._load(project)
            self._scope(state['scope'])
            request = next((r for r in state['requests'] if r['id']==request_id), None)
            require(request is not None and request['status']=='pending', 'budget_decision_replay')
            require(digest(request)==review_hash and request['approval_binding']==digest(
                dict(scope=state['scope'], approvals=state['approvals'])), 'budget_review_changed')
            self._future(request['expires_at'])
            if action == 'approve':
                state['approvals'].append(dict(request_id=request_id, amounts=deepcopy(request['amounts']),
                                               review_hash=review_hash, at=now()))
            request.update(status='approved' if action=='approve' else 'rejected', decided_at=now())
            self._save(state)

    def execute(self, project, *, operation_id, resource, expected_scope, verify_consent, send):
        """The only transport boundary: durable reservation first, no retry after any outcome.

        verify_consent MUST check the existing provider grant, revocation, account/key binding
        and data scope. A budget approval never substitutes for that separate boundary.
        """
        text(operation_id, 200)
        with self._lock(project):
            state = self._load(project)
            self._scope(state['scope'])
            require(digest(expected_scope)==digest(state['scope']), 'budget_scope_changed_new_consent_required')
            require(resource in state['scope']['services'], 'unknown_budget_resource')
            require(not any(a['operation_id']==operation_id for a in state['attempts']), 'budget_operation_replay')
            require(not any(a['status'] in ('reserved','uncertain') for a in state['attempts']), 'budget_uncertain_operation')
            require(verify_consent(deepcopy(state['scope'])) is True, 'budget_transport_consent_required')
            remaining = self._summary(state)['resources'][resource]['remaining']
            if remaining < 1:
                self._request(state, {resource:1}, reason='다음 작업의 승인 잔여량 부족',
                    progress='기존 시도와 결과를 보존하고 다음 전송 전에 대기',
                    cost_impact='동일 무료 범위만; 실제 비용 미확인', failure_risk='실패·불명도 소모, 자동 재시도 없음',
                    plan_hash=digest(dict(operation_id=operation_id, resource=resource)), valid_hours=24, automatic=True)
                require(False, 'budget_approval_required')
            attempt = dict(operation_id=operation_id, resource=resource, status='reserved', reserved_at=now())
            state['attempts'].append(attempt)
            self._save(state)
            try:
                # Revocation may have changed while reservation reached durable storage.
                require(verify_consent(deepcopy(state['scope'])) is True, 'budget_transport_consent_required')
                result = send()
            except Exception as exc:
                attempt.update(status='uncertain' if isinstance(exc,(TimeoutError,ConnectionError)) else 'failed', finished_at=now())
                self._save(state)
                raise
            attempt.update(status='completed', finished_at=now())
            self._save(state)
            return result
