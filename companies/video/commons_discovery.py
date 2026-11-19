"""Bounded Wikimedia Commons file discovery and explicit local rights review."""
from datetime import datetime
from html.parser import HTMLParser
import http.client
import re
from time import monotonic
from urllib.parse import quote, unquote, urlencode, urlsplit

from autonomous_company import CompanyError, digest, exact, now, parse, require
from autonomous_gemini35 import ENDPOINT, MODEL
from goal_dialogue import safe_text
from mission_production import (ProductionManager, approved_manager_result, canonical_bytes, draft_id,
                                production_keys)
from official_media import MAX_BYTES as MAX_MEDIA_BYTES, _PinnedHTTPS, _global_addresses
from owner_operating_policy import OwnerOperatingPolicy
from production_operating import delegated_call, run_worker, unit
from role_json_schema import S, arr, enum, obj
from tts_job import private_write

HOST='commons.wikimedia.org'
API=f'https://{HOST}/w/api.php'
USER_AGENT='AICompanyOS-Cutroom/1.0 (https://github.com/smartaiboom/ai-company-os)'
LIMIT=5
MAX_BYTES=131072
FORMATS={'.mp4':'video/mp4','.webm':'video/webm','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}
MAX_IMAGE_BYTES=8*1024*1024
LICENSE=re.compile(r'https://creativecommons\.org/(licenses/(by|by-sa)/(2\.0|2\.5|3\.0|4\.0)|publicdomain/zero/1\.0)/?')
FALLBACK_SCHEMA=obj(options=arr(obj(scene_id=S,route=enum('illustrative_footage','licensed_still_motion',
    'authorized_capture','verify_generation','hold'),suggestion=S,rights_needed=S)))
FALLBACK_SYSTEM=(
    '승인 장면과 검색 결과 상태를 바탕으로 한국어 JSON으로 장면별 대안 한 가지를 제안하세요. '
    '권리를 확인한 비게임 설명 영상, 라이선스 확인 정지 이미지에 모션 적용, 권한 있는 직접 캡처, 생성 도구 검증 또는 보류만 허용됩니다. '
    '게임 플레이를 일반 B-roll로 위장하지 말고 대본·음성·타임라인 변경이나 실행을 요청하지 마세요. '
    '사용권과 실제 가능성은 미확인입니다. 다운로드 URL을 만들어 내지 마세요.'
)


def original_url(value, mime=None):
    require(type(value) is str and len(value)<=1500 and value.isascii(),'commons_unsafe_file_url')
    try:
        url=urlsplit(value)
    except ValueError:
        raise CompanyError('commons_unsafe_file_url') from None
    match=re.fullmatch(r'/wikipedia/commons/[0-9a-f]/[0-9a-f]{2}/([^/]+)',url.path)
    require(url.scheme=='https' and url.netloc=='upload.wikimedia.org' and url.geturl()==value
            and not url.query and not url.fragment and match is not None,'commons_unsafe_file_url')
    name=unquote(match[1],errors='strict')
    require(not any(c in name for c in '/\\%?#') and all(ord(c)>=32 and ord(c)!=127 for c in name)
            and not name.startswith('.') and not name.endswith('.'),'commons_unsafe_file_url')
    extension='.'+name.lower().rsplit('.',1)[-1]
    require(extension in FORMATS and (mime is None or FORMATS[extension]==mime),'commons_unsafe_file_url')
    return url


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.ignored=0

    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):
            self.ignored+=1

    def handle_endtag(self,tag):
        if tag in ('script','style') and self.ignored:
            self.ignored-=1

    def handle_data(self,data):
        if not self.ignored:
            self.parts.append(data)


def plain(value, limit=320):
    if not isinstance(value,str) or len(value)>8000:
        return ''
    reader=PlainText()
    try:
        reader.feed(value)
        reader.close()
    except (AssertionError,ValueError):
        return ''
    text=' '.join(' '.join(reader.parts).split())[:limit]
    if not text:
        return ''
    try:
        safe_text(text,limit)
    except CompanyError:
        return ''
    return text


