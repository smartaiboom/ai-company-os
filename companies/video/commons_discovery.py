"""Bounded Wikimedia Commons file discovery and explicit local rights review."""
from datetime import datetime
from collections import Counter
from html.parser import HTMLParser
import http.client
import re
from time import monotonic
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

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
PROVENANCE={'utm_source':HOST,'utm_campaign':'imageinfo','utm_content':'original'}
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
    require(type(value) is str and len(value)<=1500 and value.isascii()
            and not any(c.isspace() for c in value),'commons_unsafe_file_url')
    try:
        url=urlsplit(value)
    except ValueError:
        raise CompanyError('commons_unsafe_file_url') from None
    match=re.fullmatch(r'/wikipedia/commons/[0-9a-f]/[0-9a-f]{2}/([^/]+)',url.path)
    require(url.scheme=='https' and url.netloc=='upload.wikimedia.org' and url.geturl()==value
            and not url.query and not url.fragment and match is not None,'commons_unsafe_file_url')
    require(re.search(r'%(?![a-fA-F0-9]{2})',match[1]) is None,'commons_unsafe_file_url')
    name=unquote(match[1],errors='strict')
    require(not any(c in name for c in '/\\%?#') and all(ord(c)>=32 and ord(c)!=127 for c in name)
            and not name.startswith('.') and not name.endswith('.'),'commons_unsafe_file_url')
    extension='.'+name.lower().rsplit('.',1)[-1]
    require(extension in FORMATS and (mime is None or FORMATS[extension]==mime),'commons_unsafe_file_url')
    return url


def imageinfo_url(value,mime):
    require(type(value) is str and len(value)<=1500 and value.isascii()
            and not any(c.isspace() for c in value),'commons_unsafe_file_url')
    try:
        url=urlsplit(value)
        require(url.geturl()==value and not url.fragment,'commons_unsafe_file_url')
        if url.query:
            pairs=parse_qsl(url.query,keep_blank_values=True,strict_parsing=True,max_num_fields=3,errors='strict')
            require(len(pairs)==len(PROVENANCE) and dict(pairs)==PROVENANCE,'commons_unsafe_file_url')
        return original_url(url._replace(query='').geturl(),mime).geturl()
    except (ValueError,UnicodeError):
        raise CompanyError('commons_unsafe_file_url') from None


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


def request_path(phrase,media='video',*,include_context=False):
    require(media in ('video','image'),'commons_response_failed')
    filetype='bitmap' if media=='image' else 'video'
    params=dict(action='query',generator='search',gsrnamespace=6,
        gsrsearch=f'{phrase} filetype:{filetype}',gsrlimit=LIMIT,prop='imageinfo',iilimit=1,
        iiprop='url|mime|mediatype|size|sha1|extmetadata',iiextmetadatafilter=
        'LicenseShortName|LicenseUrl|Artist|Credit|Attribution|AttributionRequired|Restrictions',
        format='json',formatversion=2,maxlag=5)
    if include_context:
        params['prop']='imageinfo|categories'
        params['iiextmetadatafilter']+='|ImageDescription'
        params.update(cllimit=5,clshow='!hidden')
    return '/w/api.php?'+urlencode(params)


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


def diagnostic_title(value):
    title=plain(value,140)
    if re.search(r'@|https?\s*[:_]|(?:\+?\d[ ._()-]*){8,}|(?:TOKEN|PASSWORD|SECRET)[_-]',title,re.I):
        return None
    return title or None


def technical_snapshot(page,media):
    info={}
    fields=[]
    if not isinstance(page,dict):
        page={}
        fields.append('page_structure')
    else:
        if type(page.get('ns')) is not int or page['ns']!=6:
            fields.append('file_namespace')
        if type(page.get('pageid')) is not int or not 0<page['pageid']<10**12:
            fields.append('page_id')
        if not isinstance(page.get('title'),str) or not page['title'].startswith('File:') or len(page['title'])<=5:
            fields.append('file_title')
    infos=page.get('imageinfo')
    url=None
    if isinstance(infos,list) and len(infos)==1 and isinstance(infos[0],dict):
        info=infos[0]
        image=media=='image'
        mime=info.get('mime')
        if not isinstance(mime,str) or mime not in FORMATS.values() or not mime.startswith('image/' if image else 'video/'):
            fields.append('mime')
        if info.get('mediatype')!=('BITMAP' if image else 'VIDEO'):
            fields.append('media_type')
        if 'url' not in info:
            fields.append('original_url_missing')
        else:
            try:
                url=imageinfo_url(info['url'],mime if isinstance(mime,str) and mime in FORMATS.values() else None)
            except CompanyError:
                fields.append('original_url_invalid')
        if 'size' in info:
            size=info['size']
            if type(size) is not int or size<=0:
                fields.append('size_invalid')
            elif size>(MAX_IMAGE_BYTES if image else MAX_MEDIA_BYTES):
                fields.append('size_limit')
    elif 'page_structure' not in fields:
        fields.append('imageinfo_missing' if infos is None or infos==[] else 'imageinfo_shape')
    mime=info.get('mime')
    media_type=info.get('mediatype')
    size=info.get('size')
    snapshot=dict(page_id=page.get('pageid') if type(page.get('pageid')) is int and 0<page['pageid']<10**12 else None,
        title=diagnostic_title(page.get('title')),
        mime=mime if isinstance(mime,str) and re.fullmatch('[a-z0-9.+-]{1,32}/[a-z0-9.+-]{1,32}',mime) else None,
        media_type=media_type if media_type in ('BITMAP','VIDEO','DRAWING','AUDIO','MULTIMEDIA','UNKNOWN',
                                               'OFFICE','TEXT','EXECUTABLE','ARCHIVE','3D') else None,
        size_bytes=size if type(size) is int and -(2**63)<=size<2**63 else None,
        url_allowed=url is not None,provenance_removed=bool(url and info['url']!=url),technical_reasons=fields)
    return info,url,snapshot


