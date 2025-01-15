from __future__ import annotations

import datetime
import re
import warnings
from urllib.parse import urlparse, urlunparse

import utils
from bs4 import BeautifulSoup
from session import CHROME, REQUEST_STATS, Session

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
MONTH = re.compile(
    r'\b(?:(?P<_1>1月|1월|ene|enero|gen|gennaio|jan|janeiro|januar|januari|january|janv|janvier|led|leden|ledna|oca|ocak|sty|styczeń|stycznia|ינואר|ינו׳|يناير|一月)'
    r'|(?P<_2>2月|2월|feb|febbraio|febrero|februar|februari|february|fev|fevereiro|févr|février|lut|lutego|luty|úno|únor|února|şub|şubat|פברואר|פבר׳|فبراير|二月)'
    r'|(?P<_3>3月|3월|bře|březen|března|maart|mar|marca|march|mars|mart|marts|marzec|marzo|março|mrt|mär|märz|מרץ|مارس|三月)'
    r'|(?P<_4>4月|4월|abr|abril|apr|april|aprile|avr|avril|dub|duben|dubna|kwi|kwiecień|kwietnia|nis|nisan|אפריל|אפר׳|أبريل|四月)'
    r'|(?P<_5>5月|5월|kvě|květen|května|mag|maggio|mai|maio|maj|maja|may|mayo|mayıs|mei|מאי|مايو|五月)'
    r'|(?P<_6>6月|6월|cze|czerwca|czerwiec|giu|giugno|haz|haziran|juin|jun|june|junho|juni|junio|červen|června|čvn|יוני|يونيو|六月)'
    r'|(?P<_7>7月|7월|juil|juillet|jul|julho|juli|julio|july|lip|lipca|lipiec|lug|luglio|tem|temmuz|července|červenec|čvc|יולי|يوليو|七月)'
    r'|(?P<_8>8月|8월|ago|agosto|août|aug|august|augustus|ağu|ağustos|sie|sierpień|sierpnia|srp|srpen|srpna|אוגוסט|אוג׳|أغسطس|八月)'
    r'|(?P<_9>9月|9월|eyl|eylül|sep|sept|september|septembre|septiembre|set|setembro|settembre|wrz|wrzesień|września|zář|září|ספטמבר|ספט׳|سبتمبر|九月)'
    r'|(?P<_10>10月|10월|eki|ekim|oct|october|octobre|octubre|okt|oktober|ott|ottobre|out|outubro|paź|październik|października|říj|říjen|října|אוקטובר|אוק׳|أكتوبر|十月)'
    r'|(?P<_11>11月|11월|kas|kasım|lis|listopad|listopada|listopadu|nov|november|novembre|novembro|noviembre|נובמבר|נוב׳|نوفمبر|十一月)'
    r'|(?P<_12>12月|12월|ara|aralık|dec|december|dez|dezember|dezembro|dic|dicembre|diciembre|déc|décembre|gru|grudnia|grudzień|pro|prosince|prosinec|דצמבר|דצמ׳|ديسمبر|十二月))\b',
    flags=re.IGNORECASE,
)
DAY = re.compile(r'\d{1,2}')


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


def strpdate(s: str) -> datetime.date | None:
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
            s = s.replace(match[0], '')
            month = match.lastindex
        if match := DAY.search(s):
            day = match.group(0)
            s = s.replace(day, '')
            day = int(day)

        return datetime.date(year, month, day)
    except NameError:
        return None


def parse(session: Session, links: list[str], *,
          series: utils.Series = None, publisher: str = '', title: str = '',
          index: int = 0, format: str = '', isbn: str = ''
          ) -> tuple[utils.Series, set[utils.Info]] | None:
    REQUEST_STATS['www.amazon.com'].cache += 1
    page = session.cf_search(links[0], refresh=30)
    if not page or b'"/errors/validateCaptcha"' in page.content:
        page = session.cf_create(links[0])
    if not page or b'"/errors/validateCaptcha"' in page.content:
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
    if not date:
        warnings.warn(f'No date found: {links[0]}')
        return None
    date = strpdate(date)
    if not date:
        warnings.warn(f'Error parsing date: {date} ({links[0]})')
        return None

    info = utils.Info(series.key, links[0], NAME, publisher, title, index, format, isbn, date)
    return series, {info}
