import datetime
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from utils import Info, Series

NAME = 'Barnes & Noble'

PATH = re.compile(r'/w/(?P<name>[\w-]+)/(?P<id>\d+)')
PUBLISHER = re.compile(r'^\s*Publisher:\s*(?P<name>.+)$')
DATE = re.compile(r'^\s*Pub\. Date:\s*(?P<date>.+)$')

FORMATS = 'https://www.barnesandnoble.com/cartridges/ProductDetailContent/ProductDetailTypes/includes/formatModal-ra.jsp'


# 'github' banned
HEADERS = {'User-Agent': ''}


def normalise(link: str) -> str | None:
    u = urlparse(link)
    if not PATH.fullmatch(u.path):
        return None
    query = urlencode([(k, v) for k, v in parse_qsl(u.query) if k == 'ean'])
    return urlunparse(('https', 'www.barnesandnoble.com', u.path, '', query, ''))


def parse(session, link: str, norm: str, *, series: Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = '') -> tuple[Series, set[Info]] | None:
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
        info.add(Info(serieskey, link, NAME, publisher, title, index, format, isbn, date))

    return series, info
