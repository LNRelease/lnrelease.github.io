import datetime
import re
import warnings
from random import random

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series

NAME = 'Seven Seas Entertainment'

PAGES = re.compile(r'Page (?P<cur>\d+) of (?P<last>\d+)')
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


def parse(session: Session, link: str, series: Series) -> set[Info]:
    info = set()
    page = session.get(link, web_cache=True, ia_save=7)
    soup = BeautifulSoup(page.content, 'lxml')
    digital = soup.find(string='Early Digital:')  # assume all volumes are either digital or not
    audio = False
    index = 0
    for release in soup.find_all(class_='series-volume'):
        index += 1
        header = release.find_previous('h3', class_='header').text
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

        volume_link = release.get('href')
        title = release.h3.text
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
    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    today = datetime.date.today()

    with Session() as session:
        url = 'https://sevenseasentertainment.com/tag/light-novels/'
        while url:
            page = session.get(url, web_cache=True, ia_save=14)
            soup = BeautifulSoup(page.content, 'lxml')
            lst = soup.find_all(class_='series')
            if not lst:
                warnings.warn(f'No series found: {page.url}', RuntimeWarning)
                break
            url = soup.find(class_='nextpostslink')
            url = url.get('href') if url else None

            for a in lst:
                try:
                    link = a.get('href')
                    title = a.text
                    serie = Series(None, title)
                    prev = {i for i in info if i.serieskey == serie.key}
                    if random() > 0.5 and prev and (
                            today - max(i.date for i in prev)).days > 365:
                        continue

                    if inf := parse(session, link, serie):
                        series.add(serie)
                        info -= inf
                        info |= inf
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

    return series, info
