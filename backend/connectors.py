"""Seeded public web connector for qualitative evidence."""
import hashlib
import ipaddress
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import func, select

from .audit import append_event, digest
from .config import DATA_DIR, MAPPING_VERSION, PIPELINE_VERSION
from .ingestion import evidence
from .models import Aspect, Feedback, Source
from .schemas import WebConnectorRequest
from .taxonomy import feature_for_tag, seed_taxonomy, serious_concern

USER_AGENT = 'BMWProductCockpit/1.0 (+local seeded evidence connector)'
MAX_BYTES = 1_500_000
MIN_BLOCK_CHARS = 80
MAX_BLOCKS_PER_PAGE = 80

TAG_KEYWORDS = [
    (('touchscreen', 'touch screen', 'screen', 'display', 'idrive', 'infotainment'), 'Touch screen, operation'),
    (('voice', 'speech', 'assistant'), 'Voice control / speech recognition'),
    (('carplay', 'android auto', 'bluetooth', 'phone'), 'Manage / pair mobile device (Bluetooth)'),
    (('charging', 'charger', 'charge', 'battery', 'range'), 'Charge high-voltage battery'),
    (('seat', 'seats', 'lumbar', 'massage'), 'Seats'),
    (('climate', 'air conditioning', 'heater', 'heated'), 'Air conditioning, setting'),
    (('brake', 'brakes', 'steering', 'safety'), 'Vehicle safety, overall technology'),
    (('lane', 'assist', 'cruise', 'parking', 'camera'), 'Driver assistance, automated driving, overall technology'),
    (('price', 'expensive', 'cost'), 'General enquiry: customer feedback'),
    (('noise', 'sound', 'audio', 'speaker'), 'Audio mode, sound'),
]

NEGATIVE = re.compile(r'\b(problem|issue|annoy|hard|difficult|fail|broken|bug|bad|hate|missing|wish|want|needs?|complain|disappoint)\b', re.I)
DEFECT = re.compile(r'\b(fail|failed|broken|bug|error|fault|stopped working|does not work|not working)\b', re.I)
POSITIVE = re.compile(r'\b(love|like|great|excellent|good|easy|smooth|useful|impressive)\b', re.I)
NAVIGATION = re.compile(r'\b(cookie|privacy policy|terms of use|subscribe|sign in|login|advertisement|share this|all rights reserved)\b', re.I)


class TextBlockParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.blocks = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'noscript', 'svg', 'nav', 'footer', 'header', 'form', 'button'):
            self.hidden += 1
        if self.hidden:
            return
        classes = ' '.join([attrs.get('class', ''), attrs.get('id', '')]).casefold()
        capture = tag in ('article', 'p', 'li', 'blockquote') or any(token in classes for token in ('post', 'comment', 'message', 'reply', 'review'))
        self.stack.append({'tag': tag, 'capture': capture, 'text': []})

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in ('script', 'style', 'noscript', 'svg', 'nav', 'footer', 'header', 'form', 'button'):
                self.hidden = max(self.hidden - 1, 0)
            return
        if not self.stack:
            return
        current = self.stack.pop()
        text_value = normalize_text(' '.join(current['text']))
        if current['capture'] and useful_block(text_value):
            self.blocks.append(text_value)
        if self.stack and text_value:
            self.stack[-1]['text'].append(text_value)

    def handle_data(self, data):
        if not self.hidden and self.stack:
            self.stack[-1]['text'].append(data)


