"""Offline video goal dialogue CLI. Never starts production or calls an AI API."""
import argparse
import json
from pathlib import Path
from autonomous_company import CompanyError, digest
from goal_dialogue import DialogueStore


class OfflineProposal:
    offline = True
    name = 'user_supplied_offline_proposal_not_live_AI'

    def __init__(self, raw): self.raw = raw
    def respond(self, context): return self.raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='data/goal_dialogues')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create'); create.add_argument('goal'); create.add_argument('--max-rounds', type=int, default=4)
    for name in ('show', 'propose', 'answer', 'skip', 'revise', 'confirm', 'handoff'):
        command = sub.add_parser(name); command.add_argument('id')
        if name in ('propose', 'revise'): command.add_argument('json_file')
        if name in ('answer', 'skip'): command.add_argument('question_id')
        if name == 'answer': command.add_argument('value')
        if name == 'confirm': command.add_argument('review_hash')
        if name == 'handoff': command.add_argument('--projects', default='data/dialogue_video_projects')
    args = parser.parse_args(argv); store = DialogueStore(args.root)
    try:
        if args.command == 'create': result = store.create(args.goal, max_rounds=args.max_rounds)
        elif args.command == 'show': result = store.load(args.id)
        elif args.command == 'propose': result = store.propose(args.id, OfflineProposal(Path(args.json_file).read_text()))
        elif args.command == 'answer': result = store.answer(args.id, args.question_id, args.value)
        elif args.command == 'skip': result = store.answer(args.id, args.question_id, skip=True)
        elif args.command == 'revise':
            from autonomous_company import parse
            result = store.revise(args.id, parse(Path(args.json_file).read_text()))
        elif args.command == 'confirm': result = store.confirm(args.id, args.review_hash)
        else: result = store.handoff_video(args.id, args.projects)
        if result.get('spec'): result['review_hash'] = digest(result['spec'])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CompanyError, OSError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
