"""Local HTTP adapter for the representative video workflow."""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit

from autonomous_company import CompanyError, Store, exact, require
from representative_workflow import RepresentativeVideoWorkflow, _file_hash

ASSETS = Path(__file__).with_name('studio')
ROOT = Path('data/video_representative_workflow')
PROJECT = r'company-[0-9a-f]{32}'
STATIC = {'/': ('index.html', 'text/html'), '/studio.css': ('studio.css', 'text/css'),
          '/studio.js': ('studio.js', 'text/javascript')}
ERRORS = {
    'representative_stage_mismatch': '현재 단계에서는 실행할 수 없습니다. 최신 상태를 확인해 주세요.',
    'stale_representative_report': '검토한 버전이 최신 보고서와 다릅니다. 새로고침 후 확인해 주세요.',
    'representative_artifact_changed': '파일 또는 검증 기록의 해시가 달라 작업이 차단됐습니다.',
    'representative_artifact_missing': '영상이나 검증 파일이 없습니다.',
    'representative_render_uncertain': '이전 로컬 렌더의 결과가 미확정입니다.',
    'representative_plan_approval_required': '기획·대본에 대한 대표 승인이 필요합니다.',
    'project_busy': '이 프로젝트에서 작업 중입니다. 잠시 후 최신 상태를 확인해 주세요.',
    'invalid_text': '필수 입력과 글자 수를 확인해 주세요.',
    'invalid_fields': '입력 형식을 확인해 주세요.',
    'readonly_project': '기존 검증 사례는 읽기 전용입니다.',
    'invalid_request': '요청 형식이 올바르지 않습니다.',
    'invalid_creation_key': '프로젝트 생성 요청을 확인해 주세요.',
    'local_tool_failed': '로컬 렌더 도구 실행에 실패했습니다. 제작 시도 기록을 확인해 주세요.',
}


def byte_range(header, size):
    if header is None:
        return 0, size - 1
    match = re.fullmatch(r'bytes=(\d{0,18})-(\d{0,18})', header)
    if not match or not any(match.groups()):
        raise ValueError
    first, last = match.groups()
    if not first and int(last) == 0:
        raise ValueError
    start = int(first) if first else max(0, size - int(last))
    end = min(size - 1, int(last)) if first and last else size - 1
    if start > end:
        raise ValueError
    return start, end


