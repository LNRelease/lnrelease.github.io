import datetime
import re
import warnings

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series

NAME = 'Seven Seas Entertainment'

PAGES = re.compile(r'Page (?P<cur>\d+) of (?P<last>\d+)')


def parse(session: Session, link: str, series_title: str) -> tuple[Series, set[Info]]:
    series = Series(None, series_title)
    info = set()

    page = session.get(link)
    soup = BeautifulSoup(page.content, 'lxml')
    digital = soup.find(string='Early Digital:')  # assume all volumes are either digital or not
    for index, release in enumerate(soup.find_all(class_='series-volume'), start=1):
        header = release.find_previous_sibling('h3').text
        format = release.find('b', string='Format:')
        if (format and 'Light Novel' not in format.next_sibling):
            continue

        a = release.h3.a
        volume_link = a.get('href')
        title = a.text
        date = release.find('b', string='Release Date')
        physical_date = datetime.datetime.strptime(date.next_sibling.strip(' :'), '%Y/%m/%d').date()
        if date := release.find('b', string='Early Digital:'):
            digital_date = datetime.datetime.strptime(date.next_sibling.strip(), '%Y/%m/%d').date()
        elif digital and header == 'VOLUMES':
            digital_date = physical_date
        else:
            digital_date = None
        isbn = ''
        if header == 'VOLUMES':
            isbn = release.find('b', string='ISBN:').next_sibling.strip()
            if isbn == '(digital-only single)':
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
        base = r'https://sevenseasentertainment.com/tag/light-novels/'
        path = 'page/{}/'
        for i in range(1, 100):
            url = base + ('' if i == 1 else path.format(i))
            page = session.get(url)
            soup = BeautifulSoup(page.content, 'lxml')

            for serie in soup.find_all(id='series'):
                try:
                    a = serie.h3.a
                    link = a.get('href')
                    title = a.text
                    res = parse(session, link, title)
                    if len(res[1]) > 0:
                        series.add(res[0])
                        info -= res[1]
                        info |= res[1]
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if (not (pages := soup.find(class_='pages'))
                    or (match := PAGES.fullmatch(pages.text))
                    and match.group('cur') == match.group('last')):
                break
    return series, info
