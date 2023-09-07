import datetime
import json
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from utils import Info, Series

NAME = 'Apple'

PATH = re.compile(r'/(?P<country>\w+)/(?P<format>book|audiobook)/(?:[\w-]+/)?(?P<id>id\d{10})')


def normalise(link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = f'/us/{match.group("format")}/{match.group("id")}'
    else:
        return None
    return urlunparse(('https', 'books.apple.com', path, '', '', ''))


def parse(session, link: str, norm: str, *, series: Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = '') -> tuple[Series, set[Info]] | None:
    page = session.get(norm)
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

    info = Info(serieskey, norm, NAME, publisher, title, index, format, isbn, date)
    return series, {info}
