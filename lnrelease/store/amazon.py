from __future__ import annotations

import datetime
import re
import warnings
from urllib.parse import urlparse, urlunparse

import utils
from bs4 import BeautifulSoup
from session import REQUEST_STATS, Session

NAME = 'Amazon'
SALT = hash(NAME)

PATH = re.compile(r'(?:/.+)?/(?:dp/(?:product/)?|gp/.+/)(?P<asin>\w{10})(?:/.*)?')
ISBN_13 = re.compile(r'ISBN-13')
ISBN = re.compile(r'^\s*978[-\d]{10,}\s*$')
DATE = re.compile(r'^(?:Publication date|Audible release date)$')
PRODUCT = re.compile(r'^\s*Product (?:details|information)\s*$')
PUBLISHER = re.compile(r'Publisher')
DETAILS = re.compile(r'^[\s\W]*(?P<publisher>[\s\w]+?)(?:;[\s\w]+ edition)? \((?P<date>.+)\)\s*$')

YEAR = re.compile(r'\d{4}')
MONTH = re.compile(r'[^\W\d]+')
DAY = re.compile(r'\d{1,2}')

MONTHS = {
    'eme': 1, 'gen': 1, 'jan': 1, 'sty': 1,
    'feb': 2, 'fev': 2, 'lut': 2,
    'maa': 3, 'mac': 3, 'mar': 3, 'mrt': 3,
    'abr': 4, 'apr': 4, 'avr': 4, 'kwi': 4,
    'mag': 5, 'mai': 5, 'maj': 5, 'may': 5, 'mei': 5,
    'cze': 6, 'giu': 6, 'jun': 6,
    'jul': 7, 'lip': 7, 'lug': 7,
    'ago': 8, 'aou': 8, 'aug': 8, 'sie': 8,
    'sep': 9, 'set': 9, 'wrz': 9,
    'oct': 10, 'okt': 10, 'ott': 10, 'out': 10, 'paz': 10,
    'lis': 11, 'nov': 11,
    'dec': 12, 'des': 12, 'dez': 12, 'dic': 12, 'gru': 12,
}


def equal(a: str, b: str) -> bool:
    match_a = PATH.fullmatch(urlparse(a).path)
    match_b = PATH.fullmatch(urlparse(b).path)
    return (match_a and match_b
            and match_a.group('asin') == match_b.group('asin'))


def hash_link(link: str) -> int:
    return SALT + hash(PATH.fullmatch(urlparse(link).path).group('asin'))


def normalise(session: Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = '/dp/' + match.group('asin')
    else:
        return None
    return urlunparse(('https', 'www.amazon.com', path, '', '', ''))


def get_attr(soup: BeautifulSoup, attr: str) -> str:
    div = soup.find(id=attr)
    if div:
        return div.find('div', class_='rpi-attribute-value').text.strip()
    return ''


def strpdate(link: str, s: str) -> datetime.date:
    if not s:
        warnings.warn(f'No date found: {link}', RuntimeWarning)
        return None

    try:
        return datetime.datetime.strptime(s, r'%Y/%m/%d').date()
    except ValueError:
        pass

    try:
        if match := YEAR.search(s):
            year = match.group(0)
            s = s.replace(year, '')
            year = int(year)
        if match := MONTH.search(s):
            month = match.group(0)
            s = s.replace(month, '')
            month = MONTHS[utils.clean_str(month[:3])]
        if match := DAY.search(s):
            day = match.group(0)
            s = s.replace(day, '')
            day = int(day)

        return datetime.date(year, month, day)
    except Exception as e:
        warnings.warn(f'Error parsing date: {s} ({link}): {e}', RuntimeWarning)
        return None


def parse(session: Session, links: list[str], *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    session.set_retry(total=2, status_forcelist={500, 502, 503, 504})
    stats = REQUEST_STATS['www.amazon.com']
    for link in {urlparse(link)
                 ._replace(params='', query='', fragment='')
                 .geturl(): None for link in links[1:]}:
        stats.cache += 1
        page = session.google_cache(link, timeout=10)
        if page.status_code != 404:
            break
    else:
        page = session.bing_cache(links[0], timeout=10)
    session.set_retry()

    if not page:
        return None
    soup = BeautifulSoup(page.content, 'lxml')

    if not series:
        series_title = ''
        if attr := soup.find(id='rpi-attribute-book_details-series'):
            series_title = attr.a.text
        series = utils.Series(None, series_title)

    isbn = isbn or get_attr(soup, 'rpi-attribute-book_details-isbn13')
    if (not isbn
        and (entry := soup.find(string=ISBN_13))
            and (value := entry.find_next(string=ISBN))):
        isbn = value.text

    date = (get_attr(soup, 'rpi-attribute-book_details-publication_date')
            or get_attr(soup, 'rpi-attribute-audiobook_details-release-date'))
    if not date and (span := soup.find('span', string=DATE)):
        div = span.find_parent('div', class_='rpi-attribute-content')
        date = div.find('div', class_='rpi-attribute-value').text.strip()
    if ((product := soup.find(string=PRODUCT))
        and (entry := product.find_next(string=PUBLISHER))
        and (value := entry.find_parent(lambda x: x.name in ('li', 'tr'))
                           .find(string=DETAILS))):
        match = DETAILS.fullmatch(value.text)
        publisher = publisher or match.group('publisher')
        date = date or match.group('date')
    date = strpdate(page.url, date)
    if not date:
        return None

    info = utils.Info(series.key, links[0], NAME, publisher, title, index, format, isbn, date)
    return series, {info}
