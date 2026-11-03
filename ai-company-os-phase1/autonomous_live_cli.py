"""Local explicit commands; execution never manufactures operating consent."""
import argparse
import json
import os
from pathlib import Path
from autonomous_company import CompanyError, digest, parse
from autonomous_live import LiveStore, LiveCompany, LiveManagerProvider, LiveEmployeeProvider, LiveConfig


def main(argv=None):
    parser=argparse.ArgumentParser(description='자율 회사 live 운영 동의 및 실행. 기본 상태는 송신 차단입니다.')
    parser.add_argument('--store',required=True,help='기존 업무 데이터와 분리된 새 저장 경로')
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create');create.add_argument('--goal',required=True)
    create.add_argument('--max-calls',type=int,default=20)
    for name in ('status','prepare','approve','revoke','start','resume'):
        p=sub.add_parser(name);p.add_argument('project_id')
        if name=='prepare':
            p.add_argument('--hours',type=int,default=24);p.add_argument('--per-start',type=int,default=2)
            p.add_argument('--proposal-out',help='검토할 contract를 새 파일로 저장; 기존 파일 덮어쓰기 금지')
        if name=='approve':
            p.add_argument('--proposal',required=True,help='prepare에서 확인한 contract JSON 파일')
            p.add_argument('--review-hash',required=True)
        if name in ('approve','revoke'):p.add_argument('--owner-confirmed',action='store_true')
        if name in ('start','resume'):p.add_argument('--state-hash',required=True)
    args=parser.parse_args(argv);store=LiveStore(args.store)
    try:
        if args.command=='create':value=store.create(args.goal,max_calls=args.max_calls)
        elif args.command=='prepare':
            body=store.prepare(args.project_id,valid_hours=args.hours,per_start=args.per_start)
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
        else:
            company=LiveCompany(store,LiveManagerProvider(),LiveEmployeeProvider(),LiveConfig.from_env())
            value=company.run(args.project_id,expected_state_hash=args.state_hash,resume=args.command=='resume')
        # Deliberately show only operational summaries, never raw role replies or credentials.
        if 'storage_hash' in value:
            value={k:value[k] for k in ('id','status','phase','storage_hash','artifacts')}
            p=store.load(value['id']);value['calls_used']=len(p['real_ai']['attempts'])
            value['reason_code']=p.get('reason_code');value['business_approvals']=p['user_business_approval_requests']
        print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    except (CompanyError,OSError,ValueError) as exc:
        code=exc.code if isinstance(exc,CompanyError) else 'local_input_or_storage_error'
        print('작업이 안전하게 중단되었습니다. 동의·상태 해시·모델·서버 설정을 확인하세요. 자동 재전송하지 않습니다. 코드: '+code)
        return 1


if __name__=='__main__':raise SystemExit(main())
