import datetime
import json
import warnings
from pathlib import Path
from random import random

from bs4 import BeautifulSoup
from utils import Info, Link, Series, Session, Table

NAME = 'BOOK☆WALKER'

PAGES = Path('book_walker.csv')


def parse(session: Session, link: str) -> tuple[Series, Info] | None:
    page = session.get(link)
    soup = BeautifulSoup(page.content, 'html.parser')

    jsn = json.loads(soup.find('script', type='application/ld+json').text)
    publisher = jsn['brand']['name']
    title = jsn['name']
    index = 0
    for index, vol in enumerate(soup.select('h3:-soup-contains("Read all volumes") + div a'), start=1):
        if link == vol.get('href'):
            break
    isbn = jsn['isbn']
    date = datetime.datetime.strptime(jsn['productionDate'], '%B %d, %Y (%I:%M %p) JST').date()
    series_title = soup.select_one('div.product-detail-inner th:-soup-contains("Series Title") + td a')
    if series_title:
        series_title = series_title.text
    else:
        series_title = title
    if series_title.startswith('<Partial release>') or series_title.endswith('(light novel serial)'):
        return None

    series = Series(None, series_title)
    info = Info(series.key, link, NAME, publisher, title, index, 'Digital', isbn, date)
    return series, info


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    limit += 1
    pages = Table(PAGES, Link)
    today = datetime.date.today()
    cutoff = today.replace(year=today.year - 1)
    # no date = not light novel
    skip = {row.link for row in pages if random() < 0.9 and (not row.date or row.date < cutoff)}

    with Session() as session:
        session.cookies.set('glSafeSearch', '1')
        params = {
            'np': '1',  # by individual books
            'order': 'release'
        }
        for i in range(1, limit):
            params['page'] = i
            page = session.get('https://global.bookwalker.jp/categories/3/', params=params)
            soup = BeautifulSoup(page.content, 'html.parser')

            for book in soup.find_all(class_='a-tile-ttl'):
                a = book.a
                link = a.get('href')
                title = a.get('title')
                if title.startswith('BOOK☆WALKER Exclusive: ') or link in skip:
                    continue

                try:
                    res = parse(session, link)
                    if res:
                        series.add(res[0])
                        info.discard(res[1])
                        info.add(res[1])
                        date = res[1].date
                    else:
                        date = None
                    l = Link(link, date)
                    pages.discard(l)
                    pages.add(l)
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

            if soup.select_one('.pager-area ul li:last-child').get('class')[0] == 'on':
                break

    pages.save()
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 5)