def candidates(data, scene, media='video', diagnostics=None, *,include_context=False):
    query=data.get('query',{})
    pages=query.get('pages',[]) if isinstance(query,dict) else None
    if diagnostics is not None:
        diagnostics.update(response_json_sha256=digest(data),pages=[],returned=len(pages) if isinstance(pages,list) else None)
    if not isinstance(pages,list):
        if diagnostics is not None:
            diagnostics['response_issue']='pages_shape'
        raise CompanyError('commons_response_shape')
    if len(pages)>LIMIT:
        if diagnostics is not None:
            diagnostics['response_issue']='pages_limit'
        raise CompanyError('commons_response_limit')
    found=[]
    rejected=0
    page_ids=Counter(page['pageid'] for page in pages if isinstance(page,dict)
                     and type(page.get('pageid')) is int)
    for page in pages:
        info,url,snapshot=technical_snapshot(page,media)
        if page_ids[snapshot['page_id']]>1:
            snapshot['technical_reasons'].append('duplicate_page_id')
        if diagnostics is not None:
            diagnostics['pages'].append(snapshot)
        if snapshot['technical_reasons']:
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
        snapshot.update(rights_reasons=reasons,scene_suitability='unassessed')
        found.append(dict(id='commons-'+str(page['pageid']),title=title,scene_ids=[scene],
            url=url,mime=info['mime'],sha1=checksum,original_page=f'https://{HOST}/wiki/'+quote(page['title'].replace(' ','_'),safe=':'),
            creator=author,credit=credit,attribution=field('Attribution') or author,
            license_url=license_url if rights else None,license_name=license_name,
            attribution_required=license_is_by,share_alike=bool(rights and rights[2]=='by-sa'),
            edit_allowed_by_license=bool(rights),reviewable=not reasons,reasons=reasons))
        if include_context:
            tags=page.get('categories')
            found[-1]['description']=field('ImageDescription')
            found[-1]['categories']=[plain(tag['title'],140) for tag in tags[:5]
                if isinstance(tag,dict) and tag.get('ns')==14 and isinstance(tag.get('title'),str)] if isinstance(tags,list) else []
    if diagnostics is not None:
        for kind in ('technical','rights'):
            diagnostics[kind+'_counts']=dict(Counter(code for row in diagnostics['pages'] for code in row.get(kind+'_reasons',[])))
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
                result=result,result_sha256=digest(result) if result else None,rights=review,
                search_trace=search_trace(store),used=len(attempts))
    if (attempts.get('fallback',{}).get('result') or {}).get('status')=='completed':
        answer['fallback']=approved_manager_result(fallback_worker(manager))
    return answer


def accepted_media(manager,plan,adaptive=False,diagnostic=False,*,store=None):
    if store is None:
        store=diagnostic_store(manager,plan) if diagnostic else store_for(manager,plan,adaptive)
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
            if c.get('relevance'):
                items[c['id']]['relevance']=c['relevance']
    require(set(items)==set(review['accepted']),'commons_rights_review_changed')
    return items


def review_rights(store,body):
    exact(body,('result_sha256','accepted','confirmed'))
    result=store.read('candidates.json')
    completed=store.read('done.json')
    allowed={c['id'] for c in result['candidates'] if c['reviewable']} if result else set()
    require(completed and not store.read('revoked.json') and body['confirmed'] is True
            and all(entry['result'] and entry['result']['status']=='completed' for entry in store.attempts().values())
            and digest(result)==body['result_sha256']==completed['result_sha256']
            and isinstance(body['accepted'],list) and all(isinstance(c,str) and c in allowed for c in body['accepted'])
            and 0<len(set(body['accepted']))==len(body['accepted']),'commons_rights_review_changed')
    record=dict(accepted=body['accepted'],result_sha256=body['result_sha256'],at=now(),
        basis='owner_reviewed_subject_third_party_rights_license_attribution_local_edit_only')
    return store.write('rights.json',record)


def row_key(row):
    return row.get('unit_id',row['scene_id'])


