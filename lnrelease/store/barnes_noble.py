from __future__ import annotations

import datetime
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import session
import utils
from bs4 import BeautifulSoup

NAME = 'Barnes & Noble'

PATH = re.compile(r'/w/(?P<name>[\w-]+)/(?P<id>\d+)')
PUBLISHER = re.compile(r'^\s*Publisher:\s*(?P<name>.+)$')
DATE = re.compile(r'^\s*Pub\. Date:\s*(?P<date>.+)$')

FORMATS = 'https://www.barnesandnoble.com/cartridges/ProductDetailContent/ProductDetailTypes/includes/formatModal-ra.jsp'


# 'github' banned
HEADERS = {'User-Agent': ''}


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
    return hash(ean or match.group('id'))


def normalise(session: session.Session, link: str) -> str | None:
    u = urlparse(link)
    if not PATH.fullmatch(u.path):
        res = session.resolve(link, force=True, headers=HEADERS)
        if res != link:
            return normalise(session, res)
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(u.query) if k == 'ean'])
    return urlunparse(('https', 'www.barnesandnoble.com', u.path, '', query, ''))


def parse(session: session.Session, link: str, norm: str, *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    id = PATH.fullmatch(urlparse(norm).path).group('id')
    page = session.get(FORMATS, params={'workId': id}, headers=HEADERS)
    soup = BeautifulSoup(page.content, 'lxml')

    serieskey = series.key if series else ''
    soup.find('')
    title = title or soup.find('h3', class_='all-formats-text').text
    info = set()
    for div in soup.find_all('div', role='tablist'):
        link = urljoin('https://www.barnesandnoble.com/', div.a['href'])
        format = div.ul['data-format-type']
        publisher = publisher or PUBLISHER.fullmatch(div.find(string=PUBLISHER).text).group('name')
        date = DATE.fullmatch(div.find(string=DATE).text).group('date')
        date = datetime.datetime.strptime(date, '%m/%d/%Y').date()
        info.add(utils.Info(serieskey, link, NAME, publisher, title, index, format, isbn, date))

    return series, info
