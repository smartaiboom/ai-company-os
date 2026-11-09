"""Explicit one-new-request decisions. No UI, automatic consent, or transport.

The caller must authenticate a CURRENT user decision and hold the application's
project mutation lock. A trusted local authority directory is required; HMAC
protects accidental/unauthorized record edits, not an owner who controls both
records and signing keys. Never copy/reset that authority to resume a replica.
An observer must track the prior server's real request threads; lack of evidence
must return False, including after a restart. Process exit is not provider proof.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from pathlib import Path
import fcntl
import hashlib
import hmac
import json
import os

_active = ContextVar('uncertain_reservation_decision', default=None)
SCOPE = 'goal_task_inputs_predecessors_feedback'


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _reject():
    raise ValueError('미확정 예약 판단 또는 종료 관측이 없거나 유효하지 않습니다.')


class ResolutionLedger:
    """One authority per canonical project; locks survive process restarts."""
    def __init__(self, project_path):
        self.project_path = Path(project_path).resolve()
        self.root = self.project_path.parent / '.uncertain-reservations' / self.project_path.name
        self.record_path = self.root / 'decision.json'
        self.used_path = self.root / 'consumed.json'
        self.key_path = self.root / 'signing.key'

    @contextmanager
    def _lock(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / 'authority.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _reject()
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _write_new(self, path, value):
        # Exclusive creation: a partial/crashed write remains invalid and blocks.
        with path.open('xb') as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _binding(self, project):
        try:
            if json.loads(self.project_path.read_text()) != project:
                _reject()
            attempts = project['real_ai']['attempts']
            pending = [a for a in attempts if a['status'] == 'reserved']
            if len(pending) != 1:
                _reject()
            goal = project.get('manager_goal') or project['goal']
            return {'project_id': project['id'], 'project_path': str(self.project_path),
                    'authority_path': str(self.root), 'goal_hash': hashlib.sha256(str(goal).encode()).hexdigest(),
                    'reservation_id': pending[0]['id'],
                    'reservation_hash': fingerprint(pending[0]),
                    'project_hash': fingerprint(project)}
        except (OSError, KeyError, TypeError, ValueError):
            _reject()

    def record_user_decision(self, project, decision, observer):
        """Only call after actual explicit user input; no inference from task files.

        Observer.requests_finished() must inspect a stopped prior server and all
        its request workers. The observer itself is trusted, never a JSON flag.
        """
        with self._lock():
            binding = self._binding(project)
            try:
                timestamp = datetime.fromisoformat(decision['decided_at'])
                valid = (set(decision) == {'project_id', 'goal_hash', 'reservation_id',
                                         'reservation_hash', 'project_path', 'project_hash',
                                         'decided_at', 'provider_outcome',
                                         'acknowledge_duplicate_risk', 'decision',
                                         'new_requests', 'data_scope'}
                         and decision['project_id'] == binding['project_id']
                         and decision['goal_hash'] == binding['goal_hash']
                         and decision['project_path'] == binding['project_path']
                         and decision['project_hash'] == binding['project_hash']
                         and decision['reservation_id'] == binding['reservation_id']
                         and decision['reservation_hash'] == binding['reservation_hash']
                         and decision['provider_outcome'] == 'unknown'
                         and decision['acknowledge_duplicate_risk'] is True
                         and decision['decision'] == 'allow_one_new_request'
                         and type(decision['new_requests']) is int
                         and decision['new_requests'] == 1
                         and decision['data_scope'] == SCOPE
                         and timestamp.utcoffset() == timedelta(hours=9)
                         and observer.requests_finished() is True)
            except (KeyError, TypeError, ValueError, AttributeError):
                valid = False
            if not valid or self.record_path.exists() or self.used_path.exists():
                _reject()
            # Never replace a signing key, even after partial issuance.
            if not self.key_path.exists():
                with self.key_path.open('xb') as key:
                    os.chmod(self.key_path, 0o600)
                    key.write(os.urandom(32))
                    key.flush()
                    os.fsync(key.fileno())
            record = {'binding': binding, 'judgment': decision}
            signature = hmac.new(self.key_path.read_bytes(), encoded(record), hashlib.sha256).hexdigest()
            self._write_new(self.record_path, {'record': record, 'signature': signature})

    def _validate(self, project, observer):
        try:
            envelope = json.loads(self.record_path.read_text())
            record = envelope['record']
            signature = hmac.new(self.key_path.read_bytes(), encoded(record), hashlib.sha256).hexdigest()
            if (self.used_path.exists() or not hmac.compare_digest(signature, envelope['signature'])
                    or record['binding'] != self._binding(project)
                    or observer.requests_finished() is not True):
                _reject()
        except (OSError, KeyError, TypeError, ValueError, AttributeError):
            _reject()

    @contextmanager
    def request_scope(self, project, observer):
        """Holds cross-process authority lock across reservation and transport.

        No loaded approval survives restart: reload, recheck worker evidence and
        consumed marker each time. A replica path never matches the signed path.
        """
        with self._lock():
            self._validate(project, observer)
            token = _active.set((self, observer))
            try:
                yield
            finally:
                _active.reset(token)


def permits(project, goal):
    active = _active.get()
    if active is None:
        return False
    ledger, observer = active
    if goal != (project.get('manager_goal') or project.get('goal', '')):
        _reject()
    ledger._validate(project, observer)
    return True


def consume(project, attempt_id):
    active = _active.get()
    if active is None:
        _reject()
    ledger, observer = active
    ledger._validate(project, observer)
    # Before project reservation: storage failure may lose permission, never
    # grant a second call. Existing reserved entry is not touched.
    ledger._write_new(ledger.used_path, {'decision_hash': fingerprint(
        json.loads(ledger.record_path.read_text())), 'new_attempt_id': attempt_id})
