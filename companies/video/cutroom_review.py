"""Local draft lookup and an allowlisted plan-review export."""
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from autonomous_company import CompanyError, digest, exact, parse, require, text

DRAFT_NAME = '.cutroom-revision-draft.json'
PRIVATE_TEXT = re.compile(
    r'https?://[^\s<>]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'
    r'|(?<!\d)(?:\+?82[- ]?)?0?1[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)'
    r'|\b\d{6}[- ]?[1-8]\d{6}\b'
    r'|\b(?:AIza[\w-]{20,}|(?:sk-|gh[pousr]_|github_pat_|eyJ)[\w.-]{12,}|[a-f0-9]{32,}'
    r'|(?:company|qualityprovider)-[a-f0-9]+|gen-lang-client-\d+)\b'
    r'|(?i:\bbearer\s+\S+|\b(?:api[_ -]?key|password|token|secret|credential_binding|signature)\s*[:=]\s*\S+)'
)


def matching_plan(project, version, report_hash):
    plan = next((p for p in project['representative']['plan_versions'] if p['version'] == version), None)
    require(type(version) is int and plan is not None and plan['sha256'] == report_hash
            and digest({k: v for k, v in plan.items() if k != 'sha256'}) == report_hash,
            'stale_representative_report')
    return plan


def revision_draft(root, project):
    flow = project['representative']
    if flow['stage'] != 'awaiting_plan_approval' or not flow['plan_versions']:
        return None
    try:
        path = Path(root)/DRAFT_NAME
        with os.fdopen(
            os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb'
        ) as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'invalid_revision_draft')
            raw = stream.read(16385)
        require(len(raw) <= 16384, 'invalid_revision_draft')
        draft = parse(raw.decode('utf-8'))
        exact(draft, ('project', 'version', 'report_hash', 'feedback', 'checksum'))
        require(draft['project'] == project['id'] and draft['version'] == flow['plan_versions'][-1]['version']
                and draft['checksum'] == digest({k: v for k, v in draft.items() if k != 'checksum'}),
                'invalid_revision_draft')
        matching_plan(project, draft['version'], draft['report_hash'])
        text(draft['feedback'], 2000)
    except (OSError, UnicodeError, CompanyError):
        return None
    return dict(version=draft['version'], report_hash=draft['report_hash'], feedback=draft['feedback'])


def _plain(value):
    value = PRIVATE_TEXT.sub('[제외]', str(value or ''))
    return re.sub(r'([\\`*_{}\[\]<>()#+.!|~-])', r'\\\1', ' '.join(value.split()))


def _source_url(value):
    try:
        url = urlsplit(value)
    except ValueError:
        return None
    if (url.scheme == 'https' and url.netloc == 'www.youtube.com' and url.path == '/watch'
            and not url.fragment and re.fullmatch(r'v=[A-Za-z0-9_-]{11}', url.query)):
        return url.geturl()
    return None


def plan_markdown(project, plan):
    script = plan['script']
    research = plan.get('research', {})
    decision = research.get('manager_decision', {})
    rework = plan.get('rework_plan', {})
    topic_reason = rework.get('feedback_response') or decision.get('selection_reason') or research.get('selection_reason')
    duration_reason = (rework.get('duration_reason') or decision.get('duration_reason')
                       or script.get('estimation_method'))
    lines = [
        f"# 기획·대본 검토 v{plan['version']}", "",
        f"비교 기준 v{plan['version']-1}" if plan['version'] > 1 else "최초 보고서", "",
        "## 목표", "", _plain(project['goal']), "",
        "## 주제와 길이", "",
        f"- 주제 및 근거 · {_plain(plan['topic'])} · {_plain(topic_reason)}",
        f"- 길이 및 근거 · {_plain(script['target_duration'])}초 · {_plain(duration_reason)}",
        f"- 시청자 · {_plain(script.get('target_audience'))}", "",
        "## 조사 출처와 한계", "",
    ]
    public_sources = {}
    for source in research.get('observations', []):
        url = _source_url(source['url'])
        if url:
            public_sources[source.get('id')] = url
            lines.append(f"- [공개 영상]({url}) · {_plain(source['duration_seconds'])}초 · "
                         f"관측 조회수 {_plain(source['view_count'])} · {_plain(source['observed_at'])}")
    if not public_sources:
        lines.append("내보낼 수 있는 공개 영상 출처가 없습니다.")
    elif rework:
        lines.append("이전 보고서의 관측 자료를 재사용했다. 이번 재작업에는 추가 웹 조사가 없다.")
    lines += ["", _plain(research.get('uncertainty')), _plain(plan.get('risks')),
              *(_plain(item) for item in script.get('unknowns', [])), "",
              "## 전체 내레이션", "",
              *(f"> {_plain(line)}<br>" for line in script['transcript'].splitlines()), "",
              "## 장면", ""]
    for beat in script['narrative_beats']:
        caption = '<br>'.join(_plain(line) for line in beat['caption'].splitlines())
        source_url = public_sources.get(beat.get('source_ref'))
        source_link = f" · [참고 영상]({source_url})" if source_url else ''
        lines.append(f"- {_plain(beat['start'])}–{_plain(beat['end'])}초 · {_plain(beat['shot_type'])} · "
                     f"{_plain(beat['screen'])} · 자막 {caption} · {_plain(beat['source_status'])}{source_link}")
    lines += ["", "## 관리자 검토", ""]
    for task in plan.get('task_history', []):
        for review in task['reviews']:
            lines.append(f"- {_plain(task['role'])} / {_plain(review['action'])} · {_plain(review.get('rationale'))}")
    final = plan.get('final_review', {})
    lines += [_plain(final.get('rationale') or plan.get('summary')), ""]
    for check in final.get('checks', []):
        lines.append(f"- {_plain(check['criterion_id'])} / {_plain(check['status'])} · {_plain(check['evidence'])}")
    lines += ["", "## 호출 집계", ""]
    run = plan.get('provider_run', {})
    counts = plan.get('call_counts')
    if counts is None and run:
        counts = dict(gemini=len(run['attempts']), youtube=len(run.get('web_attempts', [])))
    if counts is None:
        lines.append("이 보고서에 호출 집계가 저장되어 있지 않습니다.")
    else:
        lines.append(f"- Gemini {counts['gemini']}회 · YouTube {counts['youtube']}회")
    return '\n'.join(lines) + '\n'
