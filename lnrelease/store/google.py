from __future__ import annotations

import datetime
import json
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from session import Session
import utils
from bs4 import BeautifulSoup

NAME = 'Google'
SALT = hash(NAME)

PATH = re.compile(r'/store/(?P<format>books|audiobooks)/details(?:/.*)?')
SCRIPT = re.compile(r'"Published on"')
DATA = re.compile(r'data:(?P<data>\[.+\])')


def equal(a: str, b: str) -> bool:
    id_a = next((v for k, v in parse_qsl(urlparse(a).query) if k == 'id'), '')
    id_b = next((v for k, v in parse_qsl(urlparse(b).query) if k == 'id'), '')
    return id_a == id_b


def hash_link(link: str) -> int:
    return SALT + hash(next((v for k, v in parse_qsl(urlparse(link).query) if k == 'id'), ''))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = f'/store/{match.group("format")}/details'
    else:
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(u.query) if k == 'id'])
    return urlunparse(('https', u.netloc, path, '', query, ''))


def find_detail(detail: str, lst: list) -> str:
    if len(lst) == 2 and lst[0] == detail:
        lst = lst[1]
        while len(lst) == 1:
            lst = lst[0]
        return lst[1]

    for item in lst:
        if isinstance(item, list):
            if x := find_detail(detail, item):
                return x


def parse(session: Session, links: list[str], *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    page = session.get(links[0], ia=True)
    soup = BeautifulSoup(page.content, 'lxml')

    serieskey = series.key if series else ''
    jsn = json.loads(soup.find('script', type='application/ld+json').text)
    title = title or jsn['name']
    work = jsn['workExample']
    format = format or work['@type']
    if format == 'Book':
        format = 'Digital'
    isbn = isbn or work.get('isbn', '')
    date = datetime.date.fromisoformat(work['datePublished'])

    info = utils.Info(serieskey, links[0], NAME, publisher, title, index, format, isbn, date)
    return series, {info}
