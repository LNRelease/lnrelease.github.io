import datetime
import re
import warnings

from bs4 import BeautifulSoup
from utils import Format, Info, Series, Session

NAME = 'Seven Seas Entertainment'

PAGES = re.compile(r'Page (?P<cur>\d+) of (?P<last>\d+)')


def parse(session: Session, link: str, series_title: str) -> tuple[Series, set[Info]]:
    series = Series(None, series_title)
    info = set()

    page = session.get(link)
    soup = BeautifulSoup(page.content, 'html.parser')
    digital = soup.find(string='Early Digital:')  # assume all volumes are either digital or not
    for index, release in enumerate(soup.find_all(class_='series-volume'), start=1):
        if not (format := release.find('b', string='Format:')) or format.next_sibling != ' Light Novel':
            continue

        a = release.h3.a
        volume_link = a.get('href')
        title = a.text
        date = release.find('b', string='Release Date')
        physical_date = datetime.datetime.strptime(date.next_sibling, ': %Y/%m/%d').date()
        if date := release.find('b', text='Early Digital:'):
            digital_date = datetime.datetime.strptime(date.next_sibling, ' %Y/%m/%d').date()
        elif digital:
            digital_date = physical_date
        else:
            digital_date = None
        isbn = release.find('b', string='ISBN:').next_sibling.strip()
        if isbn == '(digital-only single)':
            digital_date = physical_date
            physical_date = None
            isbn = None

        if physical_date:
            info.add(Info(series.key, volume_link, NAME, NAME, title, index, Format.PHYSICAL, isbn, physical_date))
        if digital_date:
            info.add(Info(series.key, volume_link, NAME, NAME, title, index, Format.DIGITAL, None, digital_date))
    return series, info


def scrape_full() -> tuple[set[Series], set[Info]]:
    series: set[Series] = set()
    info: set[Info] = set()

    with Session() as session:
        tag = r'https://sevenseasentertainment.com/tag/light-novels/page/{}/'
        for i in range(1, 100):
            page = session.get(tag.format(i))
            soup = BeautifulSoup(page.content, 'html.parser')

            for serie in soup.find_all(id='series'):
                try:
                    a = serie.h3.a
                    link = a.get('href')
                    title = a.text
                    res = parse(session, link, title)
                    if len(res[1]) > 1:
                        series.add(res[0])
                        info.update(res[1])
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if (not (pages := soup.find(class_='pages'))
                    or (match := PAGES.fullmatch(pages.text))
                    and match.group('cur') == match.group('last')):
                break

    return series, info