def queries(plan, clips):
    existing={c['scene_id'] for c in clips}
    terms=[]
    for row in plan['scenes']:
        if row['scene_id'] in existing:
            continue
        # Discard reference IDs and directive prefixes. The signed review exposes the exact search text.
        phrase=re.split(r'\b(?:showing|showcasing|depicting|displaying|featuring)\b',row['request'],maxsplit=1,flags=re.I)[-1]
        phrase=re.sub(r'https?://\S+|\b[a-z][0-9]+:[\w-]+',' ',phrase)
        words=re.findall(r"[^\W_]+(?:['’][^\W_]+)?",phrase,re.UNICODE)
        stop={'use','operator','clip','show','showing','the','and','with','for','of','a','an'}
        phrase=' '.join(w for w in words if w.lower() not in stop and len(w)<=40)[:100].strip()
        if phrase:
            safe_text(phrase,100)
            previous=next((item for item in terms if item['query'].casefold()==phrase.casefold()),None)
            if previous:
                previous['scene_ids'].append(row['scene_id'])
            else:
                terms.append(dict(scene_id=row['scene_id'],scene_ids=[row['scene_id']],query=phrase))
    return terms[:6]


def adaptive_queries(plan, clips, previous):
    existing={clip['scene_id'] for clip in clips}
    choices={row['scene_id']:row['route'] for row in previous.get('fallback',{}).get('options',[])}
    old={row['query'].casefold() for row in previous.get('proposal',{}).get('queries',[])}
    rows=[]
    for shot in plan['scenes']:
        scene=shot['scene_id']
        if scene in existing:
            continue
        phrase=re.split(r'\b(?:showing|showcasing|depicting|displaying|featuring)\b',shot['request'],maxsplit=1,flags=re.I)[-1]
        phrase=re.sub(r'https?://\S+|\b[a-z][0-9]+:[\w-]+',' ',phrase).strip()
        proper=re.match(r"[A-Z][\w'’]*(?:(?: (?:of|the|and))? [A-Z][\w'’]*){1,5}",phrase)
        subject=proper[0] if proper else ''
        words=re.findall(r"[^\W_]+(?:['’][^\W_]+)?",phrase,re.UNICODE)
        stop={'a','and','the','use','operator','clip','with','show','of','montage','trending'}
        terms=[w for w in words if w.casefold() not in stop and len(w)<=30]
        short=(subject or ' '.join(terms[:3]))[:80].strip()
        alias=(subject.rsplit(' ',1)[0] if len(subject.split())>=4 else
               subject or ' '.join(terms[:2]))[:80].strip()
        if not short:
            continue
        first='image' if choices.get(scene)=='licensed_still_motion' else 'video'
        for wave,(query,media) in enumerate(((short,first),(alias or short,'video' if first=='image' else 'image'))):
            if media=='video' and query.casefold() in old:
                query=alias
            if not query or (media=='video' and query.casefold() in old):
                continue
            safe_text(query,80)
            prior=next((row for row in rows if row['query'].casefold()==query.casefold() and row['media']==media),None)
            if prior:
                prior['scene_ids'].append(scene)
            else:
                rows.append(dict(scene_id=scene,scene_ids=[scene],query=query,media=media,wave=wave,
                                 subject=subject[:80],topic_terms=' '.join(terms[:3]),alternate_terms=alias,
                                 unit_id=f'{scene}-{media}'))
    return sorted(rows,key=lambda row:row['wave'])[:12]


def request_path(phrase,media='video'):
    require(media in ('video','image'),'commons_response_failed')
    filetype='bitmap' if media=='image' else 'video'
    return '/w/api.php?'+urlencode(dict(action='query',generator='search',gsrnamespace=6,
        gsrsearch=f'{phrase} filetype:{filetype}',gsrlimit=LIMIT,prop='imageinfo',iilimit=1,
        iiprop='url|mime|mediatype|size|sha1|extmetadata',iiextmetadatafilter=
        'LicenseShortName|LicenseUrl|Artist|Credit|Attribution|AttributionRequired|Restrictions',
        format='json',formatversion=2,maxlag=5))


def search_commons(path):
    require(path.startswith('/w/api.php?') and path.isascii() and len(path)<=4096,'commons_response_failed')
    deadline=monotonic()+25
    family,address=_global_addresses(HOST,deadline)
    connection=_PinnedHTTPS(HOST,family,address,deadline)
    try:
        connection.request('GET',path,headers={'Accept':'application/json','Accept-Encoding':'identity',
                                              'User-Agent':USER_AGENT})
        with connection.getresponse() as response:
            require(response.status==200 and response.headers.get_content_type()=='application/json'
                and response.getheader('Content-Encoding','identity').lower()=='identity','commons_response_failed')
            # The parser's bound is also the transport body bound.
            raw=response.read(MAX_BYTES+1)
            require(0<len(raw)<=MAX_BYTES and monotonic()<=deadline,'commons_response_limit')
            data=parse(raw.decode('utf-8'))
            require(isinstance(data,dict) and 'error' not in data,'commons_response_failed')
            return data
    except (UnicodeError,OSError,http.client.HTTPException):
        raise CompanyError('commons_response_failed') from None
    finally:
        connection.close()
        connection.cancel_timer()