class Studio:
    def __init__(self, writable, references=()):
        self.stores = {'workspace': Store(writable),
                       **{f'reference-{index}': Store(root) for index, root in enumerate(references)}}
        require(len({store.root for store in self.stores.values()}) == len(self.stores), 'studio_store_overlap')
        self.workflow = RepresentativeVideoWorkflow(self.stores['workspace'])
        self.token = secrets.token_urlsafe(32)
        self.creation_lock = threading.Lock()

    def projects(self, key):
        store = self.stores[key]
        for path in store.root.glob('company-*.json'):
            if re.fullmatch(PROJECT, path.stem):
                yield store.load(path.stem)

    def project(self, key, pid):
        if key not in self.stores or not re.fullmatch(PROJECT, pid):
            raise FileNotFoundError
        project = self.stores[key].load(pid)
        if 'representative' not in project:
            raise FileNotFoundError
        return project

    def card(self, key, p):
        flow = p['representative']
        video = flow['video_versions'][-1] if flow['video_versions'] else None
        prefix = f'/media/{key}/{p["id"]}'
        return dict(id=p['id'], store=key, goal=p['goal'], updated_at=p['updated_at'], stage=flow['stage'],
                    readonly=key != 'workspace', simulation=p['simulation'], audience=flow['audience'],
                    thumbnail=f'{prefix}/{video["version"]}/thumbnail' if video else None,
                    plans=len(flow['plan_versions']), videos=len(flow['video_versions']),
                    render_status=flow['render_attempts'][-1]['status'] if flow['render_attempts'] else None)

    def dashboard(self):
        cards, deferred = [], []
        for key in self.stores:
            for p in self.projects(key):
                if 'representative' in p:
                    cards.append(self.card(key, p))
                if 'topic_reference_disposition' in p:
                    deferred.append(p['topic_reference_disposition'])
        return dict(projects=sorted(cards, key=lambda p: p['updated_at'], reverse=True),
                    deferred=deferred, token=self.token)

    def detail(self, key, pid):
        p = self.project(key, pid)
        flow = deepcopy(p['representative'])
        flow.pop('scoped_experiences', None)
        flow.pop('creation_key', None)
        for video in flow['video_versions']:
            prefix = f'/media/{key}/{pid}/{video["version"]}'
            video.update(url=prefix+'/video', thumbnail=prefix+'/thumbnail')
            video.pop('artifact', None)
        flow.pop('final_video', None)
        store = self.stores[key]
        jobs = [store.load(job_id) for job_id in flow['planning_jobs']]
        return {**self.card(key, p), 'flow': flow,
                'jobs': [dict(id=j['id'], status=j['status'], reason=j.get('reason_code'),
                              assignments=[dict(role=t['role'], state=t['state'], versions=len(t['versions']))
                                           for t in j['assignments']]) for j in jobs]}

    def create(self, body):
        exact(body, ('goal', 'audience', 'language', 'platform', 'duration', 'notes', 'key'))
        require(isinstance(body['key'], str) and re.fullmatch(r'[a-f0-9-]{36}', body['key']),
                'invalid_creation_key')
        for field in ('goal', 'audience', 'language', 'platform', 'notes'):
            require(isinstance(body[field], str), 'invalid_request')
        require(all(len(body[k]) <= 300 for k in ('audience', 'language', 'platform')) and
                len(body['notes']) <= 2000 and
                (body['duration'] is None or type(body['duration']) is int and 1 <= body['duration'] <= 120),
                'invalid_request')
        constraints = {k: body[k].strip() for k in ('language', 'platform', 'notes') if body[k].strip()}
        if body['duration'] is not None:
            constraints['duration_seconds'] = body['duration']
        with self.creation_lock:
            for p in self.projects('workspace'):
                if p.get('representative', {}).get('creation_key') == body['key']:
                    return {'id': p['id']}
            pid = self.workflow.create(body['goal'].strip(), audience=body['audience'].strip() or '미정',
                                       constraints=constraints, creation_key=body['key'])
        return {'id': pid}

    def action(self, key, pid, name, body):
        self.project(key, pid)
        require(key == 'workspace', 'readonly_project')
        if name == 'planning':
            exact(body, ())
            self.workflow.start_planning(pid)
        elif name == 'decide':
            exact(body, ('stage', 'version', 'sha256', 'action', 'feedback', 'changes_plan'))
            self.workflow.decide(pid, **body)
        elif name == 'produce':
            exact(body, ('version', 'sha256', 'changes', 'camera'))
            require(body['camera'] in (None, 'hold', 'push_in', 'pan_right'), 'invalid_request')
            p = self.project(key, pid)
            current = p['representative']['plan_versions']
            cameras = [body['camera']] * len(current[-1]['render_spec']['scenes']) if body['camera'] and current else None
            self.workflow.produce(pid, version=body['version'], sha256=body['sha256'],
                                  changes=body['changes'], cameras=cameras)
        else:
            raise FileNotFoundError
        return self.detail(key, pid)

    def media(self, key, pid, version, kind):
        p = self.project(key, pid)
        video = next((v for v in p['representative']['video_versions'] if v['version'] == version), None)
        if not video:
            raise FileNotFoundError
        root = self.stores[key].root
        path = root/video['artifact']
        base = root/'artifacts'/pid
        require(path.name == 'video.mp4' and path.parent.parent == base and
                re.fullmatch(r'render-[1-9]\d*', path.parent.name) and
                not any(item.is_symlink() for item in (base.parent, base, path.parent, path)),
                'representative_artifact_path')
        if kind == 'video':
            expected, mime = video['artifact_sha256'], 'video/mp4'
        else:
            frames = video['render_receipt']['review_material']
            if not frames:
                raise FileNotFoundError
            frame = frames[len(frames)//2]
            require(re.fullmatch(r'keyframe-\d{2}\.png', frame['keyframe']), 'representative_artifact_path')
            path = path.with_name(frame['keyframe'])
            expected, mime = frame['keyframe_sha256'], 'image/png'
        require(_file_hash(path) == expected, 'representative_artifact_changed')
        return path, mime


def make_server(host, port, studio):
    class Handler(BaseHTTPRequestHandler):
        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; media-src 'self'; object-src 'none'; frame-ancestors 'self'; base-uri 'none'")
            super().end_headers()

        def send_bytes(self, status, payload, mime):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(payload)

        def send_json(self, status, value):
            self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

        def file(self, path, mime):
            size = path.stat().st_size
            requested = self.headers.get('Range')
            try:
                start, end = byte_range(requested, size)
            except ValueError:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            self.send_response(206 if requested else 200)
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('Cache-Control', 'private, no-cache')
            self.end_headers()
            if self.command == 'HEAD':
                return
            with path.open('rb') as stream:
                stream.seek(start)
                left = end-start+1
                while left:
                    chunk = stream.read(min(left, 65536))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def dispatch(self):
            path = urlsplit(self.path).path
            if self.command in ('GET', 'HEAD'):
                if path in STATIC:
                    name, mime = STATIC[path]
                    return self.send_bytes(200, (ASSETS/name).read_bytes(), mime+'; charset=utf-8')
                if path == '/api/studio':
                    return self.send_json(200, studio.dashboard())
                if match := re.fullmatch(rf'/api/project/([\w-]+)/({PROJECT})', path):
                    return self.send_json(200, studio.detail(*match.groups()))
                if match := re.fullmatch(rf'/media/([\w-]+)/({PROJECT})/([1-9][0-9]{{0,5}})/(video|thumbnail)', path):
                    key, pid, version, kind = match.groups()
                    return self.file(*studio.media(key, pid, int(version), kind))
            elif self.command == 'POST':
                if self.headers.get('Sec-Fetch-Site') == 'cross-site' or not secrets.compare_digest(
                    self.headers.get('X-Studio-Token', '').encode('latin-1'), studio.token.encode('ascii')
                ):
                    return self.send_json(403, dict(error='이 화면에서 새로고침 후 다시 시도해 주세요.'))
                length = self.headers.get('Content-Length', '')
                require(length.isdecimal() and 0 < int(length) <= 20000 and
                        self.headers.get_content_type() == 'application/json', 'invalid_request')
                body = json.loads(self.rfile.read(int(length)))
                if path == '/api/project':
                    return self.send_json(201, studio.create(body))
                if match := re.fullmatch(rf'/api/project/([\w-]+)/({PROJECT})/(planning|decide|produce)', path):
                    return self.send_json(200, studio.action(*match.groups(), body))
            raise FileNotFoundError

        def handle_request(self):
            try:
                self.dispatch()
            except FileNotFoundError:
                self.send_json(404, dict(error='프로젝트 또는 파일을 찾을 수 없습니다.'))
            except CompanyError as exc:
                status = 403 if exc.code == 'readonly_project' else 409
                self.send_json(status, dict(code=exc.code, error=ERRORS.get(exc.code, '요청을 완료할 수 없습니다. 현재 상태와 입력을 확인해 주세요.')))
            except (ValueError, UnicodeError):
                self.send_json(400, dict(error='요청 형식이 올바르지 않습니다.'))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except OSError:
                self.send_json(500, dict(error='로컬 파일 처리에 실패했습니다.'))

        do_GET = do_HEAD = do_POST = handle_request

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--root', type=Path, default=ROOT/'studio')
    parser.add_argument('--reference', type=Path, action='append')
    args = parser.parse_args()
    references = args.reference if args.reference is not None else [ROOT/'20261111_validation', ROOT/'20261111_reference']
    with make_server(args.host, args.port, Studio(args.root, references)) as server:
        print(f'Studio · http://{args.host}:{server.server_port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