def normalize_url(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('Only public http and https URLs are supported.')
    host = parsed.hostname or ''
    if is_private_host(host):
        raise ValueError('Private, localhost and link-local URLs are not allowed.')
    normalized = parsed._replace(fragment='', scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return urlunparse(normalized)


def is_private_host(host):
    if host in ('localhost',) or host.endswith('.local'):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f'Could not resolve host {host}.') from exc
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return True
    return False


def robots_allowed(client, url):
    parsed = urlparse(url)
    robots_url = urljoin(f'{parsed.scheme}://{parsed.netloc}', '/robots.txt')
    try:
        response = client.get(robots_url, headers={'User-Agent': USER_AGENT})
    except httpx.HTTPError:
        return True
    if response.status_code >= 400:
        return True
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def normalize_text(value):
    return re.sub(r'\s+', ' ', value).strip()


def useful_block(value):
    if len(value) < MIN_BLOCK_CHARS or len(value) > 5000:
        return False
    if NAVIGATION.search(value) and len(value) < 220:
        return False
    words = re.findall(r'[A-Za-z]{3,}', value)
    return len(words) >= 12


def extract_blocks(html):
    if '<' not in html:
        return [block for block in (normalize_text(part) for part in re.split(r'\n{2,}', html)) if useful_block(block)][:MAX_BLOCKS_PER_PAGE]
    parser = TextBlockParser()
    parser.feed(html)
    seen, blocks = set(), []
    for block in parser.blocks:
        key = block.casefold()
        if key in seen:
            continue
        seen.add(key)
        blocks.append(block)
        if len(blocks) >= MAX_BLOCKS_PER_PAGE:
            break
    return blocks


def feedback_type(text_value):
    if DEFECT.search(text_value):
        return 'Defect'
    if NEGATIVE.search(text_value):
        return 'Wants' if re.search(r'\b(wish|want|missing|needs?)\b', text_value, re.I) else 'Difficult to Use'
    if POSITIVE.search(text_value):
        return 'Likes'
    return 'Unclassified'


def feature_tag(text_value):
    lowered = text_value.casefold()
    for keywords, tag in TAG_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return tag
    return 'Unclassified feedback'


def import_web(session, request: WebConnectorRequest, progress=lambda _: None, client=None):
    seed_taxonomy(session)
    DATA_DIR.joinpath('sources').mkdir(parents=True, exist_ok=True)
    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=httpx.Timeout(12.0, connect=5.0), follow_redirects=True, max_redirects=3)
    summary = {'imported': [], 'skipped': [], 'failed': []}
    try:
        for raw_url in request.urls:
            try:
                url = normalize_url(raw_url)
                progress(f'Fetching {url}')
                if not robots_allowed(client, url):
                    raise ValueError('robots.txt disallows fetching this URL.')
                response = client.get(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,text/plain;q=0.8'})
                final_url = normalize_url(str(response.url))
                if final_url != url:
                    url = final_url
                if response.status_code >= 400:
                    raise ValueError(f'HTTP {response.status_code}.')
                content_type = response.headers.get('content-type', '').casefold()
                if 'html' not in content_type and 'text/plain' not in content_type:
                    raise ValueError(f'Unsupported content type: {content_type or "unknown"}.')
                content = response.content
                if len(content) > MAX_BYTES:
                    raise ValueError('Page exceeds the connector size limit.')
                html = content.decode(response.encoding or 'utf-8', errors='replace')
                checksum = hashlib.sha256(content).hexdigest()
                existing = session.scalar(select(Source).where(Source.checksum == checksum))
                if existing:
                    summary['skipped'].append({'url': url, 'source_id': existing.id, 'reason': 'unchanged checksum'})
                    continue
                blocks = extract_blocks(html)
                if not blocks:
                    raise ValueError('No readable qualitative text blocks were found in static HTML.')
                for older in session.scalars(select(Source).where(Source.format == 'html', Source.edition == url, Source.active == True)):
                    older.active = False
                source_id = checksum[:32]
                filename = safe_filename(url, checksum)
                path = DATA_DIR / 'sources' / filename
                path.write_bytes(content)
                source = Source(id=source_id, filename=filename, checksum=checksum, format='html', kind='customer_statement',
                                origin='observed', language='en', market=request.country, source_date=response.headers.get('last-modified'),
                                edition=url, path=str(path), extraction_version=PIPELINE_VERSION)
                session.add(source)
                session.flush()
                import_blocks(session, source, url, blocks, request)
                source.record_count = len(blocks)
                source.row_count = len(blocks)
                summary['imported'].append({'url': url, 'source_id': source.id, 'records': source.record_count, 'http_status': response.status_code})
            except Exception as exc:
                summary['failed'].append({'url': raw_url, 'error': str(exc)[:500]})
        append_event(session, 'Web connector', 'connectors.web.imported', 'web', summary)
        if not summary['imported'] and not summary['skipped'] and summary['failed']:
            raise ValueError('Web connector did not import any pages: ' + '; '.join(f"{f['url']}: {f['error']}" for f in summary['failed'][:3]))
        return summary
    finally:
        if own_client:
            client.close()


def safe_filename(url, checksum):
    parsed = urlparse(url)
    stem = re.sub(r'[^a-zA-Z0-9]+', '-', (parsed.netloc + parsed.path).strip('/'))[:80].strip('-') or 'web-evidence'
    return f'{checksum[:16]}-{stem}.html'


def import_blocks(session, source, url, blocks, request):
    hashes = {h: count for h, count in session.execute(select(Feedback.text_hash, func.count()).group_by(Feedback.text_hash)).all()}
    local_hashes = {}
    for block in blocks:
        text_hash = hashlib.sha256(block.encode('utf-8')).hexdigest()
        local_hashes[text_hash] = local_hashes.get(text_hash, 0) + 1
    for index, block in enumerate(blocks, 1):
        text_hash = hashlib.sha256(block.encode('utf-8')).hexdigest()
        external_id = digest([url, block])[:24]
        ref = evidence(session, source, {'url': url, 'block_index': index, 'extraction_method': 'static-html-text-block-v1'}, block, 'customer_statement', request.model)
        record = Feedback(id=f'{source.id[:12]}:{external_id}', source_id=source.id, external_id=external_id,
                          model=request.model, country=request.country, powertrain=request.powertrain,
                          raw_powertrain=request.powertrain, text=block, text_hash=text_hash, origin='observed',
                          source_label=request.source_label or url, source_date=source.source_date, tags=[],
                          duplicate_text=hashes.get(text_hash, 0) > 0 or local_hashes[text_hash] > 1)
        session.add(record)
        session.flush()
        tag = feature_tag(block)
        kind = feedback_type(block)
        feature = feature_for_tag(session, tag)
        record.tags = [{'row': index, 'type': kind, 'level2': tag, 'level3': None, 'combined': tag, 'evidence_id': ref.id}]
        session.add(Aspect(feedback_id=record.id, evidence_id=ref.id, feature_id=feature.id, feedback_type=kind,
                           quote=block, mapping_status='pending' if tag == 'Unclassified feedback' else 'suggested',
                           mapping_reason='Seeded web connector keyword mapping; PM review required.',
                           mapping_version=f'{MAPPING_VERSION}-web-v1',
                           critical=serious_concern(block, kind) and feature.category in ('C04', 'C09')))