def unmatched_scenes(scenes, compatible):
    """Find a distinct candidate assignment, rather than counting duplicates per scene."""
    assigned={}
    def seat(scene,seen):
        for candidate in compatible(scene):
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate not in assigned or seat(assigned[candidate],seen):
                assigned[candidate]=scene
                return True
        return False
    return [scene for scene in scenes if not seat(scene,set())]


def candidates(data, scene, media='video'):
    query=data.get('query',{})
    require(isinstance(query,dict),'commons_response_failed')
    pages=query.get('pages',[])
    require(isinstance(pages,list) and len(pages)<=LIMIT,'commons_response_limit')
    found=[]
    rejected=0
    for page in pages:
        if not (isinstance(page,dict) and page.get('ns')==6 and type(page.get('pageid')) is int
                and 0<page['pageid']<10**12 and isinstance(page.get('title'),str)
                and page['title'].startswith('File:')):
            rejected+=1
            continue
        infos=page.get('imageinfo',[])
        info=infos[0] if isinstance(infos,list) and len(infos)==1 and isinstance(infos[0],dict) else {}
        mime=info.get('mime')
        try:
            image=media=='image'
            require(isinstance(mime,str) and mime in FORMATS.values() and mime.startswith('image/' if image else 'video/')
                    and info.get('mediatype')==('BITMAP' if image else 'VIDEO'),'commons_unsafe_file_url')
            original_url(info.get('url'),mime)
            require('size' not in info or type(info['size']) is int and 0<info['size']<=(MAX_IMAGE_BYTES if image else MAX_MEDIA_BYTES),
                    'commons_unsafe_file_url')
        except (CompanyError,UnicodeError):
            rejected+=1
            continue
        ext=info.get('extmetadata')
        ext=ext if isinstance(ext,dict) else {}
        def field(key):
            entry=ext.get(key)
            return plain(entry.get('value')) if isinstance(entry,dict) else ''
        author,credit,license_url=field('Artist'),field('Credit'),field('LicenseUrl')
        rights=LICENSE.fullmatch(license_url)
        license_is_by=bool(rights and rights[2])
        license_name=field('LicenseShortName')
        label=license_name.upper()
        original_hash=info.get('sha1')
        checksum=None
        if isinstance(original_hash,str) and re.fullmatch('[a-f0-9]{40}',original_hash):
            checksum=original_hash
        elif isinstance(original_hash,str) and re.fullmatch('[0-9a-z]{31}',original_hash):
            number=int(original_hash,36)
            if number<2**160:
                checksum=f'{number:040x}'
        required=field('AttributionRequired').lower()
        title=plain(page['title'])
        reasons=[]
        if not title or not author or not credit or author.casefold() in ('unknown','unknown author','not specified'):
            reasons.append('missing_author_or_source')
        if not checksum:
            reasons.append('original_checksum_unverified')
        expected_label=('CC '+rights[2].upper()+' '+rights[3]) if license_is_by else None
        if not rights or (label!=expected_label if license_is_by else label not in ('CC0','CC0 1.0')):
            reasons.append('unsupported_or_missing_license')
        if license_is_by and required!='true' or not license_is_by and required!='false':
            reasons.append('attribution_requirement_unverified')
        if 'Restrictions' in ext and (field('Restrictions') or not isinstance(ext['Restrictions'],dict)):
            reasons.append('additional_restrictions')
        found.append(dict(id='commons-'+str(page['pageid']),title=title,scene_ids=[scene],
            url=info['url'],mime=mime,sha1=checksum,original_page=f'https://{HOST}/wiki/'+quote(page['title'].replace(' ','_'),safe=':'),
            creator=author,credit=credit,attribution=field('Attribution') or author,
            license_url=license_url if rights else None,license_name=license_name,
            attribution_required=license_is_by,share_alike=bool(rights and rights[2]=='by-sa'),
            edit_allowed_by_license=bool(rights),reviewable=not reasons,reasons=reasons))
    return found,rejected


