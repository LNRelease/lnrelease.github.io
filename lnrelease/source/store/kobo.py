import datetime
import json
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from utils import Info, Series

NAME = 'Kobo'

PATH = re.compile(r'(?:/\w+/\w+)?/(?P<format>ebook|audiobook)/(?P<name>[^/]+)(?:/.+)?')
INDEX = re.compile(r'Book (?P<index>\d+) - ')


def normalise(link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = f'/us/en/{match.group("format")}/{match.group("name")}'
    else:
        return None
    return urlunparse(('https', 'www.kobo.com', path, '', '', ''))


def parse(session, link: str, norm: str, *, series: Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = '') -> tuple[Series, set[Info]] | None:
    page = session.get(norm)
    soup = BeautifulSoup(page.content, 'lxml')

    about = soup.select_one('div.about > p.series > span.series')
    index = index or INDEX.fullmatch(about.find('span', class_='sequenced-name-prefix').text).group('index')
    series = series or Series(None, about.a.text)

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

    info = Info(series.key, norm, NAME, publisher, title, index, format, isbn, date)
    return series, {info}
