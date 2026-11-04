"""Local explicit commands; execution never manufactures operating consent."""
import argparse
import json
import os
from pathlib import Path
from autonomous_company import CompanyError, digest, parse
from autonomous_live import LiveStore, LiveCompany, LiveManagerProvider, LiveEmployeeProvider, LiveConfig
from autonomous_free import FreeStore, FreeCompany


def main(argv=None):
    parser=argparse.ArgumentParser(description='자율 회사 live 운영 동의 및 실행. 기본 상태는 송신 차단입니다.')
    parser.add_argument('--store',required=True,help='기존 업무 데이터와 분리된 새 저장 경로')
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create');create.add_argument('--goal',required=True)
    create.add_argument('--local-video',action='store_true',help='새 free-v2 프로젝트에 한정된 로컬 자막 MP4 도구')
    create.add_argument('--max-calls',type=int,default=None,help='선택적 기술 상한. 새 무료 프로젝트 기본값은 상한 없음')
    for name in ('recovery-proposal','status','prepare','approve','revoke','start','resume','run','continue'):
        p=sub.add_parser(name);p.add_argument('project_id')
        if name=='prepare':
            p.add_argument('--hours',type=int,default=24);p.add_argument('--per-start',type=int,default=None,help='기존 bounded 계약에만 사용')
            p.add_argument('--proposal-out',help='검토할 contract를 새 파일로 저장; 기존 파일 덮어쓰기 금지')
        if name=='approve':
            p.add_argument('--proposal',required=True,help='prepare에서 확인한 contract JSON 파일')
            p.add_argument('--review-hash',required=True)
        if name in ('approve','revoke'):p.add_argument('--owner-confirmed',action='store_true')
        if name in ('start','resume','run','continue'):p.add_argument('--state-hash',required=True)
    args=parser.parse_args(argv)
    try:
        legacy=(Path(args.store)/LiveStore.marker_name).is_file()
        if legacy and (Path(args.store)/FreeStore.marker_name).exists():raise CompanyError('ambiguous_store')
        store=LiveStore(args.store) if legacy else FreeStore(args.store)
        if args.command=='create':
            options={} if legacy and args.max_calls is None else {'max_calls':args.max_calls}
            if args.local_video:
                if legacy:raise CompanyError('legacy_tools_forbidden')
                options['local_tools']=['caption_video_v1']
            value=store.create(args.goal,**options)
        elif args.command=='prepare':
            if legacy:
                body=store.prepare(args.project_id,valid_hours=args.hours,per_start=2 if args.per_start is None else args.per_start)
            else:
                if args.per_start is not None:raise CompanyError('free_policy_has_no_per_start_cap')
                body=store.prepare(args.project_id,valid_hours=args.hours)
            if args.proposal_out:
                with os.fdopen(os.open(args.proposal_out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
                    json.dump(body,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
            value={'goal':store.load(args.project_id)['goal'],'contract':body,'review_hash':digest(body),
                   'notice':'동의 준비일 뿐입니다. contract만 파일로 저장하고 범위를 검토한 뒤 별도 approve 명령으로 승인합니다.'}
        elif args.command=='approve':
            path=Path(args.proposal)
            if path.stat().st_size>16384:raise CompanyError('proposal_too_large')
            value=store.approve(args.project_id,parse(path.read_text()),review_hash=args.review_hash,
                                owner_confirmed=args.owner_confirmed)
        elif args.command=='revoke':value=store.revoke(args.project_id,owner_confirmed=args.owner_confirmed)
        elif args.command=='status':value=store.result(args.project_id)
        elif args.command=='recovery-proposal':
            from autonomous_recovery import recovery_proposal
            value=recovery_proposal(store,args.project_id)
        else:
            if legacy and args.command in ('run','continue'):raise CompanyError('legacy_contract_requires_bounded_start_resume')
            cls=LiveCompany if legacy else FreeCompany
            company=cls(store,LiveManagerProvider(),LiveEmployeeProvider(),LiveConfig.from_env())
            value=company.run(args.project_id,expected_state_hash=args.state_hash,resume=args.command in ('resume','continue'))
        # Deliberately show only operational summaries, never raw role replies or credentials.
        if 'storage_hash' in value:
            value={k:value[k] for k in ('id','status','phase','storage_hash','artifacts')}
            p=store.load(value['id']);value['calls_used']=len(p['real_ai']['attempts'])
            value['reason_code']=p.get('reason_code');value['business_approvals']=p['user_business_approval_requests']
            value['policy']=p.get('policy_version',1)
            value['optional_or_legacy_call_cap']=p['limits']['max_calls']
        print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    except (CompanyError,OSError,ValueError) as exc:
        code=exc.code if isinstance(exc,CompanyError) else 'local_input_or_storage_error'
        print('작업이 안전하게 중단되었습니다. 동의·상태 해시·모델·서버 설정을 확인하세요. 자동 재전송하지 않습니다. 코드: '+code)
        return 1


if __name__=='__main__':raise SystemExit(main())
