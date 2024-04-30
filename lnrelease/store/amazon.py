from __future__ import annotations

import datetime
import re
import warnings
from urllib.parse import urlparse, urlunparse

import session
import utils
from bs4 import BeautifulSoup

NAME = 'Amazon'

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
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
}

NETLOCS = {
    'www.amazon.ca',
    'www.amazon.co.uk',
    'www.amazon.com',
    'www.amazon.com.au',
}


def equal(a: str, b: str) -> bool:
    ua = urlparse(a)
    ub = urlparse(b)
    if ua.netloc.removeprefix('www.') != ub.netloc.removeprefix('www.'):
        return False

    match_a = PATH.fullmatch(ua.path)
    match_b = PATH.fullmatch(ub.path)
    return (match_a and match_b
            and match_a.group('asin') == match_b.group('asin'))


def hash_link(link: str) -> int:
    u = urlparse(link)
    netloc = u.netloc.removeprefix('www.')
    match = PATH.fullmatch(u.path)
    return hash(netloc + match.group('asin'))


def normalise(session: session.Session, link: str) -> str | None:
    u = urlparse(link)
    if match := PATH.fullmatch(u.path):
        path = '/dp/' + match.group('asin')
    else:
        return None
    netloc = u.netloc
    if not netloc.startswith('www.'):
        if netloc.startswith('amazon.'):
            netloc = f'www.{netloc}'
        else:
            return None
    if u.netloc not in NETLOCS:
        netloc = 'www.amazon.com'
    return urlunparse(('https', netloc, path, '', '', ''))


def get_attr(soup: BeautifulSoup, attr: str) -> str:
    div = soup.find(id=attr)
    if div:
        return div.find('div', class_='rpi-attribute-value').text.strip()
    return ''


def strpdate(link: str, s: str) -> datetime.date:
    try:
        if match := YEAR.search(s):
            year = match.group(0)
            s = s.replace(year, '')
            year = int(year)
        if match := MONTH.search(s):
            month = match.group(0)
            s = s.replace(month, '')
            month = MONTHS[month[:3].lower()]
        if match := DAY.search(s):
            day = match.group(0)
            s = s.replace(day, '')
            day = int(day)

        return datetime.date(year, month, day)
    except Exception as e:
        warnings.warn(f'Error parsing date: {s} ({link}): {e}', RuntimeWarning)
        return None


def parse(session: session.Session, link: str, norm: str, *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    u = urlparse(link)
    link = (u._replace(params='', query='', fragment='').geturl()
            if u.netloc in NETLOCS else norm)
    page = session.get(link, direct=False, web_cache=True)
    if page.status_code == 404 and link != norm:
        page = session.get(norm, direct=False, web_cache=True)
    if page.status_code == 404:
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
    date = strpdate(link, date)
    if not date:
        return None

    info = utils.Info(series.key, norm, NAME, publisher, title, index, format, isbn, date)
    return series, {info}
