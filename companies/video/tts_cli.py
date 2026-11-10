"""Private terminal review for one TTS request; production remains disabled."""
import argparse
import getpass
import json
import sys
import warnings
from autonomous_company import CompanyError, require
from tts_execution import TTSExecution


def secure_key(prompt):
    require(sys.stdin.isatty() and sys.stderr.isatty(), 'secure_interactive_terminal_required')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        return getpass.getpass(prompt)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare'); prepare.add_argument('--source-job', required=True); prepare.add_argument('--project', required=True)
    commands.add_parser('status')
    verify = commands.add_parser('verify-key'); verify.add_argument('--evidence', required=True)
    commands.add_parser('review')
    approve = commands.add_parser('approve'); approve.add_argument('review_hash')
    approve.add_argument('--owner-confirmed', action='store_true')
    approve.add_argument('--accept-google-data-policy', action='store_true')
    commands.add_parser('execute')
    args = parser.parse_args(argv)
    try:
        runner = TTSExecution(args.root)
        if args.command == 'prepare': result = runner.create(args.source_job, args.project)
        elif args.command == 'status': result = runner.status()
        elif args.command == 'verify-key':
            key = secure_key('실행에 사용할 키(표시/저장 안 함): ')
            project_key = secure_key('확인한 AI Studio 프로젝트의 키(로컬 대조): ')
            with open(args.evidence, encoding='utf-8') as stream: evidence = json.load(stream)
            runner.verify_key(key, project_key, evidence)
            result = dict(account='owner_attested_not_independently_verified', execution='disabled_by_default')
        elif args.command == 'review': result = runner.review(secure_key('대조할 실행 키: '))
        elif args.command == 'approve':
            runner.approve(args.review_hash, secure_key('대조할 실행 키: '),
                owner_confirmed=args.owner_confirmed, accept_google_data_policy=args.accept_google_data_policy)
            result = dict(consent='signed_exact_tts_once', execution='disabled_by_default')
        else: result = runner.execute(secure_key('단1회 실행 키: '))
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (CompanyError, OSError, ValueError, KeyError, TypeError, getpass.GetPassWarning):
        print('차단: TTS 확인/승인/실행 조건 미충족. 키와 원시 오류는 출력하지 않습니다.', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
