"""Persistent offline goal dialogue. No network providers or execution permissions."""
from copy import deepcopy
import json
import re
import uuid
from autonomous_company import Store, require, text, exact, digest, now, parse, ID

FIELDS = ('audience', 'deliverable', 'style', 'quality', 'constraints_budget')


def safe_text(value, limit=4000):
    text(value, limit)
    require(not re.search(r'AIza[\w-]{20,}|sk-[\w-]{16,}|-----BEGIN .*PRIVATE KEY|(?:api[_ -]?key|secret|password)\s*[:=]\s*\S+', value, re.I),
            'secret_not_allowed')


def validate_spec(spec, state):
    exact(spec, (*FIELDS, 'summary', 'assumptions'))
    safe_text(spec['summary'], 1000)
    require(isinstance(spec['assumptions'], list) and len(spec['assumptions']) <= 12, 'invalid_assumptions')
    for item in spec['assumptions']: safe_text(item, 500)
    for field in FIELDS:
        item = spec[field]
        exact(item, ('value', 'evidence'))
        safe_text(item['value'], 600)
        require(isinstance(item['evidence'], list)
                and all(isinstance(ref, str) for ref in item['evidence'])
                and len(set(item['evidence'])) == len(item['evidence']), 'invalid_evidence')
        for ref in item['evidence']:
            require(isinstance(ref, str) and (ref == 'goal' or
                    ref in {n['id'] for n in state.get('user_notes', [])} or
                    ref in state['answers'] and state['answers'][ref]['status'] == 'answered'), 'invalid_evidence')
    # Evidence references are traceability, never proof that a model's interpretation is correct.
    return spec


