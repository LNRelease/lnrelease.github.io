import datetime
import json
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from utils import Info, Series

NAME = 'Audible'

PATH = re.compile(r'/pd/(?P<name>[^/]+)/(?P<asin>\w{10})(?:/.*)?')
BOOK = re.compile(r',?\s*Book (?P<index>\d+)\s*')


def normalise(link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = f'/pd/{match.group("name")}/{match.group("asin")}'
    else:
        return None
    netloc = u.netloc
    if not u.netloc.startswith('www'):
        if netloc.split('.')[0] == 'audible':
            netloc = 'www.' + netloc
        else:
            return None
    return urlunparse(('https', netloc, path, '', '', ''))


def parse(session, link: str, norm: str, *, series: Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = '') -> tuple[Series, set[Info]] | None:
    page = session.get(norm)
    soup = BeautifulSoup(page.content, 'lxml')

    jsn = json.loads(soup.find(id='bottom-0').find('script', type='application/ld+json').text)[0]
    publisher = publisher or jsn['publisher']

    title = title or jsn['name']
    format = format or 'Audiobook'
    isbn = isbn or jsn.get('isbn', '')
    date = datetime.date.fromisoformat(jsn['datePublished'])

    label = soup.find(class_='seriesLabel')
    if label:
        a = label.find_all('a')[-1]
        index = index or BOOK.fullmatch(a.next_sibling.text).group('index')
        series_title = a.text

    series = series or Series(None, series_title)
    info = Info(series.key, norm, NAME, publisher, title, index, format, isbn, date)
    return series, {info}
