import datetime
import re
import warnings
from html import unescape
from random import random

from bs4 import BeautifulSoup
from session import CHROME, Session
from utils import PHYSICAL, Info, Series

NAME = 'Seven Seas Entertainment'

PAGES = re.compile(r'Page (?P<cur>\d+) of (?P<last>\d+)')
OMNIBUS = re.compile(rf'(?P<name>.+?)(?: \w+ Edition \d+)? \(Light Novel\)\s*\(Vol\. (?P<volume>\d+(?:\.\d)?-\d+(?:\.\d)?) ?(?P<format>{"|".join(PHYSICAL)})? Omnibus\)')
NON_FORMATS = ('Manga', 'Novel')
FORMATS = ('Light Novel', 'Reference Guide')
DATES = (r'%b %d, %Y', r'%Y-%m-%d', r'%B %d, %Y', r'%Y/%m/%d')


def strpdate(s: str) -> datetime.date:
    for d in DATES:
        try:
            return datetime.datetime.strptime(s, d).date()
        except ValueError:
            pass
    raise ValueError(f"Invalid time data '{s}'")


def parse(session: Session, link: str, series: Series, refresh: int) -> set[Info]:
    info = set()
    page = session.get(link, cf=True, ia=True, refresh=refresh, headers=CHROME)
    soup = BeautifulSoup(page.content, 'lxml')
    digital = soup.find(string='Early Digital:')  # assume all volumes are either digital or not
    audio = False
    index = 0
    for release in soup.find_all(class_='series-volume'):
        index += 1
        header = release.find_previous('h3', class_='header').text
        title = release.h3.text
        if ' (Light Novel)' in title:
            pass
        elif format := release.find('b', string='Format:'):
            format = format.next_sibling.strip()
            if format in NON_FORMATS:
                continue
            if format not in FORMATS:
                warnings.warn(f'Unknown SS format: {format}', RuntimeWarning)
                continue
        elif not audio and header == 'AUDIOBOOKS':
            if not info:
                break
            audio = True
            index = 1

        volume_link = release.get('href') or release.a['href']
        date = release.find('b', string='Release Date')
        physical_date = strpdate(date.next_sibling.strip(' \t\n\r\v\f:'))
        if date := release.find('b', string='Early Digital:'):
            digital_date = strpdate(date.next_sibling.strip())
        elif digital and header == 'VOLUMES':
            digital_date = physical_date
        else:
            digital_date = None
        isbn = ''
        format = 'Physical' if header == 'VOLUMES' else 'Audiobook'
        if header == 'VOLUMES':
            isbn = release.find('b', string='ISBN:').next_sibling.strip()
            if 'digital' in isbn:
                digital_date = physical_date
                physical_date = None
                isbn = ''
            elif match := OMNIBUS.fullmatch(title):
                title = f'{match.group("name")} Vol. {match.group("volume")}'
                format = match.group('format') or 'Physical'
                digital_date = None

        if physical_date:
            info.add(Info(series.key, volume_link, NAME, NAME, title, index, format, isbn, physical_date))
        if digital_date:
            info.add(Info(series.key, volume_link, NAME, NAME, title, index, 'Digital', '', digital_date))
    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        links: dict[str, tuple[str, datetime.date]] = {}
        kwargs = {
            'cf': True,
            'ia': True,
            'refresh': 2,
            'headers': CHROME,
        }
        url = 'https://sevenseasentertainment.com/wp-json/wp/v2/series'
        params = {
            'tags[0]': 43,
            'orderby': 'modified',
            'per_page': 100,
            'page': 1,
        }
        while True:
            page = session.get(url, params=params, **kwargs)
            jsn = page.json()
            for serie in jsn:
                link = serie['link']
                title = unescape(serie['title']['rendered'])
                modified = datetime.date.fromisoformat(serie['modified_gmt'][:10])
                links.setdefault(link, (title, modified))
            if len(jsn) != params['per_page']:
                break
            params['page'] += 1

        page = session.get('https://sevenseasentertainment.com/series-list/', **kwargs)
        soup = BeautifulSoup(page.content, 'lxml')
        lst = soup.select('tr#volumes > td:first-child > a')
        if not lst:
            warnings.warn(f'No series found: {page.url}', RuntimeWarning)
        for a in lst:
            link = a.get('href')
            if link.endswith('-light-novel/'):
                links.setdefault(link, (a.text, None))

        today = datetime.date.today()
        for link, (title, modified) in links.items():
            try:
                serie = Series(None, title)
                if modified is None:
                    prev = {i for i in info if i.serieskey == serie.key}
                    old = bool(prev) and (today - max(i.date for i in prev)).days > 365
                    if old and random() > 0.2:
                        continue
                    refresh = 7 if old else 2
                else:
                    days = (today - modified).days
                    if days < 2:
                        refresh = 0
                    elif days < 30:
                        refresh = 2
                    elif random() > 0.1:
                        continue
                    else:
                        refresh = 7

                if inf := parse(session, link, serie, refresh):
                    series.add(serie)
                    info -= inf
                    info |= inf
            except Exception as e:
                warnings.warn(f'({link}): {e}', RuntimeWarning)
    return series, info
