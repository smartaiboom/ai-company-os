"""One owner scope across signed research report stages."""
import re

from autonomous_company import CompanyError, digest, require
from decision_recovery import delegated_call
from owner_operating_policy import OwnerOperatingPolicy
from video_mission_one import MISSION_ACCOUNT


def operation_kind(unit):
    name=unit['id']
    return 'youtube' if name.startswith('youtube-') else 'tavily' if name=='general-web' else 'gemini'


def definition(unit):
    return {key:value for key,value in unit.items() if key!='id'}


def envelope(source,base,anchor=None):
    name=anchor or source.root.name
    require(re.fullmatch(r'research-company-[a-f0-9]{32}-[a-f0-9]{20}',name),
            'owner_policy_scope_changed')
    require(name.startswith('research-'+source.binding['project']+'-'),'owner_policy_scope_changed')
    return OwnerOperatingPolicy(source.root.parent/(name+'-work'),dict(mode='research_work_scope_v1',
        project=source.binding['project'],anchor=name,goal_sha256=digest(
            {field:base[field] for field in ('mission','target','audience','constraints','output')})))


def proposal(work,stage,*,budget=None):
    units=[]
    limits={}
    allowed={}
    for operation in stage['units']:
        kind=operation_kind(operation)
        limits[kind]=limits.get(kind,0)+1
        choice=definition(operation)
        if choice not in allowed.setdefault(kind,[]):
            allowed[kind].append(choice)
    # Up to one additional staff report and manager review. No additional searches are implied.
    if not stage.get('continuation_sha256'):
        limits['gemini']+=2
    if budget is not None:
        required={kind:sum(operation_kind(row)==kind for row in stage['units']) for kind in limits}
        require(all(required[kind]<=budget.get(kind,0) for kind in required),'owner_policy_exhausted')
        limits={kind:min(count,budget[kind]) for kind,count in limits.items()}
    for kind,count in limits.items():
        units.extend(dict(id=f'{kind}-{i}',provider=kind,max_cost_usd=0) for i in range(count))
    phases=['approved_collection','staff_report','manager_review','owner_feedback_rewrite']
    if stage.get('checkpoint_report_only'):
        phases=['staff_report','manager_review'] if stage['max_model_calls']==2 else ['manager_review']
    return {**work.proposal(units),'limits':limits,'allowed':allowed,'provider_project':MISSION_ACCOUNT,
            'phases':phases,
            'gemini_inputs':['project_goal','constraints','approved_public_queries','observed_evidence',
                             'prior_report_and_owner_feedback'],'initial_stage_sha256':digest(stage)}


CORRECTABLE_RULES = ('option_not_allowed', 'mixed_tool_and_report')


def development_proposal(work, stage):
    standard = proposal(work, stage)
    units = [dict(id=kind,provider=kind,max_cost_usd=0) for kind in standard['allowed']]
    standard.pop('limits')
    return {**standard, 'units':units, 'mode':'development_scope',
            'purpose':'verify_general_research_response_and_public_evidence',
            'gemini_inputs':[*standard['gemini_inputs'],'local_validation_rule_and_instruction'],
            'response_contract_correction':list(CORRECTABLE_RULES),
            'account_evidence':'owner_attested_free_only_provider_status_unverified'}


def unresolved(ledger):
    repaired = {item['reservation'].get('replaces') for item in ledger.values()
                if item['result'] and item['result']['status']=='completed'}
    return {name for name, item in ledger.items() if name not in repaired
            and (not item['result'] or item['result']['status']!='completed')}


def remaining(work,grant):
    ledger=work.attempts()
    require(all(row['result'] and row['result']['status']=='completed' for row in ledger.values()),
            'owner_policy_unresolved_attempt')
    limits=grant['proposal']['limits']
    return {name:count-sum(row['reservation']['unit']['provider']==name for row in ledger.values())
            for name,count in limits.items()}


def check_stage(work,key,stage):
    grant=work.active(key)
    if grant['proposal'].get('mode') == 'development_scope':
        require(not unresolved(work.attempts()), 'owner_policy_unresolved_attempt')
        require(all(definition(operation) in grant['proposal']['allowed'].get(operation_kind(operation),[])
                    for operation in stage['units']), 'owner_policy_scope_changed')
        return grant,None
    left=remaining(work,grant)
    needed={}
    for operation in stage['units']:
        kind=operation_kind(operation)
        require(definition(operation) in grant['proposal']['allowed'].get(kind,[]),'owner_policy_scope_changed')
        needed[kind]=needed.get(kind,0)+1
    require(all(count<=left.get(name,0) for name,count in needed.items()),'owner_policy_exhausted')
    return grant,left


def charge(work,key,operation,payload,invoke,*,replaces=None):
    grant=work.active(key)
    provider=operation_kind(operation)
    if grant['proposal'].get('mode')=='development_scope':
        require(definition(operation) in grant['proposal']['allowed'].get(provider,[]),'owner_policy_scope_changed')
        ledger=work.attempts()
        unit=dict(id=f'{provider}:{len(ledger)+1}',provider=provider,max_cost_usd=0)
        replaced=None
        if replaces is not None:
            prior_operation, prior_payload=replaces
            target=digest(dict(operation=prior_operation,payload_hash=prior_payload))
            matches=[name for name,row in ledger.items() if row['reservation']['payload_sha256']==target]
            require(len(matches)==1,'owner_policy_unresolved_attempt')
            replaced=matches[0]
        return delegated_call(work,key,unit,digest(dict(operation=operation,payload_hash=payload)),
                             lambda _proof,check:invoke(check),replaces=replaced)
    require(replaces is None,'owner_policy_scope_changed')
    left=remaining(work,grant)
    require(left.get(provider,0)>0,'owner_policy_exhausted')
    require(definition(operation) in grant['proposal']['allowed'].get(provider,[]),'owner_policy_scope_changed')
    index=grant['proposal']['limits'][provider]-left[provider]
    unit=dict(id=f'{provider}-{index}',provider=provider,max_cost_usd=0)
    delegated_call(work,key,unit,digest(dict(operation=operation,payload_hash=payload)),
                   lambda _proof,check:invoke(check))


def inherited(source,base):
    anchor=base.get('work_anchor')
    if not anchor:
        return None
    work=envelope(source,base,anchor)
    policy=work.read('policy.json')
    return None if policy and policy['proposal'].get('mode')=='development_scope' else work
