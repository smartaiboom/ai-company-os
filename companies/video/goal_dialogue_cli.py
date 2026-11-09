"""Video goal dialogue CLI: offline proposals or isolated, consent-gated Gemini manager."""
import argparse
import json
import os
from pathlib import Path
from autonomous_company import CompanyError, digest, parse
from goal_dialogue import DialogueStore, FIELDS
from goal_dialogue_live import (LiveDialogueStore, OneCallAcceptanceStore, MODEL, ENDPOINT,
                                LIVE_TRANSPORT_ENABLED, ACCEPTANCE_GOAL, ACCEPTANCE_PROJECT, GOOGLE_TERMS)

LABELS = dict(audience='대상 사용자', deliverable='산출물', style='스타일',
              quality='품질 기준', constraints_budget='제약·예산')


class OfflineProposal:
    offline = True
    name = 'user_supplied_offline_proposal_not_live_AI'
    def __init__(self, raw): self.raw = raw
    def respond(self, context): return self.raw


def show_context(context):
    print('전송할 원래 목표: '+context['goal'])
    for q in context['questions']:
        answer = context['answers'].get(q['id'])
        print(f"  {q['id']}: {q['text']} (필요 근거: {q['reason']})")
        if answer: print('  답변: '+(answer['value'] if answer['status'] == 'answered' else '건너뜀'))
    for note in context['user_notes']: print(f"  사용자 수정 {note['id']}: {note['value']}")
    for revised in context['user_spec_revisions']:
        print('이전에 사용자가 수정한 명세:'); show_spec(revised)
    if context['specification']:
        print('현재 명세:'); show_spec(context['specification'])


def show_spec(spec):
    print('요구사항: '+spec['summary'])
    for field in FIELDS:
        item = spec[field]
        refs = ', '.join(item['evidence'])
        print(f"  {LABELS[field]}: {item['value']} [사용자 입력 참조: {refs}]" if refs else
              f"  {LABELS[field]}: {item['value']} [AI 추정/미확정]")
    for item in spec['assumptions']: print('  가정·미확정: '+item)
    print('근거 참조의 해석도 모델 주장입니다. 사용자 최종 검토가 필요합니다.')


