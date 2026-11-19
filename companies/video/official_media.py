"""Bounded direct MP4 transfer from a registered official publisher endpoint."""
import hashlib
import http.client
import ipaddress
from datetime import datetime
from queue import Empty, Queue
import re
import socket
import ssl
from threading import Thread, Timer
from time import monotonic
from urllib.parse import urlsplit

from autonomous_company import CompanyError, exact, now, parse, require
from goal_dialogue import safe_text

MAX_BYTES = 64 * 1024 * 1024
TIMEOUT = 45
HOST = re.compile(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}')
IDENT = re.compile(r'[a-z0-9][a-z0-9_-]{0,39}')
PATH = re.compile(r'/[A-Za-z0-9._~/-]{1,1200}')


def official_url(value, *, media):
    require(isinstance(value,str) and value.isascii() and len(value)<=1500,'official_url_blocked')
    try:
        url=urlsplit(value)
    except ValueError:
        raise CompanyError('official_url_blocked') from None
    require(url.scheme=='https' and HOST.fullmatch(url.netloc) and
            (not media and url.path=='/' or PATH.fullmatch(url.path))
            and url.geturl()==value and not url.query and not url.fragment
            and (url.path=='/' or all(part not in ('','.','..') for part in url.path.split('/')[1:]))
            and (not media or url.path.lower().endswith('.mp4')),'official_url_blocked')
    require(not (url.hostname=='youtu.be' or any(url.hostname==name or url.hostname.endswith('.'+name)
        for name in ('youtube.com','youtube-nocookie.com','googlevideo.com'))),'official_url_blocked')
    return url


def _manifest(root, name):
    path=root/name
    require(not any(p.is_symlink() for p in (path,root,*root.parents)), 'official_registry_invalid')
    if not path.exists():
        return []
    require(path.is_file() and path.stat().st_size<=32768,'official_registry_invalid')
    rows=parse(path.read_text())
    require(isinstance(rows,list) and len(rows)<=16,'official_registry_invalid')
    return rows


def registered_media(root):
    sources={}
    for row in _manifest(root,'publishers.json'):
        exact(row,('issuer','identity_url','hosts'))
        safe_text(row['issuer'],120)
        identity=official_url(row['identity_url'],media=False)
        require(row['issuer'] not in sources and isinstance(row['hosts'],list) and 1<=len(row['hosts'])<=8
                and all(isinstance(host,str) and HOST.fullmatch(host) for host in row['hosts'])
                and identity.hostname in row['hosts'],'official_registry_invalid')
        sources[row['issuer']]=row
    assets={}
    for row in _manifest(root,'inventory.json'):
        exact(row,('id','issuer','url','terms_url','description','rights_evidence','download_allowed',
                   'local_edit_review_allowed','free_download','duration_frames','sha256'))
        require(isinstance(row['id'],str) and IDENT.fullmatch(row['id']) and row['id'] not in assets
                and isinstance(row['issuer'],str) and row['issuer'] in sources
                and row['download_allowed'] is True and row['local_edit_review_allowed'] is True
                and row['free_download'] is True,'official_rights_unverified')
        safe_text(row['description'],320)
        safe_text(row['rights_evidence'],1200)
        require(len(row['rights_evidence'].strip())>=20,'official_rights_unverified')
        require(type(row['duration_frames']) is int and 24<=row['duration_frames']<=2880
                and (row['sha256'] is None or isinstance(row['sha256'],str)
                     and re.fullmatch('[a-f0-9]{64}',row['sha256'])),'official_registry_invalid')
        url=official_url(row['url'],media=True)
        terms=official_url(row['terms_url'],media=False)
        issuer=sources[row['issuer']]
        require(url.hostname in issuer['hosts'] and terms.hostname in issuer['hosts'],'official_host_not_registered')
        assets[row['id']]={**row,'identity_url':issuer['identity_url']}
    require(len({asset['url'] for asset in assets.values()})==len(assets),'official_registry_invalid')
    return assets


