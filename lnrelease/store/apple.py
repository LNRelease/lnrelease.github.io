from __future__ import annotations

import datetime
import json
import re
from urllib.parse import urlparse, urlunparse

import session
import utils
from bs4 import BeautifulSoup

NAME = 'Apple'

PATH = re.compile(r'/(?P<country>\w+)/(?P<format>book|audiobook)/(?:[\w-]+/)?(?P<id>id\d{10})')


def equal(a: str, b: str) -> bool:
    match_a = PATH.fullmatch(urlparse(a).path)
    match_b = PATH.fullmatch(urlparse(b).path)
    return (match_a and match_b
            and match_a.group('id') == match_b.group('id'))


def hash_link(link: str) -> int:
    return hash(PATH.fullmatch(urlparse(link).path).group('id'))


def normalise(session: session.Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = f'/us/{match.group("format")}/{match.group("id")}'
    else:
        return None
    return urlunparse(('https', 'books.apple.com', path, '', '', ''))


def parse(session: session.Session, links: list[str], *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    page = session.get(links[0], web_cache=True)
    soup = BeautifulSoup(page.content, 'lxml')

    serieskey = series.key if series else ''
    jsn = json.loads(soup.find('script', type='application/ld+json').text)
    publisher = publisher or jsn['publisher']
    title = title or jsn['name']
    format = format or jsn['@type']
    if format == 'Book':
        format = 'Digital'
    isbn = isbn or jsn.get('isbn', '')
    date = datetime.date.fromisoformat(jsn['datePublished'][:10])

    info = utils.Info(serieskey, links[0], NAME, publisher, title, index, format, isbn, date)
    return series, {info}
