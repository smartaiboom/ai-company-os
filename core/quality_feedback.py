"""Offline experience journal and provider-ready context; never grants transport permission."""
from copy import deepcopy
from autonomous_company import Store, require, exact, digest, now
from goal_dialogue import safe_text

EXPERIENCE_FIELDS = ('project', 'domain', 'target_segment', 'issue', 'positive_preference',
                     'proposed_correction', 'evidence', 'source', 'confidence', 'verification')

# Passed to an explicitly approved future provider, never executed by this module.
ROLE_CONTRACTS = {
    'manager': 'Use goal, answers, constraints, capabilities and scoped experiences. Return existing '
               'tasks/criteria/rationale/uncertainty contract. Instructions must state audience, message, '
               'story, source quantities, voice requirements, completion evidence and blockers. '
               'Ask only necessary questions with reasons; do not infer permissions. Review each defect '
               'with evidence, severity, owner, correction and expected metric in feedback. Compare versions; '
               'stop at revision/call limits. Never turn unassessed sensory quality into a pass.',
    'employee': 'Read actual previous_results and their revision/source/hash. Follow assignment and '
                'revision_feedback; output content/evidence/uncertainty. Keep unknown facts explicit. '
                'Never claim external generation, listening or viewing without evidence.',
    'feedback': 'Extract natural language into project/domain/target_segment/issue/positive_preference/'
                'proposed_correction/evidence/source/confidence/verification. Preserve original text. '
                'User preference is evidence of preference, not proof that media improved. '
                'Use hypothesis unless independent verification exists. No global generalization.'}


class ExperienceJournal:
    """Uses existing mock Store namespace, locks and version hashes in a dedicated root."""
    def __init__(self, root):
        self.store = Store(root)

    def create(self):
        p = self.store.create('Scoped feedback journal (offline)', opt_in=True)
        p['experiences'] = []
        self.store.save(p)
        return p['id']

    def record(self, journal_id, original_text, extracted, *, provenance, replaces=None):
        safe_text(original_text)
        exact(extracted, EXPERIENCE_FIELDS)
        require(provenance in ('offline_fixture', 'user_structured'), 'live_feedback_blocked')
        for key in EXPERIENCE_FIELDS:
            if key != 'confidence': safe_text(extracted[key], 2000 if key == 'evidence' else 1000)
        require(type(extracted['confidence']) in (int, float) and 0 <= extracted['confidence'] <= 1,
                'invalid_confidence')
        require(extracted['verification'] in ('verified', 'hypothesis'), 'invalid_verification')
        require(extracted['verification'] != 'verified' or provenance == 'user_structured',
                'fixture_cannot_verify')
        with self.store.lock(journal_id):
            p = self.store.load(journal_id)
            old = next((e for e in p['experiences'] if e['id'] == replaces), None)
            require(replaces is None or old and old['active'], 'invalid_replacement')
            if old: old['active'] = False
            entry = dict(id='experience-'+str(len(p['experiences'])+1), version=old['version']+1 if old else 1,
                         original_text=original_text, extraction_source=provenance, active=True,
                         replaces=replaces, created_at=now(), **deepcopy(extracted))
            p['experiences'].append(entry); self.store.save(p)
            return deepcopy(entry)

    def withdraw(self, journal_id, experience_id, reason):
        safe_text(reason)
        with self.store.lock(journal_id):
            p = self.store.load(journal_id)
            entry = next((e for e in p['experiences'] if e['id'] == experience_id), None)
            require(entry is not None and entry['active'], 'experience_not_active')
            entry.update(active=False, withdrawn_at=now(), withdrawal_reason=reason)
            self.store.save(p)

    def select(self, journal_id, *, domain, target_segment):
        p = self.store.load(journal_id)
        return {**select_experiences(p['experiences'], domain=domain, target_segment=target_segment),
                'journal_hash': p['storage_hash']}


def select_experiences(records, *, domain, target_segment):
    """Shared selection policy; journal/transport provenance remains with the caller."""
    selected, excluded = [], []
    for e in records:
        if e['active'] and e['domain'] == domain and e['target_segment'] == target_segment:
            selected.append({**deepcopy(e), 'selection_reason': 'exact domain and audience match',
                             'record_hash': digest(e)})
        else:
            excluded.append(dict(id=e['id'], reason='inactive or domain/audience mismatch'))
    return dict(selected=selected, excluded=excluded)


def bind_context(store, project_id, context):
    """Bind immutable offline planning inputs before any reserved operation."""
    exact(context, ('answers', 'constraints', 'capabilities', 'experiences', 'permissions'))
    require(context['permissions'] == {'external_calls': False, 'cost_limit': 0}, 'offline_permissions_required')
    safe_text(__import__('json').dumps(context, ensure_ascii=False), 24000)
    with store.lock(project_id):
        p = store.load(project_id)
        require(not p['attempts'] and 'quality_context' not in p, 'context_already_bound')
        p['quality_context'] = deepcopy(context);store.save(p)
    return p