def display(result, store):
    if 'transmission' in result:
        body = result['body']
        print(f"전송 동의 준비 · 초안 {body['draft_id']}\n공급자: Google Gemini · 모델: {MODEL}\n주소: {ENDPOINT}")
        print(f"이번 실행 1회 / 초안 누적 한도 {body['total_limit']}회 · 최대 비용 0 · 유료 전환/재시도 없음")
        print('무료 계정·키 연결 확인은 별도 필요하며 실제 남은 쿼터·0원 사용을 보장하지 않습니다.')
        if isinstance(store, OneCallAcceptanceStore):
            print('전용 인수 테스트: 로컬 키 대조 + Free/Billing 확인 + 아래 해시의 명시 승인 전까지 전송 금지.')
            print('인수 범위 해시: '+body['policy']['scope_hash'])
            print('현재 키 대조 기록: '+('미확인' if body['policy']['verification_hash'] == digest(None) else '사용자 로컬 확인 기록 있음(원격 검증 아님)'))
            print('Google 무료 서비스 입력·응답은 제품 개선에 이용되고 사람이 검토할 수 있습니다: '+GOOGLE_TERMS)
            print('키 대조 후 재준비하면 승인 해시가 바뀝니다. 이전 해시를 재사용하지 마세요.')
        print('전송 범위: 원래 목표, 질문·답변, 사용자 수정, 현재/사용자 수정 명세, 라운드 한도. 원장/키/파일 경로 제외.')
        show_context(result['transmission'])
        print('동의 만료: '+body['expires_at'])
        print('검토 해시: '+result['review_hash'])
        if isinstance(store, OneCallAcceptanceStore):
            print(f"요청 본문 {result['request_bytes']} bytes · 출력 최대 4096 tokens · 토큰 계수 API 호출 없음")
            print('전체 요청 본문(인증키 제외):')
            print(json.dumps(result['wire_payload'], ensure_ascii=False, indent=2))
        return
    if 'questions' not in result:
        print(f"영상 회사 초안 생성: {result['id']} · 제작 실행 승인 없음")
        return
    print(f"초안: {result['id']} · 상태: {result['status']} · 문답: {result['rounds']}/{result['max_rounds']}")
    print('목표: '+result['goal'])
    if isinstance(store, LiveDialogueStore):
        print(f"Gemini {MODEL} · 일반 전송 {'활성' if LIVE_TRANSPORT_ENABLED else '기본 차단'}")
        if isinstance(store, OneCallAcceptanceStore):
            print('인수 전용 예외: 사용자 키 대조·Free/Billing·Google 데이터 정책·해시 승인 필요, 최대 1회')
        print(f"호출 시도 {len(result['real_ai']['attempts'])}/{result['real_ai']['limit']} · "+store.consent_status(result))
    else: print('오프라인 제안 · 실제 AI 실행 결과가 아닙니다.')
    for q in result['questions']:
        answer = result['answers'].get(q['id'])
        print(f"[{q['id']}] {q['text']} (필요 근거: {q['reason']})")
        if answer: print('  답변: '+(answer['value'] if answer['status'] == 'answered' else '건너뜀'))
        else: print('  answer 명령으로 답하거나 skip으로 건너뛰세요.')
    for note in result.get('user_notes', []): print('사용자 수정: '+note['value'])
    if result.get('spec'):
        show_spec(result['spec']); print('명세 검토 해시: '+digest(result['spec']))
    if result['status'] == 'review': print('수정: revise <ID> --text "수정 요청" / 확정: confirm <ID> <검토 해시>')
    if result.get('handoff'): print('영상 초안 연결 상태: '+result['handoff']['status'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true', help='별도 Gemini 문답 저장소 (외부 전송 승인은 별도)')
    mode.add_argument('--acceptance', action='store_true', help='고정 가상 목표의 Gemini 요청 1회 인수 테스트')
    parser.add_argument('--json', action='store_true', help='기존 도구용 JSON 출력')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create'); create.add_argument('goal', nargs='?'); create.add_argument('--max-rounds', type=int)
    for name in ('show', 'propose', 'answer', 'skip', 'revise', 'confirm', 'handoff',
                 'prepare-consent', 'approve-consent', 'ask-ai', 'verify-acceptance-key'):
        command = sub.add_parser(name); command.add_argument('id')
        if name == 'propose': command.add_argument('json_file')
        if name == 'revise':
            command.add_argument('json_file', nargs='?'); command.add_argument('--text')
        if name in ('answer', 'skip'): command.add_argument('question_id')
        if name == 'answer': command.add_argument('value', nargs='?')
        if name == 'confirm': command.add_argument('review_hash', nargs='?')
        if name == 'handoff': command.add_argument('--projects', default='data/dialogue_video_projects')
        if name == 'approve-consent':
            command.add_argument('review_hash')
            command.add_argument('--owner-confirmed', action='store_true')
            command.add_argument('--verified-free-project', action='store_true')
            command.add_argument('--accept-google-data-policy', action='store_true')
        if name == 'verify-acceptance-key':
            command.add_argument('--project', default=ACCEPTANCE_PROJECT)
            command.add_argument('--free-tier-confirmed', action='store_true')
            command.add_argument('--billing-disabled', action='store_true')
    args = parser.parse_args(argv)
    store_type = OneCallAcceptanceStore if args.acceptance else (LiveDialogueStore if args.live else DialogueStore)
    store = store_type(args.root or ('data/gemini_one_call_acceptance' if args.acceptance else
                                   ('data/goal_dialogues_gemini35' if args.live else 'data/goal_dialogues')))
    try:
        if args.command in ('prepare-consent', 'approve-consent', 'ask-ai') and not (args.live or args.acceptance):
            raise CompanyError('live_store_required')
        if args.command == 'create':
            if args.acceptance: result = store.create(args.goal or ACCEPTANCE_GOAL, max_rounds=args.max_rounds)
            else: result = store.create(args.goal, max_rounds=4 if args.max_rounds is None else args.max_rounds)
        elif args.command == 'verify-acceptance-key':
            if not args.acceptance: raise CompanyError('acceptance_store_required')
            import getpass
            import sys
            import warnings
            if not sys.stdin.isatty(): raise CompanyError('secure_local_terminal_required')
            print('AI Studio의 해당 Free 프로젝트에서 복사한 키를 로컬 비표시 입력으로 대조합니다. 채팅에 키를 보내지 마세요.')
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                try: project_key = getpass.getpass('프로젝트 API 키 (비표시): ')
                except getpass.GetPassWarning: raise CompanyError('secure_local_terminal_required') from None
            try:
                result = store.verify_project_key(args.id, api_key=os.getenv('GEMINI_API_KEY', ''),
                    project_api_key=project_key, project=args.project, free_tier_confirmed=args.free_tier_confirmed,
                    billing_disabled=args.billing_disabled)
            finally: project_key = None
        elif args.command == 'show': result = store.load(args.id)
        elif args.command == 'prepare-consent': result = store.prepare_consent(args.id)
        elif args.command == 'approve-consent':
            options = dict(owner_confirmed=args.owner_confirmed, free_project_confirmed=args.verified_free_project)
            if args.acceptance: options['google_data_policy_accepted'] = args.accept_google_data_policy
            result = store.approve_consent(args.id, args.review_hash, **options)
        elif args.command == 'ask-ai': result = store.ask_ai(args.id, api_key=os.getenv('GEMINI_API_KEY', ''))
        elif args.command == 'propose': result = store.propose(args.id, OfflineProposal(Path(args.json_file).read_text()))
        elif args.command == 'answer':
            value = args.value
            if value is None:
                p = store.load(args.id)
                question = next((q for q in p['questions'] if q['id'] == args.question_id), None)
                if question is None: raise CompanyError('unknown_question')
                value = input(question['text']+'\n답변: ')
            result = store.answer(args.id, args.question_id, value)
        elif args.command == 'skip': result = store.answer(args.id, args.question_id, skip=True)
        elif args.command == 'revise':
            if args.json_file and args.text: raise CompanyError('choose_text_or_json_revision')
            if args.json_file: result = store.revise(args.id, parse(Path(args.json_file).read_text()))
            else: result = store.clarify(args.id, args.text or input('명세에서 바꿀 내용을 적어 주세요: '))
        elif args.command == 'confirm':
            review_hash = args.review_hash
            if review_hash is None:
                p = store.load(args.id)
                if p['status'] != 'review': raise CompanyError('spec_not_ready')
                display(p, store)
                if input('위 명세를 최종 확정하려면 "확정"을 입력하세요: ') != '확정':
                    raise CompanyError('confirmation_cancelled')
                review_hash = digest(p['spec'])
            result = store.confirm(args.id, review_hash)
        else: result = store.handoff_video(args.id, args.projects)
        if args.json:
            if result.get('spec'): result['review_hash'] = digest(result['spec'])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else: display(result, store)
        return 0
    except (CompanyError, OSError, UnicodeError, EOFError) as exc:
        # Never print credentials, arbitrary provider errors, or file contents.
        print('오류: '+(exc.code if isinstance(exc, CompanyError) else 'local_io_or_input_failed'))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