def collect_metadata(store,row,path,*,include_context=False):
    info={}
    data=search_commons(path)
    name='metadata-'+row_key(row)+'.json'
    try:
        found,rejected=candidates(data,row['scene_id'],row.get('media','video'),info,include_context=include_context)
    except CompanyError:
        store.write(name,dict(candidates=[],rejected=None,diagnostics=info,at=now()))
        raise
    for item in found:
        item['scene_ids']=row['scene_ids']
    store.write(name,dict(candidates=found,rejected=rejected,diagnostics=info,at=now()))
    return found,rejected


def search_trace(store):
    grant=store.read('policy.json')
    if not grant:
        return []
    ledger=store.attempts()
    rows=[]
    for row in grant['proposal']['queries']:
        identifier=row_key(row)
        entry=ledger.get('search:'+identifier)
        if not entry:
            continue
        saved=store.read('metadata-'+identifier+'.json')
        rows.append(dict(query=row['query'],media=row.get('media','video'),scene_ids=row['scene_ids'],
            status=entry['result']['status'] if entry['result'] else 'reserved',
            candidate_count=len(saved['candidates']) if saved is not None else None,
            rejected=saved['rejected'] if saved is not None else None,
            diagnostics=saved.get('diagnostics') if saved is not None else None))
    return rows


def action(manager,plan,clips,manager_enabled,name,body,adaptive=False):
    store=store_for(manager,plan,adaptive)
    if name=='production-discovery-rights':
        return review_rights(store,body)
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
            found,rejected=collect_metadata(store,row,path)
            blocked+=rejected
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


def diagnostic_store(manager,plan):
    binding={**store_for(manager,plan,adaptive=True).binding,
             'mode':'cutroom_commons_diagnostic_v1','provider':'Wikimedia Commons'}
    return OwnerOperatingPolicy(manager.root/'commons_diagnostic',binding)


def diagnostic_proposal(manager,plan):
    previous=store_for(manager,plan,adaptive=True)
    grant=previous.read('policy.json')
    if not grant or not previous.read('done.json'):
        return None
    candidates_for_test=[]
    for row in grant['proposal']['queries']:
        record=previous.read('metadata-'+row_key(row)+'.json')
        if record and record['rejected'] and not record.get('diagnostics'):
            candidates_for_test.append((row,record['rejected']))
    if not candidates_for_test:
        return None
    row,rejected=max(candidates_for_test,key=lambda item:(item[1],item[0].get('media')=='image'))
    signed=search_unit(row)
    old=previous.attempts().get(signed['id'])
    require(old and old['result'] and old['result']['status']=='completed'
            and old['reservation']['payload_sha256']==signed['payload_sha256'],'owner_policy_scope_changed')
    scope=diagnostic_store(manager,plan).proposal([signed])
    return {**scope,'queries':[row],'max_searches':1,'max_downloads':0,'fallback_max_calls':0,
            'previous_rejected':rejected,'previous_request_sha256':signed['payload_sha256']}


def diagnostic_status(manager,plan):
    store=diagnostic_store(manager,plan)
    grant=store.read('policy.json')
    if not grant:
        offer=diagnostic_proposal(manager,plan)
        return dict(status='available',proposal=offer,review_hash=digest(offer)) if offer else None
    result=store.read('candidates.json')
    attempts=store.attempts()
    scope=grant['proposal']
    if store.read('revoked.json'):
        state='revoked'
    elif any(not row['result'] or row['result']['status']!='completed' for row in attempts.values()):
        state='stopped'
    elif store.read('done.json'):
        state=('reviewed' if store.read('rights.json') else 'review'
               if any(row['reviewable'] for row in result['candidates']) else 'empty')
    elif attempts:
        state='stopped'
    elif datetime.fromisoformat(now())>=datetime.fromisoformat(grant['expires_at']):
        state='expired'
    else:
        state='active'
    return dict(status=state,proposal=scope,result=result,result_sha256=digest(result) if result else None,
                search_trace=search_trace(store),used=len(attempts))


def diagnostic_action(manager,plan,name,body):
    store=diagnostic_store(manager,plan)
    if name=='production-diagnostic-rights':
        return review_rights(store,body)
    key,_=production_keys()
    if name=='production-diagnostic-approve':
        exact(body,('confirmed','review_hash'))
        offer=diagnostic_proposal(manager,plan)
        require(offer and body['confirmed'] is True,'owner_policy_required')
        return store.approve(offer,body['review_hash'],key)
    exact(body,())
    require(name=='production-diagnostic-run','invalid_request')
    grant=store.active(key)['proposal']
    require(not store.attempts(),'owner_policy_exhausted')
    row,=grant['queries']
    path=request_path(row['query'],row.get('media','video'))
    operation=search_unit(row)

    def perform(proof,check):
        check()
        found,rejected=collect_metadata(store,row,path)
        result=dict(candidates=found,rejected_unsafe=rejected)
        store.write('candidates.json',result)
        store.write('done.json',dict(result_sha256=digest(result),at=now()))

    return delegated_call(store,key,operation,digest(path),perform)