class DialogueStore(Store):
    mode = 'goal_dialogue_offline_v1'
    marker_name = '.goal-dialogue-offline-v1'

    def valid_mode(self, p):
        return p.get('mode') == self.mode and p.get('simulation') is True and 'real_ai' not in p

    def create(self, goal, *, max_rounds=4):
        safe_text(goal, 1500)
        require(type(max_rounds) is int and 1 <= max_rounds <= 8, 'invalid_round_limit')
        self._initialize()
        p = dict(id='dialogue-'+uuid.uuid4().hex, schema_version=1, mode=self.mode, simulation=True,
                 goal=goal, created_at=now(), limits=dict(max_calls=20, max_revisions_per_task=1, max_total_revisions=2),
                 max_rounds=max_rounds, rounds=0, questions=[], answers={}, history=[], spec=None,
                 status='draft', confirmed_hash=None, handoff=None)
        self._initialize_state(p)
        self.save(p)
        return deepcopy(p)

    def _initialize_state(self, p):
        pass

    def _event(self, p, action, **data):
        p['history'].append(dict(at=now(), action=action, **deepcopy(data)))
        self.save(p)
        return deepcopy(p)

    def propose(self, draft_id, provider):
        """Provider must explicitly be offline; production live adapters are unsupported."""
        require(getattr(provider, 'offline', False) is True, 'live_dialogue_blocked')
        safe_text(provider.name, 100)
        with self.lock(draft_id):
            p = self.load(draft_id)
            require(p['status'] == 'draft' and p['rounds'] < p['max_rounds'], 'dialogue_not_ready')
            require(all(q['id'] in p['answers'] for q in p['questions']), 'pending_answers')
            # Persist before invoking: interruptions and malformed responses cannot be automatically replayed.
            p['rounds'] += 1
            p['status'] = 'awaiting_proposal'
            self._event(p, 'proposal_reserved', provider=provider.name)
            value = parse(provider.respond(deepcopy(p)))
            return self._accept_proposal(p, value, provider.name)

    def _accept_proposal(self, p, value, provider_name):
        exact(value, ('questions', 'spec', 'sufficient'))
        require(type(value['sufficient']) is bool and isinstance(value['questions'], list), 'invalid_proposal')
        qs = value['questions']
        require((value['sufficient'] and not qs) or (not value['sufficient'] and 1 <= len(qs) <= 3), 'invalid_questions')
        require(p['rounds'] < p['max_rounds'] or not qs, 'round_limit_requires_spec')
        seen_ids = {q['id'] for q in p['questions']}
        seen_text = {q['text'].strip().casefold() for q in p['questions']}
        for q in qs:
            exact(q, ('id', 'text', 'reason'))
            require(isinstance(q['id'], str) and ID.fullmatch(q['id']) and q['id'] not in seen_ids
                    and q['id'] != 'goal' and not q['id'].startswith('note-'), 'duplicate_question')
            safe_text(q['id'], 64)
            safe_text(q['text'], 500); safe_text(q['reason'], 500)
            normalized = q['text'].strip().casefold()
            require(normalized not in seen_text, 'duplicate_question')
            seen_ids.add(q['id']); seen_text.add(normalized)
        p['spec'] = deepcopy(validate_spec(value['spec'], p))
        p['questions'].extend(deepcopy(qs))
        p['status'] = 'review' if value['sufficient'] else 'draft'
        return self._event(p, 'proposal_received', provider=provider_name, proposal=value)

    def answer(self, draft_id, question_id, value=None, *, skip=False):
        if not skip: safe_text(value, 1500)
        with self.lock(draft_id):
            p = self.load(draft_id)
            require(p['status'] in ('draft', 'review') and p['handoff'] is None, 'dialogue_locked')
            require(question_id in {q['id'] for q in p['questions']}, 'unknown_question')
            answer = dict(status='skipped' if skip else 'answered', value=None if skip else value)
            require(p['answers'].get(question_id) != answer, 'duplicate_answer')
            p['answers'][question_id] = answer
            p['spec'] = None; p['status'] = 'draft'
            return self._event(p, 'answer_changed', question_id=question_id, answer=answer)

    def revise(self, draft_id, spec):
        with self.lock(draft_id):
            p = self.load(draft_id)
            require(p['status'] in ('draft', 'review', 'awaiting_proposal') and p['handoff'] is None, 'dialogue_locked')
            require(all(q['id'] in p['answers'] for q in p['questions']), 'pending_answers')
            p['spec'] = deepcopy(validate_spec(spec, p)); p['status'] = 'review'
            return self._event(p, 'user_spec_revision', spec=spec)

    def clarify(self, draft_id, value):
        """Natural-language correction for the next manager proposal, with user evidence."""
        safe_text(value, 1500)
        with self.lock(draft_id):
            p = self.load(draft_id)
            require(p['status'] in ('draft', 'review') and p['handoff'] is None, 'dialogue_locked')
            notes = p.setdefault('user_notes', [])
            require(len(notes) < 20 and not any(n['value'] == value for n in notes), 'duplicate_or_excess_note')
            index = len(notes)+1
            while 'note-'+str(index) in {q['id'] for q in p['questions']}: index += 1
            note = dict(id='note-'+str(index), value=value)
            notes.append(note); p['status'] = 'draft'
            return self._event(p, 'user_clarification', note=note)

    def confirm(self, draft_id, review_hash):
        with self.lock(draft_id):
            p = self.load(draft_id)
            require(p['status'] == 'review' and digest(p['spec']) == review_hash, 'spec_review_changed')
            p['confirmed_hash'] = review_hash; p['status'] = 'confirmed'
            return self._event(p, 'user_confirmed', spec_hash=review_hash)

    def handoff_video(self, draft_id, project_root):
        from video_production_company import VideoProductionStore
        with self.lock(draft_id):
            p = self.load(draft_id)
            require(p['status'] == 'confirmed' and p['handoff'] is None, 'handoff_not_ready')
            require(p['confirmed_hash'] == digest(p['spec']), 'spec_review_changed')
            goal = planning_goal(p)
            text(goal, 4000)
            # Never retry an uncertain create: manual inspection is required after interruption.
            p['handoff'] = dict(status='reserved', root=str(VideoProductionStore(project_root).root))
            self._event(p, 'handoff_reserved')
            project = VideoProductionStore(project_root).create(goal)
            p['handoff'].update(status='created', project_id=project['id'])
            self._event(p, 'video_project_created')
            return project


def planning_goal(p):
    """Use existing approved goal channel, preserving all live consent/context contracts."""
    return json.dumps(dict(original_goal=p['goal'], requirements=p['spec'],
                           user_answers=p['answers'], user_notes=p.get('user_notes', []), specification_hash=p['confirmed_hash'],
                           notice='User confirmed specification. Evidence references trace user input; empty evidence is an assumption. No execution consent.'),
                      ensure_ascii=False, separators=(',', ':'))
