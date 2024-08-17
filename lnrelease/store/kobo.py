from __future__ import annotations

import datetime
import json
import re
from urllib.parse import urlparse, urlunparse

import utils
from bs4 import BeautifulSoup
from session import CHROME, Session

NAME = 'Kobo'
SALT = hash(NAME)

PATH = re.compile(r'(?:/\w+/\w+)?/(?P<format>ebook|audiobook)/(?P<name>[^/]+)(?:/.*)?')
INDEX = re.compile(r'Book (?P<index>\d+) - ')


def equal(a: str, b: str) -> bool:
    match_a = PATH.fullmatch(urlparse(a).path)
    match_b = PATH.fullmatch(urlparse(b).path)
    return (match_a and match_b
            and match_a.group('format') == match_b.group('format')
            and match_a.group('name') == match_b.group('name'))


def hash_link(link: str) -> int:
    match = PATH.fullmatch(urlparse(link).path)
    return SALT + hash(match.group('format') + match.group('name'))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = f'/ww/en/{match.group("format")}/{match.group("name")}'
    else:
        return None
    return urlunparse(('https', 'www.kobo.com', path, '', '', ''))


def parse(session: Session, links: list[str], *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    page = session.get(links[0], web_cache=True, headers=CHROME, timeout=10)
    soup = BeautifulSoup(page.content, 'lxml')

    about = soup.select_one('div.about > p.series > span.series')
    index = index or INDEX.fullmatch(about.find('span', class_='sequenced-name-prefix').text).group('index')
    series = series or utils.Series(None, about.a.text)

    jsn = json.loads(soup.select_one('div.RatingAndReviewWidget > div.kobo-gizmo')['data-kobo-gizmo-config'])
    jsn = json.loads(jsn['googleBook'])
    publisher = publisher or jsn['publisher']['name']
    work = jsn['workExample']
    title = title or work['name']
    format = format or work['@type']
    if format == 'Book':
        format = 'Digital'
    isbn = isbn or work.get('isbn', '')
    date = datetime.date.fromisoformat(work['datePublished'][:10])

    info = utils.Info(series.key, links[0], NAME, publisher, title, index, format, isbn, date)
    return series, {info}