def store_for(manager, plan, adaptive=False):
    return OwnerOperatingPolicy(manager.root/('commons_adaptive' if adaptive else 'commons_discovery'),dict(
        mode='cutroom_commons_adaptive_v1' if adaptive else 'cutroom_commons_discovery_v1',project=manager.acceptance_project,
        provider='Wikimedia Commons / Google Gemini only for fallback advice',
        plan_sha256=manager.contract['input']['approved_plan_hash'],
        direction_sha256=digest(plan),revision_scope=manager.root.name))


def search_unit(row):
    return unit('search:'+row.get('unit_id',row['scene_id']),'mediawiki_action_api',API,['scene_search_terms'],
                payload_sha256=digest(request_path(row['query'],row.get('media','video'))),max_results=LIMIT)


def fallback_unit():
    return unit('fallback',MODEL,ENDPOINT,['approved_scene_requirements','candidate_counts_and_rights_status'],
                max_output_tokens=4096)


class FallbackWorker(ProductionManager):
    marker_name='.commons-fallback-v1'
    acceptance_scope='cutroom_commons_fallback_once_v1'

    def freeze_contract(self):
        private_write(self.root/'inputs.json',canonical_bytes(self.contract['input']))

    def validate_plan(self,value):
        require([item['scene_id'] for item in value['options']]==
                [row['scene_id'] for row in self.contract['input']['scenes']], 'commons_fallback_invalid')
        for item in value['options']:
            safe_text(item['suggestion'],400)
            safe_text(item['rights_needed'],400)


def fallback_worker(manager, contract=None):
    root=manager.root/'commons_fallback'
    snapshot=root/'inputs.json'
    require(not root.is_symlink() and not snapshot.is_symlink(),'invalid_acceptance_path')
    if snapshot.is_file():
        contract=parse(snapshot.read_text())
    return FallbackWorker(root,dict(input=contract,system=FALLBACK_SYSTEM,schema=FALLBACK_SCHEMA))


def proposal(manager,plan,clips,manager_enabled,adaptive=False):
    previous=status(manager,plan,clips,manager_enabled) if adaptive else {}
    rows=(adaptive_queries(plan,clips,previous) if previous['status']=='empty' else []) if adaptive else queries(plan,clips)
    units=[search_unit(row) for row in rows]
    if rows and manager_enabled and not adaptive:
        units.append(fallback_unit())
    offer=store_for(manager,plan,adaptive).proposal(units)
    return {**offer,'queries':rows,'max_searches':len(rows),'fallback_max_calls':int(bool(rows and manager_enabled and not adaptive))}


def status(manager,plan,clips,manager_enabled,adaptive=False):
    store=store_for(manager,plan,adaptive)
    grant=store.read('policy.json')
    if grant is None:
        offer=proposal(manager,plan,clips,manager_enabled,adaptive)
        return dict(status='available' if offer['max_searches'] else 'unavailable',proposal=offer,review_hash=digest(offer))
    attempts=store.attempts()
    result=store.read('candidates.json')
    done=store.read('done.json')
    review=store.read('rights.json')
    state='active'
    if store.read('revoked.json'):
        state='revoked'
    elif any(not a['result'] or a['result']['status']!='completed' for a in attempts.values()):
        state='stopped'
    elif done:
        state='reviewed' if review else 'review' if any(c['reviewable'] for c in result['candidates']) else 'empty'
    elif datetime.fromisoformat(now())>=datetime.fromisoformat(grant['expires_at']):
        state='expired'
    answer=dict(status=state,proposal=grant['proposal'],expires_at=grant['expires_at'],
                result=result,result_sha256=digest(result) if result else None,rights=review,used=len(attempts))
    if (attempts.get('fallback',{}).get('result') or {}).get('status')=='completed':
        answer['fallback']=approved_manager_result(fallback_worker(manager))
    return answer


def accepted_media(manager,plan,adaptive=False):
    store=store_for(manager,plan,adaptive)
    review=store.read('rights.json')
    if not review:
        return {}
    result=store.read('candidates.json')
    require(digest(result)==review['result_sha256'],'commons_rights_review_changed')
    items={}
    for c in result['candidates']:
        if c['id'] in review['accepted']:
            require(c['reviewable'],'commons_rights_review_changed')
            items[c['id']]=dict(id=c['id'],issuer='Wikimedia Commons uploader / '+c['creator'],
                url=c['url'],mime=c['mime'],terms_url=c['license_url'],identity_url=c['original_page'],
                description=c['title'],sha256=None,sha1=c['sha1'],duration_frames=None,origin='commons_reviewed',
                scene_ids=c['scene_ids'],attribution=dict(creator=c['creator'],credit=c['credit'],
                    text=c['attribution'],license=c['license_url'],original_page=c['original_page'],
                    required=c['attribution_required'],share_alike=c['share_alike']),
                rights_evidence='Local edit/review attested by owner; license '+c['license_url']+
                    '; file page '+c['original_page']+'; creator '+c['creator'])
    require(set(items)==set(review['accepted']),'commons_rights_review_changed')
    return items


