"""Local representative approvals over existing project storage, quality work, and rendering."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from autonomous_company import CompanyError, Store, digest, exact, now, parse, require, text
from local_artifacts import run_command
from production_video import render, validate
from quality_feedback import bind_context, select_experiences
from script_quality import SCRIPT_CONTRACT, validate_script_editor


def _file_hash(path):
    require(path.is_file() and not path.is_symlink(), 'representative_artifact_missing')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _report(body, versions):
    value = dict(version=len(versions) + 1, reported_at=now(), **deepcopy(body))
    return {**value, 'sha256': digest(value)}


def _match(versions, version, sha256):
    require(bool(versions), 'representative_report_missing')
    report = versions[-1]
    require(type(version) is int and report['version'] == version and report['sha256'] == sha256,
            'stale_representative_report')
    return report


class RepresentativeVideoWorkflow:
    """Python entry point. The two decisions are local business approvals only."""

    def __init__(self, store):
        require(type(store) is Store, 'representative_local_store_required')
        self.store = store

    def create(self, goal, *, audience='미정', constraints=None, experiences=(), creation_key=None):
        constraints = {} if constraints is None else constraints
        text(audience, 300)
        require(isinstance(constraints, dict), 'invalid_representative_constraints')
        # This entry point uses the existing offline renderer and does not accept external tool grants.
        require(not {'external_calls', 'publish', 'budget', 'consent'}.intersection(constraints),
                'representative_external_scope_unavailable')
        project = self.store.create(goal, opt_in=True)
        with self.store.lock(project['id']):
            project['representative'] = dict(stage='goal_submitted', audience=audience,
                constraints=deepcopy(constraints), plan_versions=[], video_versions=[],
                decisions=[], planning_jobs=[], render_attempts=[], events=[], experiences=[],
                scoped_experiences=select_experiences(experiences, domain='video', target_segment=audience))
            if creation_key is not None:
                project['representative']['creation_key'] = creation_key
            self._transition(project, 'goal_submitted')
        return project['id']

    def _transition(self, project, stage):
        flow = project['representative']
        flow['stage'] = stage
        flow['events'].append(dict(stage=stage, at=now()))
        self.store.save(project)

    def start_planning(self, project_id):
        """Create a standard VideoQualityCompany job with the exact prior feedback in its context."""
        with self.store.lock(project_id):
            p = self.store.load(project_id)
            flow = p['representative']
            if flow['stage'] == 'research_planning':
                require(bool(flow['planning_jobs']), 'mission_provider_result_required')
                return flow['planning_jobs'][-1]
            require(flow['stage'] in ('goal_submitted', 'plan_revision'), 'representative_stage_mismatch')
            job = self.store.create(p['goal'], opt_in=True)
            feedback = flow['decisions'][-1] if flow['decisions'] else None
            prior = flow['plan_versions'][-1] if flow['plan_versions'] else None
            bind_context(self.store, job['id'], dict(
                answers=dict(audience=flow['audience'], representative_feedback=feedback,
                    previous_plan=prior and dict(version=prior['version'], sha256=prior['sha256'],
                        script=prior['script'], summary=prior['summary'])),
                constraints=flow['constraints'], capabilities={'script_contract': SCRIPT_CONTRACT},
                experiences=flow['scoped_experiences'], permissions=dict(external_calls=False, cost_limit=0)))
            flow['planning_jobs'].append(job['id'])
            self._transition(p, 'research_planning')
            return job['id']

    def stage_mission_one(self, project_id):
        from mission_game_evidence import DURATION_RANGE, GAME_EVIDENCE, GAME_GOAL, GAME_SCOPE
        from video_mission_one import MAX_CALLS, SCOPE, MissionOneStore
        with self.store.lock(project_id):
            p = self.store.load(project_id)
            flow = p['representative']
            if flow.get('mission_one_job') and flow['stage'] == 'research_planning':
                return flow['mission_one_job']
            require(flow['stage'] == 'goal_submitted' and not flow.get('mission_one_job'),
                    'representative_stage_mismatch')
            game = p['goal'] == GAME_GOAL
            constraints = deepcopy(flow['constraints'])
            answers = dict(audience=flow['audience'], representative_project=project_id)
            capabilities = dict(script_contract=SCRIPT_CONTRACT, mission=SCOPE)
            if game:
                require('duration_seconds' not in constraints, 'mission_game_duration_is_manager_decision')
                constraints.update(duration_range_seconds=list(DURATION_RANGE), aspect='9:16', language='한국어',
                                   platform='YouTube Shorts')
                answers['public_evidence'] = deepcopy(GAME_EVIDENCE)
                capabilities['editorial_scope'] = GAME_SCOPE
            else:
                require(constraints.get('duration_seconds', 60) == 60, 'mission_duration_requires_60')
                constraints['duration_seconds'] = 60
            store = MissionOneStore(self.store.root/'mission_one_provider')
            job = store.create(p['goal'], inputs=dict(domain='video', target_segment=flow['audience'],
                answers=answers, constraints=constraints, capabilities=capabilities,
                experiences=[], feedback_text=''), max_calls=MAX_CALLS, max_total_revisions=1)
            flow['mission_one_job'] = job['id']
            self._transition(p, 'research_planning')
            return job['id']

    def report_plan(self, project_id, *, summary=None, sources=None, risks=None, changes=None,
                    render_spec=None, provider_store=None, allow_fixture=False):
        with self.store.lock(project_id):
            p = self.store.load(project_id)
            flow = p['representative']
            mission = provider_store is not None
            if mission:
                from video_mission_one import MissionOneStore, checked_result, provider_view
                require(type(provider_store) is MissionOneStore and
                        provider_store.root == self.store.root/'mission_one_provider'
                        and flow.get('mission_one_job'), 'mission_scope_mismatch')
                job = provider_store.result(flow['mission_one_job'])
                provider_store.check_scope(job)
                require(job['goal'] == p['goal'] and job['quality_inputs']['answers']['representative_project'] == project_id,
                        'mission_scope_mismatch')
                require(render_spec is None, 'mission_media_out_of_scope')
                research, provenance = checked_result(job, allow_fixture=allow_fixture)
                if flow['plan_versions'] and flow['plan_versions'][-1]['internal_job'] == job['id']:
                    return deepcopy(flow['plan_versions'][-1])
                summary = job['final']['content']
                sources = []
                if research.get('manager_decision'):
                    evidence = job['quality_inputs']['answers']['public_evidence']
                    ids = {candidate['player_evidence_id'] for candidate in research['candidates']}
                    ids.update(research['manager_decision']['duration_evidence_ids'])
                    for key in sorted(ids):
                        source = evidence[key]
                        sources.append(dict(url=source['url'], observed_at=source['observed_at'],
                            claim=source['claim']+' '+source['limits'], rights='수치 참고. 영상 소스 권리 미확인.'))
                risks = research['uncertainty'] + ' · 한국 게임 쇼츠 성과 및 시각 소스 권리 미검증.'
                changes = '내부 검토 후 대표에게 제출한 첫 기획안.'
                mission_details = dict(research=research, provider_run=provider_view(job),
                                       manager_plan=job['plan'], final_review=job['final'],
                                       task_history=[dict(role=t['role'], versions=t['versions'], reviews=t['reviews'])
                                                     for t in job['assignments']])
            else:
                require(not flow.get('mission_one_job') and flow['planning_jobs'], 'mission_provider_result_required')
                job = self.store.result(flow['planning_jobs'][-1])
                require(job.get('reason_code') in ('manager_final_stopped', 'external_clip_pending', 'needs_user_review')
                        and job['assignments'] and all(t['state'] == 'accepted_by_ai_manager' for t in job['assignments']),
                        'representative_internal_review_incomplete')
                provenance = 'offline_mock_staff'
                mission_details = {}
            require(flow['stage'] == 'research_planning', 'representative_stage_mismatch')
            for value in (summary, risks, changes):
                text(value, 3000)
            require(isinstance(sources, list) and len(sources) <= 20, 'invalid_representative_sources')
            for source in sources:
                exact(source, ('url', 'observed_at', 'claim', 'rights'))
                for value in source.values():
                    text(value, 1200)
                parsed = urlsplit(source['url'])
                require(parsed.scheme == 'https' and parsed.hostname and not parsed.username
                        and not parsed.password, 'invalid_representative_source_url')
            writer = next(t for t in job['assignments'] if t['role'] == 'writer')
            editor = next(t for t in job['assignments'] if t['role'] == 'editor')
            writer_result = writer['versions'][-1]
            script = parse(writer_result['content'])
            editor_result = editor['versions'][-1]
            validate_script_editor(parse(editor_result['content']), [writer_result])
            if not mission:
                duration = validate(render_spec)
                constraints = flow['constraints']
                aspect = constraints.get('aspect', '16:9')
                require(aspect == '16:9' and constraints.get('duration_seconds', duration) == duration
                        and (constraints.get('audio_required') is not True or render_spec['audio_mode'] != 'none'),
                        'representative_render_constraints_unsupported')
                beats = script['narrative_beats']
                scenes = render_spec['scenes']
                require(duration == script['target_duration'] and len(beats) == len(scenes)
                        and all(scene['narration'] == beat['narration'] and scene['subtitle'] == beat['caption']
                                and scene['seconds'] == beat['end'] - beat['start'] for scene, beat in zip(scenes, beats)),
                        'representative_render_script_mismatch')
            report = _report(dict(summary=summary, sources=sources, risks=risks, changes=changes,
                topic=script['topic']['title'], script=script, render_spec=render_spec, cost_limit_usd=0,
                internal_job=job['id'], internal_state=job['reason_code'], writer_sha256=digest(writer_result),
                editor_sha256=digest(editor_result), internal_reviews=writer['reviews'],
                previous_plan_sha256=flow['plan_versions'][-1]['sha256'] if flow['plan_versions'] else None,
                provenance=provenance, **mission_details), flow['plan_versions'])
            flow['plan_versions'].append(report)
            self._transition(p, 'awaiting_plan_approval')
            return deepcopy(report)

    def decide(self, project_id, stage, *, version, sha256, action, feedback='', changes_plan=False,
               provenance='user_structured'):
        require(stage in ('plan', 'video') and action in ('approve', 'request_revision'),
                'invalid_representative_decision')
        require(type(changes_plan) is bool and (not changes_plan or (stage, action) == ('video', 'request_revision')),
                'invalid_representative_revision_scope')
        require(provenance in ('user_structured', 'offline_fixture'), 'invalid_representative_provenance')
        text(feedback, 2000, empty=action == 'approve')
        with self.store.lock(project_id):
            p = self.store.load(project_id)
            flow = p['representative']
            require(flow['stage'] == f'awaiting_{stage}_approval', 'representative_stage_mismatch')
            report = _match(flow[f'{stage}_versions'], version, sha256)
            if stage == 'video':
                self._verify_video(p, report)
            event = dict(stage=stage, action=action, version=version, sha256=sha256,
                         feedback=feedback, changes_plan=changes_plan, provenance=provenance, at=now())
            flow['decisions'].append(event)
            if action == 'request_revision':
                next_stage = 'plan_revision' if stage == 'plan' or changes_plan else 'video_revision'
            elif stage == 'plan':
                next_stage = 'production'
            else:
                flow['final_video'] = deepcopy(report)
                flow['experiences'].append(dict(id='experience-1', domain='video', target_segment=flow['audience'],
                    active=True, source='representative_workflow', extraction_source=provenance,
                    verification='verified' if provenance == 'user_structured' else 'hypothesis', original_text=feedback, issue='',
                    positive_preference='대표가 해당 영상 버전을 승인', proposed_correction='',
                    evidence=json.dumps(dict(final_approval=event,
                        feedback_history=[d for d in flow['decisions'] if d['feedback']],
                        artifact_sha256=report['artifact_sha256']), ensure_ascii=False)))
                next_stage = 'completed'
            self._transition(p, next_stage)
            return deepcopy(event)

    def _approved_plan(self, flow, version, sha256):
        plan = _match(flow['plan_versions'], version, sha256)
        latest = next((d for d in reversed(flow['decisions']) if d['stage'] == 'plan'), None)
        require(latest and latest['action'] == 'approve' and latest['sha256'] == sha256,
                'representative_plan_approval_required')
        return plan

    def produce(self, project_id, *, version, sha256, changes, palette=None, cameras=None):
        """Render the approved narration/captions; a video revision may adjust visual styling."""
        text(changes, 2000)
        with self.store.lock(project_id):
            p = self.store.load(project_id)
            flow = p['representative']
            require(flow['stage'] in ('production', 'video_revision'), 'representative_stage_mismatch')
            plan = self._approved_plan(flow, version, sha256)
            require(not any(a['status'] == 'reserved' for a in flow['render_attempts']),
                    'representative_render_uncertain')
            require(plan['render_spec'] is not None, 'representative_render_spec_pending')
            spec = deepcopy(plan['render_spec'])
            if palette is not None or cameras is not None:
                require(flow['stage'] == 'video_revision', 'representative_unapproved_render_change')
            if palette is not None:
                spec['palette'] = deepcopy(palette)
            if cameras is not None:
                require(isinstance(cameras, list) and len(cameras) == len(spec['scenes']),
                        'representative_camera_count')
                for scene, camera in zip(spec['scenes'], cameras):
                    scene['camera'] = camera
            validate(spec)
            number = len(flow['render_attempts']) + 1
            relative = Path('artifacts')/project_id/f'render-{number}'
            folder = self.store.root/relative
            require(folder.resolve().is_relative_to(self.store.root.resolve())
                    and not any(path.is_symlink() for path in (folder, folder.parent, folder.parent.parent)),
                    'representative_artifact_path')
            attempt = dict(number=number, status='reserved', at=now(), plan_sha256=sha256, spec_sha256=digest(spec))
            flow['render_attempts'].append(attempt)
            self.store.save(p)
            try:
                folder.mkdir(parents=True, exist_ok=False)
                receipt = render(spec, folder)
                require(receipt['input_hash'] == attempt['spec_sha256'], 'representative_render_receipt_mismatch')
                feedback = flow['decisions'][-1] if flow['stage'] == 'video_revision' else None
                report = _report(dict(plan_version=version, plan_sha256=sha256, changes=changes,
                    revision_feedback=feedback, previous_video_sha256=flow['video_versions'][-1]['sha256'] if flow['video_versions'] else None,
                    artifact=str(relative/'video.mp4'), artifact_sha256=receipt['sha256'],
                    receipt_sha256=_file_hash(folder/'receipt.json'), render_receipt=receipt,
                    qa=dict(full_decode=True, perceptual_quality='unassessed', subtitles='scene_level_only'),
                    cost_usd=0, publish_authorized=False), flow['video_versions'])
                self._verify_video(p, report)
            except (CompanyError, OSError) as exc:
                attempt.update(status='failed', reason=exc.code if isinstance(exc, CompanyError) else 'local_io_failed')
                self.store.save(p)
                raise
            attempt['status'] = 'completed'
            flow['video_versions'].append(report)
            self._transition(p, 'awaiting_video_approval')
            return deepcopy(report)

    def _verify_video(self, project, report):
        path = self.store.root/report['artifact']
        base = self.store.root/'artifacts'/project['id']
        require(path.resolve().is_relative_to(base.resolve())
                and not any(p.is_symlink() for p in (path.parent, base, base.parent)),
                'representative_artifact_path')
        require(_file_hash(path) == report['artifact_sha256']
                and _file_hash(path.parent/'receipt.json') == report['receipt_sha256'],
                'representative_artifact_changed')
        receipt = report['render_receipt']
        for item in receipt['source_licenses']:
            require(_file_hash(path.parent/item['file']) == item['sha256'], 'representative_artifact_changed')
        for item in receipt['review_material']:
            require(_file_hash(path.parent/item['keyframe']) == item['keyframe_sha256'],
                    'representative_artifact_changed')
        probe = json.loads(run_command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json',
                                        str(path)], stage='ffprobe_final'))
        streams = probe['streams']
        video = [s for s in streams if s['codec_type'] == 'video']
        audio = [s for s in streams if s['codec_type'] == 'audio']
        require(len(video) == 1 and video[0]['codec_name'] == 'h264'
                and (video[0]['width'], video[0]['height']) == (receipt['width'], receipt['height'])
                and len(audio) == int(receipt['audio']) and all(s['codec_name'] == 'aac' for s in audio)
                and abs(float(probe['format']['duration']) - receipt['duration_seconds']) < .05,
                'representative_media_mismatch')
