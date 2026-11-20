"""Finite owner delegation. Callers serialize control and execution under their project lock."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import hmac
import os
from pathlib import Path

from autonomous_company import Store, digest, now, parse, require
from autonomous_live import LiveStore


class OwnerOperatingPolicy:
    _sign = LiveStore._sign

    def __init__(self, root, binding):
        self.root=Path(root)
        self.binding=binding
        require(not any(p.is_symlink() for p in (self.root,*self.root.parents)), 'invalid_owner_policy_path')

    def read(self, name):
        path=self.root/name
        require(not path.is_symlink(), 'invalid_owner_policy_path')
        if not path.exists():
            return None
        require(path.is_file() and path.stat().st_mode & 0o077 == 0, 'invalid_owner_policy_path')
        document=parse(path.read_text())
        record=document['record']
        require(hmac.compare_digest(document['signature'],self._sign(record)), 'owner_policy_signature')
        return record

    def write(self, name, record):
        path=self.root/name
        require(not path.exists() and not path.is_symlink(), 'owner_policy_replay')
        Store.atomic(path,dict(record=record,signature=self._sign(record,create=True)))

    def proposal(self, units):
        return dict(version=1,binding=self.binding,units=units,free_only=True,max_cost_usd=0,
                    valid_hours=24,provider_quota='unknown',provider_billing='unknown',
                    automatic_retry=False,stop_on_uncertain=True)

    def approve(self, proposal, review_hash, key):
        require(proposal['binding']==self.binding and digest(proposal)==review_hash
                and proposal['units'] and proposal['free_only'] is True
                and proposal['max_cost_usd']==0 and not self.root.exists(), 'owner_policy_scope_changed')
        issued=now()
        self.root.mkdir(mode=0o700)
        self.write('policy.json',dict(proposal=proposal,issued_at=issued,
            expires_at=(datetime.fromisoformat(issued)+timedelta(hours=proposal['valid_hours'])).isoformat(),
            account_confirmation=('owner_attested_free_only_provider_status_unverified'
                                  if proposal.get('account_evidence') else
                                  'owner_attested_free_billing_disabled_and_budget_available'),
            credential_binding=self._sign(dict(binding=self.binding,credential=key),create=True)))

    def active(self, key):
        record=self.read('policy.json')
        require(record is not None, 'owner_policy_required')
        require(self.read('revoked.json') is None, 'owner_policy_revoked')
        require(datetime.fromisoformat(now())<datetime.fromisoformat(record['expires_at']), 'owner_policy_expired')
        require(record['proposal']['binding']==self.binding
                and record['proposal']['free_only'] is True and record['proposal']['max_cost_usd']==0,
                'owner_policy_scope_changed')
        self.check_credential(record, key)
        return record

    def check_credential(self, record, key):
        require(hmac.compare_digest(record['credential_binding'],
                    self._sign(dict(binding=self.binding,credential=key))), 'owner_policy_key_changed')

    def revoke(self):
        with self.control_lock():
            record=self.read('policy.json')
            require(record is not None, 'owner_policy_required')
            self.write('revoked.json',dict(policy_hash=digest(record),at=now()))

    @contextmanager
    def control_lock(self):
        require(self.root.is_dir(), 'owner_policy_required')
        fd=os.open(self.root/'.control.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            yield

    def attempts(self):
        attempts={}
        for path in sorted(self.root.glob('reserve-*.json')):
            item=self.read(path.name)
            result=self.read('result-'+path.name.removeprefix('reserve-'))
            if result is not None:
                require(result['reservation_hash']==digest(item),'owner_policy_signature')
            attempts[item['unit']['id']]=dict(reservation=item,result=result)
        return attempts

    def reserve(self, key, unit, payload_hash):
        with self.control_lock():
            grant=self.active(key)
            ledger=self.attempts()
            require(all(item['result'] and item['result']['status']=='completed' for item in ledger.values()),
                    'owner_policy_unresolved_attempt')
            require(unit in grant['proposal']['units'] and unit['max_cost_usd']==0, 'owner_policy_scope_changed')
            require(unit.get('payload_sha256',payload_hash)==payload_hash,'owner_policy_scope_changed')
            require(unit['id'] not in ledger, 'owner_policy_exhausted')
            reservation=dict(policy_hash=digest(grant),unit=unit,payload_sha256=payload_hash,at=now())
            self.write('reserve-'+digest(unit['id'])+'.json',reservation)
            return reservation

    def finish(self, reservation, status, *, diagnostics=None):
        result = dict(reservation_hash=digest(reservation), status=status, at=now())
        if diagnostics:
            result['diagnostics'] = diagnostics
        self.write('result-'+digest(reservation['unit']['id'])+'.json', result)
