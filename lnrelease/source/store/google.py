import datetime
import json
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from utils import Info, Series

NAME = 'Google'

PATH = re.compile(r'/store/(?P<format>books|audiobooks)/details(?:/.*)?')
SCRIPT = re.compile(r'"Published on"')
DATA = re.compile(r'data:(?P<data>\[.+\])')


def normalise(link: str) -> str | None:
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


def parse(session, link: str, norm: str, *, series: Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = '') -> tuple[Series, set[Info]] | None:
    page = session.get(norm)
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

    info = Info(serieskey, norm, NAME, publisher, title, index, format, isbn, date)
    return series, {info}