def action(manager,plan,clips,manager_enabled,name,body,adaptive=False):
    store=store_for(manager,plan,adaptive)
    if name=='production-discovery-rights':
        exact(body,('result_sha256','accepted','confirmed'))
        result=store.read('candidates.json')
        completed=store.read('done.json')
        allowed={c['id'] for c in result['candidates'] if c['reviewable']} if result else set()
        require(completed and not store.read('revoked.json') and body['confirmed'] is True
                and digest(result)==body['result_sha256']==completed['result_sha256']
                and isinstance(body['accepted'],list) and all(isinstance(c,str) and c in allowed for c in body['accepted'])
                and 0<len(set(body['accepted']))==len(body['accepted']),'commons_rights_review_changed')
        record=dict(accepted=body['accepted'],result_sha256=body['result_sha256'],at=now(),
            basis='owner_reviewed_subject_third_party_rights_license_attribution_local_edit_only')
        return store.write('rights.json',record)
    key,_=production_keys()
    if name=='production-discovery-approve':
        exact(body,('confirmed','review_hash'))
        require(body['confirmed'] is True,'owner_policy_required')
        return store.approve(proposal(manager,plan,clips,manager_enabled,adaptive),body['review_hash'],key)
    exact(body,())
    require(name=='production-discovery-run','invalid_request')
    grant=store.active(key)['proposal']
    require(not store.attempts(),'owner_policy_exhausted')
    lookup={}
    blocked=0
    missing=sorted({scene for row in grant['queries'] for scene in row['scene_ids']})
    for row in grant['queries']:
        media=row.get('media','video')
        if adaptive and row['wave']:
            deficient=unmatched_scenes(missing,lambda scene:[
                c['id'] for c in lookup.values() if c['reviewable'] and scene in c['scene_ids']])
            if not set(row['scene_ids']).intersection(deficient):
                continue
        path=request_path(row['query'],media)
        def search(proof,check):
            nonlocal blocked
            check()
            found,rejected=candidates(search_commons(path),row['scene_id'],media)
            for item in found:
                item['scene_ids']=row['scene_ids']
            blocked+=rejected
            store.write('metadata-'+row.get('unit_id',row['scene_id'])+'.json',dict(candidates=found,rejected=rejected,at=now()))
            for item in found:
                old=lookup.get(item['id']) or next((v for v in lookup.values() if v['url']==item['url']),None)
                if old:
                    old['scene_ids']=sorted(set(old['scene_ids']+item['scene_ids']))
                    if any(old[k]!=item[k] for k in ('creator','credit','license_url','url','sha1','attribution_required','attribution','share_alike')) or not item['reviewable']:
                        old.update(reviewable=False,reasons=['conflicting_or_unverified_metadata'])
                else:
                    lookup[item['id']]=item
        delegated_call(store,key,search_unit(row),digest(path),search)
    result=dict(candidates=list(lookup.values()),rejected_unsafe=blocked)
    store.write('candidates.json',result)
    eligible=[item for item in lookup.values() if item['reviewable']]
    deficient=unmatched_scenes(missing,lambda scene:[
        item['id'] for item in eligible if scene in item['scene_ids']])
    if deficient and grant['fallback_max_calls'] and manager_enabled:
        context=dict(goal='승인 영상 장면의 합법적인 시각 대안',scenes=[
            dict(scene_id=s['scene_id'],requirement=s['request']) for s in plan['scenes'] if s['scene_id'] in missing],
            potentially_unmatched=deficient,reviewable_count=len(eligible),unsafe_metadata=blocked)
        worker=fallback_worker(manager,context)
        wire=digest(worker._payload(None))
        delegated_call(store,key,fallback_unit(),wire,lambda proof,check:run_worker(worker,key,proof,wire,check))
    store.write('done.json',dict(result_sha256=digest(result),at=now()))
    return result
