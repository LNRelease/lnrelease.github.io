from __future__ import annotations

import datetime
import json
import re
import warnings
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import utils
from bs4 import BeautifulSoup
from session import Session

NAME = 'Barnes & Noble'
SALT = hash(NAME)

PATH = re.compile(r'/w/(?P<name>[\w-]+)/(?P<id>\d+)')
PUBLISHER = re.compile(r'^\s*Publisher:\s*(?P<name>.+)$')
DATE = re.compile(r'^\s*Pub\. Date:\s*(?P<date>.+)$')


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
    soup = BeautifulSoup(page.content, 'lxml')

    jsn = json.loads(soup.find('script', type='application/ld+json').text)['@graph'][0]
    variant = next(x for x in jsn['hasVariant'] if x['sku'] == ean)
    serieskey = series.key if series else utils.clean_str()
    link = variant['url']
    publisher = publisher or jsn['publisher']
    title = title or jsn['name']
    match variant['bookFormat'].removeprefix('https://schema.org/'):
        case 'AudiobookFormat':
            format = 'Audiobook'
        case 'EBook':
            format = 'Digital'
        case 'Hardcover':
            format = 'Hardcover'
        case 'Paperback':
            format = 'Paperback'
        case _:
            warnings.warn(f'Unknown format: {variant["bookFormat"]} ({links[0]})')
            return None
    date = datetime.date.fromisoformat(jsn['datePublished'])

    info = utils.Info(serieskey, link, NAME, publisher, title, index, format, isbn, date)
    return series, {info}
