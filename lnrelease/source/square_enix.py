import datetime
import json
import re
import warnings

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series

NAME = 'Square Enix'

HOST = 'https://squareenixmangaandbooks.square-enix-games.com'
SERIES = re.compile('/series/')


def get_format(s: str) -> str:
    match s:
        case ('Paperback'
              | 'Trade Paperback'):
            return 'Paperback'
        case ('Hardcover'):
            return 'Hardcover'
        case ('Digital'):
            return 'Digital'
        case ('Chapters (Digital)'):
            return None
        case _:
            warnings.warn(f'Unknown SE format: {s}', RuntimeWarning)
            return None


def parse(session: Session, series: Series, link: str, index: int) -> set[Info]:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'lxml')
    jsn = json.loads(soup.find('script', type='application/ld+json').text)
    title = jsn['name']
    date = datetime.datetime.strptime(jsn['datePublished'], '%B %d, %Y').date()
    info = set()
    for i, work in enumerate(jsn['workExample']):
        format = get_format(work['bookEdition'])
        if not format:
            continue
        isbn = work['isbn'] if i == 0 else ''
        info.add(Info(series.key, link, NAME, NAME, title, index, format, isbn, date))
    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        page = session.get(f'{HOST}/en-us/series')
        soup = BeautifulSoup(page.content, 'lxml')
        lst = soup.find_all('a', href=SERIES)
        for x in lst:
            title = x.find(class_='p-1').string
            if '(Light Novel)' not in title:
                continue
            try:
                link = f'{HOST}{x["href"]}'
                page = session.get(link)
                soup = BeautifulSoup(page.content, 'lxml')
                volumes = soup.find('div', string='VOLUMES').parent.find_all('a', recursive=False)
                serie = Series(None, title)
                index = 1
                for volume in volumes:
                    if inf := parse(session, serie, f'{HOST}{volume["href"]}', index):
                        series.add(serie)
                        info.update(inf)
                        index += 1
            except Exception as e:
                warnings.warn(f'({link}): {e}', RuntimeWarning)

    return series, info
