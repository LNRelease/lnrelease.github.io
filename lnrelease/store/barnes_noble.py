from __future__ import annotations

import datetime
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import utils
from bs4 import BeautifulSoup
from session import CHROME, Session

NAME = 'Barnes & Noble'
SALT = hash(NAME)

PATH = re.compile(r'/w/(?P<name>[\w-]+)/(?P<id>\d+)')
PUBLISHER = re.compile(r'^\s*Publisher:\s*(?P<name>.+)$')
DATE = re.compile(r'^\s*Pub\. Date:\s*(?P<date>.+)$')

FORMATS = 'https://www.barnesandnoble.com/cartridges/ProductDetailContent/ProductDetailTypes/includes/formatModal-ra.jsp'


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
        res = session.resolve(link, force=True, headers=CHROME)
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
    u = urlparse(links[0])
    match = PATH.fullmatch(u.path)
    if not match:
        return None
    ean = next((v for k, v in parse_qsl(u.query) if k == 'ean'), '')
    id = match.group('id')
    page = session.get(FORMATS, params={'workId': id}, headers=CHROME)
    soup = BeautifulSoup(page.content, 'lxml')

    serieskey = series.key if series else ''
    if h3 := soup.find('h3', class_='all-formats-text'):
        title = h3.text
    info = set()
    found = False
    for li in soup.select('div[role="tablist"] > ul > li'):
        link = urljoin('https://www.barnesandnoble.com/', li.a['href'])
        found |= ean == next((v for k, v in parse_qsl(urlparse(link).query) if k == 'ean'), '')
        format = li.parent['data-format-type']
        publisher = publisher or PUBLISHER.fullmatch(li.find(string=PUBLISHER).text).group('name')
        date = DATE.fullmatch(li.find(string=DATE).text).group('date')
        date = datetime.datetime.strptime(date, '%m/%d/%Y').date()
        info.add(utils.Info(serieskey, link, NAME, publisher, title, index, format, isbn, date))

    if not found:
        link = session.resolve(links[0], force=True, headers=CHROME)
        if links[0] != link:
            info |= parse(session, [link],
                          series=series, publisher=publisher,
                          title=title, index=index, format=format)[1]

    return series, info
