"""Prepare/review a new single-plan scope. Actual execution remains code-policy disabled."""
import argparse
import getpass
import json
import os
import sys
import warnings
from autonomous_company import CompanyError, require
from manager_plan_acceptance import VideoManagerPlanStore


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('create')
    for name in ('prepare','status','verify-key','approve','execute'):
        sub=commands.add_parser(name);sub.add_argument('id')
        if name=='verify-key':
            for flag in ('free-tier-confirmed','billing-disabled','quota-available','official-docs-reviewed'):
                sub.add_argument('--'+flag,action='store_true')
        if name=='approve':
            sub.add_argument('review_hash')
            sub.add_argument('--owner-confirmed',action='store_true')
            sub.add_argument('--accept-google-data-policy',action='store_true')
    args=parser.parse_args(argv);store=VideoManagerPlanStore(args.root)
    try:
        if args.command=='create':
            p=store.create();print(json.dumps(dict(id=p['id'],status=p['status'],calls_used=0)))
        elif args.command=='prepare':
            result=store.prepare_consent(args.id)
            print(json.dumps(dict(review_hash=result['review_hash'],payload_hash=result['body']['payload_hash'],
                payload_path=str(store.path(args.id).with_suffix('.payload.json')),
                review_path=str(store.path(args.id).with_suffix('.review.json')),execution='disabled')))
        elif args.command=='status':
            p=store.load(args.id)
            print(json.dumps(dict(id=p['id'],status=p['status'],calls_used=len(p['real_ai']['attempts']),
                execution='disabled',account_confirmed=p['acceptance']['verification'] is not None)))
        elif args.command=='verify-key':
            require(sys.stdin.isatty() and sys.stderr.isatty(),'secure_interactive_terminal_required')
            with warnings.catch_warnings():
                warnings.simplefilter('error',getpass.GetPassWarning)
                candidate=getpass.getpass('현재 Free/Billing/쿼터를 확인한 프로젝트의 키(표시/저장 안 함): ')
            store.verify_project_key(args.id,api_key=os.getenv('GEMINI_API_KEY',''),project_api_key=candidate,
                project=store.acceptance_project,free_tier_confirmed=args.free_tier_confirmed,
                billing_disabled=args.billing_disabled,quota_available=args.quota_available,
                official_docs_reviewed=args.official_docs_reviewed)
            print('계정 사용자 확인 기록 저장. prepare를 다시 실행해 새 해시를 검토하세요. 실행 승인은 아직 없음.')
        elif args.command=='approve':
            store.approve_consent(args.id,args.review_hash,api_key=os.getenv('GEMINI_API_KEY',''),
                owner_confirmed=args.owner_confirmed,free_project_confirmed=True,
                google_data_policy_accepted=args.accept_google_data_policy)
            print('이 입력의1회 승인 기록 저장. 실제 실행 정책은 비활성.')
        else:
            p=store.ask_ai(args.id,api_key=os.getenv('GEMINI_API_KEY',''))
            print(json.dumps(dict(status=p['status'],calls_used=len(p['real_ai']['attempts']))))
        return 0
    except (CompanyError,OSError,ValueError,getpass.GetPassWarning) as exc:
        # Never log arbitrary OS/provider/input/credential text.
        print('차단: '+(exc.code if isinstance(exc,CompanyError) else 'local_operation_failed'),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
