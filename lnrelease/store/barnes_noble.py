from __future__ import annotations

import datetime
import json
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import utils
from session import Session

NAME = 'Barnes & Noble'
SALT = hash(NAME)

PATH = re.compile(r'/w/(?P<name>[\w-]+)/(?P<id>\d+)')
SCRIPT = re.compile(r'enqueue\((?P<json>"\[\{(?:[^"\\]|\\.)*")\)')
ISBN = re.compile(r'97[89]\d{10}')


def equal(a: str, b: str) -> bool:
    ua = urlparse(a)
    ub = urlparse(b)
    match_a = PATH.fullmatch(ua.path)
    match_b = PATH.fullmatch(ub.path)
    ean_a = next((v for k, v in parse_qsl(ua.query) if k == 'ean'), '')
    ean_b = next((v for k, v in parse_qsl(ub.query) if k == 'ean'), '')

    return (ean_a and ean_b and ean_a == ean_b
            or match_a and match_b
            and match_a.group('id') == match_b.group('id')
            and not (ean_a and ean_b))


def hash_link(link: str) -> int:
    u = urlparse(link)
    ean = next((v for k, v in parse_qsl(u.query) if k == 'ean'), '')
    match = PATH.fullmatch(u.path)
    return SALT + hash(ean or match.group('id'))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    query = urlencode([(k, v) for k, v in parse_qsl(u.query) if k == 'ean'])
    if not PATH.fullmatch(u.path):
        res = session.resolve(link, force=True)
        if res != link:
            return normalise(session, res)
        if query and u.path.startswith('/w'):
            return urlunparse(('https', 'www.barnesandnoble.com', '/w', '', query, ''))
        return None
    return urlunparse(('https', 'www.barnesandnoble.com', u.path, '', query, ''))


def parse(session: Session, links: list[str], *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    ean = next((v for k, v in parse_qsl(urlparse(links[0]).query) if k == 'ean'), '')
    page = session.get(links[0])
    parts = urlparse(page.url)
    jsn = json.loads(json.loads(SCRIPT.search(page.text).group('json')))

    def get(i: int):
        x = jsn[i]
        if isinstance(x, dict):
            return {get(int(k[1:])): get(v) if v >= 0 else None for k, v in x.items()}
        if isinstance(x, list):
            return [get(v) if v >= 0 else None for v in x]
        return x

    info = set()
    key = f'_{jsn.index("productType")}'
    nodes: list[dict] = [get(i) for i, v in enumerate(jsn) if isinstance(v, dict) and key in v]
    full = next(n for n in nodes if 'vendor' in n)
    series = series or utils.Series(None, (full.get('seriesTitle') or {}).get('value', ''))
    publisher = publisher or full['vendor']
    for node in nodes:
        ean = node['ean']['value']
        link = parts._replace(query=urlencode({'ean': ean}), fragment='').geturl()
        title = node['title'] or title
        format = node['productType'] or format
        isbn = ean if ISBN.fullmatch(ean) else isbn
        date = datetime.date.fromisoformat(node['publicationDate']['value'][:10])
        info.add(utils.Info(series.key, link, NAME, publisher, title, index, format, isbn, date))
    return series, info
