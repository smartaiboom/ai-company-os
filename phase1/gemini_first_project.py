"""Prepare locally; a separate explicit owner command approves and runs once."""
import argparse
import json
import os
from pathlib import Path
from autonomous_company import CompanyError,require,digest,parse
from autonomous_gemini import GeminiStore,GeminiCompany,GeminiConfig
from autonomous_live import LiveManagerProvider,LiveEmployeeProvider
from gemini_provider import MODEL,ENDPOINT

ROOT=Path(__file__).resolve().parent/'data/gemini-first-autonomous-20261104'
GOAL=('개인·회사 비밀 없는 합성 교육 목표: 초보자가 AI에게 좋은 질문을 작성하는 방법을 '
      '한국어 자막과 로컬 한국어 음성으로 설명하는 20~30초 MP4를 만들고 최종 보고서를 제공해 주세요. '
      'AI 관리자가 필요한 계획·직원 배정·품질 기준을 정하고 직원 산출물을 검토하여 필요하면 수정하세요. '
      '외부 검색이나 업로드 없이 제공된 목표와 생성한 내용 및 허용된 로컬 영상 도구만 사용하세요. '
      '실측한 영상 기술 검사와 독립 확인하지 않은 내용·미적 품질은 구분해 보고하세요.')


def write_new(path,value):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())


def prepare(root=None):
    # Never issues a grant, creates a signing key or starts a company.
    root=Path(root) if root is not None else ROOT
    require(not root.exists(),'first_project_already_prepared')
    store=GeminiStore(root)
    p=store.create(GOAL,local_tools=['caption_video_v1'])
    b=store.prepare(p['id'],confirm_free_account=True)
    write_new(root/'operating-proposal.json',b)
    manifest={'project_id':p['id'],'review_hash':digest(b)}
    write_new(root/'launch-manifest.json',manifest)
    return manifest


def execute(review_hash,*,owner_confirmed=False,confirm_free_tier=False,root=None):
    require(owner_confirmed is True and confirm_free_tier is True,'explicit_owner_confirmation_required')
    root=Path(root) if root is not None else ROOT
    store=GeminiStore(root)
    m=parse((root/'launch-manifest.json').read_text());b=parse((root/'operating-proposal.json').read_text())
    require(review_hash==m['review_hash']==digest(b),'consent_review_changed')
    p=store.load(m['project_id']);store._check_contract(p,b)
    require(p['storage_hash']==b['initial_state_hash'] and p['status']=='ready'
            and not p['real_ai']['attempts'] and not p['real_ai']['enabled'],'first_project_not_ready')
    config=GeminiConfig(os.getenv('GEMINI_API_KEY',''))
    require(bool(config.api_key.strip()),'missing_gemini_key')
    for name,value in (('GEMINI_MODEL',MODEL),('GEMINI_ENDPOINT',ENDPOINT),('GEMINI_AUTONOMOUS_FREE_ENABLED','1')):
        require(os.getenv(name,value)==value,'gemini_provider_binding')
        os.environ[name]=value  # Only this explicit launch process; never .env/global settings.
    company=GeminiCompany(store,LiveManagerProvider('gemini-free-manager'),
                          LiveEmployeeProvider('gemini-free-employee'),config)
    write_new(root/'owner-launch-consumed.json',{'project_id':p['id'],'review_hash':review_hash,'consumed':True})
    p=store.approve(p['id'],b,review_hash=review_hash,owner_confirmed=True)
    result=company.run(p['id'],expected_state_hash=p['storage_hash'])
    return {k:result.get(k) for k in ('id','status','reason_code','phase','artifacts')}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Gemini 최초 프로젝트: 준비는 송신 0회, execute는 최초 운영 승인 후 자율 실행')
    parser.add_argument('--store',help='새 독립 저장소. 기존 stopped 저장소를 초기화하거나 재사용하지 않음')
    sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('prepare')
    p=sub.add_parser('execute');p.add_argument('--review-hash',required=True)
    p.add_argument('--owner-confirmed',action='store_true');p.add_argument('--confirm-free-tier',action='store_true')
    args=parser.parse_args(argv)
    try:
        result=prepare(args.store) if args.command=='prepare' else execute(args.review_hash,
                owner_confirmed=args.owner_confirmed,confirm_free_tier=args.confirm_free_tier,root=args.store)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (CompanyError,OSError,ValueError):
        print('준비 또는 실행이 차단됐습니다. 동의안·무료 등급·유효기간·소진 기록을 확인하세요. 자동 재시도하지 않습니다.')
        return 1


if __name__=='__main__':raise SystemExit(main())
