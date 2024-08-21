import datetime
import re
import warnings

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series

NAME = 'Seven Seas Entertainment'

PAGES = re.compile(r'Page (?P<cur>\d+) of (?P<last>\d+)')
NON_FORMATS = ('Manga', 'Novel')
FORMATS = ('Light Novel', 'Reference Guide')
DATES = (r'%Y-%m-%d', r'%B %d, %Y', r'%Y/%m/%d')


def strpdate(s: str) -> datetime.date:
    for d in DATES:
        try:
            return datetime.datetime.strptime(s, d).date()
        except ValueError:
            pass
    raise ValueError(f"Invalid time data '{s}'")


def parse(session: Session, link: str, series_title: str) -> tuple[Series, set[Info]]:
    series = Series(None, series_title)
    info = set()

    page = session.get(link, web_cache=True)
    soup = BeautifulSoup(page.content, 'lxml')
    digital = soup.find(string='Early Digital:')  # assume all volumes are either digital or not
    audio = False
    index = 0
    for release in soup.find_all(class_='series-volume'):
        index += 1
        header = release.find_previous_sibling('h3').text
        if format := release.find('b', string='Format:'):
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

        a = release.h3.a
        volume_link = a.get('href')
        title = a.text
        date = release.find('b', string='Release Date')
        physical_date = strpdate(date.next_sibling.strip(' \t\n\r\v\f:'))
        if date := release.find('b', string='Early Digital:'):
            digital_date = strpdate(date.next_sibling.strip())
        elif digital and header == 'VOLUMES':
            digital_date = physical_date
        else:
            digital_date = None
        isbn = ''
        if header == 'VOLUMES':
            isbn = release.find('b', string='ISBN:').next_sibling.strip()
            if 'digital' in isbn:
                digital_date = physical_date
                physical_date = None
                isbn = ''

        if physical_date:
            format = 'Physical' if header == 'VOLUMES' else 'Audiobook'
            info.add(Info(series.key, volume_link, NAME, NAME, title, index, format, isbn, physical_date))
        if digital_date:
            info.add(Info(series.key, volume_link, NAME, NAME, title, index, 'Digital', '', digital_date))
    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        base = 'https://sevenseasentertainment.com/tag/light-novels/'
        path = 'page/{}/'
        for i in range(1, 100):
            url = base + ('' if i == 1 else path.format(i))
            page = session.get(url, web_cache=True)
            soup = BeautifulSoup(page.content, 'lxml')

            for serie in soup.find_all(class_='series'):
                try:
                    a = serie.h3.a
                    link = a.get('href')
                    title = a.text
                    serie, inf = parse(session, link, title)
                    if inf:
                        series.add(serie)
                        info -= {i for i in info if i.serieskey == serie.key}
                        info |= inf
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if (not (pages := soup.find(class_='pages'))
                    or (match := PAGES.fullmatch(pages.text))
                    and match.group('cur') == match.group('last')):
                break
    return series, info
