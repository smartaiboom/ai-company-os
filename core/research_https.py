"""HTTPS with a bounded deadline and a TLS-verified, pinned public IP."""
import http.client
import ipaddress
from queue import Empty, Queue
import re
import socket
import ssl
from threading import Thread, Timer
from time import monotonic

from autonomous_company import CompanyError, require
from decision_recovery import ProviderFailure


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


def fetch_public_text(parsed,kind,*,agent,connect,resolve,page_limit):
    """Fetch an exact, caller-allowlisted robots or HTML URL using the shared pinned transport."""
    require(kind in ('page','robots'),'publisher_url_blocked')
    deadline=monotonic()+20
    family,address=resolve(parsed.hostname,deadline)
    connection=connect(parsed.hostname,family,address,deadline)
    limit=32768 if kind=='robots' else page_limit
    try:
        connection.request('GET',parsed.path,headers={'User-Agent':agent,
            'Accept':'text/plain' if kind=='robots' else 'text/html','Accept-Encoding':'identity'})
        with connection.getresponse() as response:
            if response.status in (401,403,404) or 300<=response.status<400:
                return dict(status=response.status,text=None)
            if response.status != 200:
                raise ProviderFailure('publisher_http_failure')
            mime='text/plain' if kind=='robots' else 'text/html'
            if (response.headers.get_content_type()!=mime or
                    response.getheader('Content-Encoding','identity').lower()!='identity'):
                return dict(status=200,text=None)
            data=response.read(limit+1)
            require(len(data)<=limit and monotonic()<=deadline,'publisher_response_limit')
            return dict(status=200,text=data.decode('utf-8',errors='strict'))
    except (UnicodeError,OSError,http.client.HTTPException):
        raise CompanyError('publisher_http_failure') from None
    finally:
        connection.close()
        connection.cancel_timer()


def robots_allows(text,path):
    """Conservative consent gate. A missing/unverified file or matching denial blocks the path."""
    if not isinstance(text,str) or not text.strip():
        return False
    agents=[]
    previous=None
    applicable=False
    for raw in text.splitlines():
        line=raw.split('#',1)[0].strip()
        if ':' not in line:
            continue
        key,value=(part.strip() for part in line.split(':',1))
        key=key.lower()
        if key=='user-agent':
            if previous!='user-agent':
                agents=[]
            agents.append(value.lower())
        elif key in ('allow','disallow','crawl-delay') and any(a=='*' or a and a in 'aicompanyos-cutroom' for a in agents):
            if key=='crawl-delay' and value!='0':
                return False
            applicable=True
            if key=='disallow' and value:
                tail='$' if value.endswith('$') else ''
                literal=value[:-1] if tail else value
                pattern=re.escape(literal).replace(r'\*','.*')+tail
                if re.match(pattern,path):
                    return False
        previous=key
    return applicable


def observe_approved_page(page, robots, invoke, fetch, extract, cache):
    """Observe one exact approved page, charging separate robots and page requests."""
    host = page['host']
    requests = []

    def get(entry):
        response = {}

        def read(check):
            check()
            response.update(fetch(entry['url'], entry['kind']))

        operation = entry['operation']
        invoke(operation, operation['payload_sha256'], read)
        requests.append(dict(url=entry['url'], kind=entry['kind'], http_status=response['status']))
        return response

    if host not in cache:
        cache[host] = get(robots)['text']
    if not robots_allows(cache[host], page['path']):
        return dict(status='policy_blocked', reason='robots_permission_unconfirmed', sources=[], requests=requests)
    response = get(page)
    if response['text'] is None:
        if response['status'] in (401, 403):
            cache[host] = None
        return dict(status='unavailable', reason='restricted_or_unavailable', sources=[], requests=requests)
    observed = extract(page['url'], response['text'])
    if observed['status'] == 'policy_blocked':
        cache[host] = None
    return {**observed, 'requests':requests}