def _global_addresses(host, deadline):
    results=Queue(maxsize=1)
    def resolve():
        try:
            results.put(socket.getaddrinfo(host,443,type=socket.SOCK_STREAM))
        except OSError:
            results.put([])
    Thread(target=resolve,daemon=True).start()
    try:
        rows=results.get(timeout=max(0,deadline-monotonic()))
    except Empty:
        raise CompanyError('official_download_timeout') from None
    addresses=[(family,address, ipaddress.ip_address(address[0]))
               for family,_,_,_,address in rows if family in (socket.AF_INET,socket.AF_INET6)]
    require(addresses and all(ip.is_global and not ip.is_multicast and not ip.is_reserved
                and not getattr(ip,'ipv4_mapped',None) and not getattr(ip,'sixtofour',None)
                and not getattr(ip,'teredo',None) and not ip.is_link_local and not ip.is_loopback
                and (ip.version==4 or ip in ipaddress.ip_network('2000::/3'))
                for _,_,ip in addresses),'official_destination_blocked')
    return addresses[0][:2]


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, family, address, deadline):
        super().__init__(host, timeout=max(.001,deadline-monotonic()),context=ssl.create_default_context())
        self._family=family
        self._address=address
        self._deadline=deadline
        self._timer=None

    def connect(self):
        raw=socket.socket(self._family,socket.SOCK_STREAM)
        try:
            raw.settimeout(max(.001,self._deadline-monotonic()))
            raw.connect(self._address)
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host,do_handshake_on_connect=False)
            self._timer=Timer(max(0,self._deadline-monotonic()),self._abort,args=(self.sock,))
            self._timer.daemon=True
            self._timer.start()
            self.sock.do_handshake()
        except BaseException:
            raw.close()
            raise

    @staticmethod
    def _abort(sock):
        try: sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass

    def cancel_timer(self):
        if self._timer:
            self._timer.cancel()


def download_mp4(asset, destination):
    """One request, no cookies, credentials, proxy, redirects, or retries."""
    mime=asset.get('mime','video/mp4')
    if asset.get('origin')=='commons_reviewed':
        from commons_discovery import original_url, USER_AGENT, MAX_IMAGE_BYTES
        url=original_url(asset['url'],mime)
        headers={'User-Agent':USER_AGENT}
        limit=MAX_IMAGE_BYTES if mime.startswith('image/') else MAX_BYTES
    elif asset.get('origin')=='publisher_reviewed':
        from publisher_discovery import FORMATS, PROFILES, USER_AGENT, profile_url
        require(datetime.fromisoformat(now())<datetime.fromisoformat(asset['access_expires_at']),
                'publisher_rights_unverified')
        url=profile_url(PROFILES[asset['publisher_profile']],asset['url'],'asset')
        require(FORMATS.get('.'+url.path.rsplit('.',1)[-1].lower())==mime,'official_media_response_invalid')
        headers={'User-Agent':USER_AGENT}
        limit=8*1024*1024 if mime.startswith('image/') else MAX_BYTES
    else:
        url=official_url(asset['url'],media=True)
        headers={}
        limit=MAX_BYTES
    deadline=monotonic()+TIMEOUT
    family,address=_global_addresses(url.hostname,deadline)
    connection=_PinnedHTTPS(url.hostname,family,address,deadline)
    try:
        connection.request('GET',url.path,headers={**headers,'Accept':mime,'Accept-Encoding':'identity'})
        with connection.getresponse() as response:
            require(response.status==200 and response.headers.get_content_type()==mime
                    and response.getheader('Content-Encoding','identity').lower()=='identity',
                    'official_media_response_invalid')
            size=response.getheader('Content-Length')
            require(size is None or size.isascii() and size.isdecimal() and 0<int(size)<=limit,
                    'official_media_size_invalid')
            checksum=hashlib.sha256()
            original_checksum=hashlib.sha1() if asset.get('origin')=='commons_reviewed' else None
            total=0
            with destination.open('xb') as output:
                while block:=response.read1(65536):
                    require(monotonic()<=deadline,'official_download_timeout')
                    total+=len(block)
                    require(total<=limit,'official_media_size_invalid')
                    checksum.update(block)
                    if original_checksum:
                        original_checksum.update(block)
                    output.write(block)
            require(monotonic()<=deadline,'official_download_timeout')
            require(total>0 and (size is None or total==int(size)),'official_media_size_invalid')
            sha=checksum.hexdigest()
            require(asset['sha256'] is None or sha==asset['sha256'],'production_source_asset_changed')
            require(original_checksum is None or original_checksum.hexdigest()==asset['sha1'],
                    'production_source_asset_changed')
            return dict(sha256=sha,bytes=total,http_status=200)
    except (OSError,http.client.HTTPException):
        raise CompanyError('official_download_failed_or_uncertain') from None
    finally:
        connection.close()
        connection.cancel_timer()
