import datetime
import re
import warnings

from bs4 import BeautifulSoup
from session import Session
from utils import Info, Series

NAME = 'TOKYOPOP'

ISBN = re.compile(r'.*/products/(?P<isbn>\d{13})_.+')
API = 'https://v3-static.supadu.io/tokyo-pop-us/products/{}.json'


def read(jsn: dict, series: Series, index: int) -> Info | None:
    isbn = jsn['isbn13']
    link = f'https://tokyopop.com/products/{isbn}_{jsn["seo"]}'
    title = jsn['title']
    format = jsn['formats'][0]['format']['name']
    date = datetime.date.fromisoformat(jsn['date']['date'][:10])
    return Info(series.key, link, NAME, NAME, title, index, format, isbn, date)


def parse(session: Session, link: str) -> tuple[Series, set[Info]] | None:
    info = set()
    page = session.get(API.format(link))
    jsn = page.json()
    if s := jsn['series']['series']:
        series = Series(None, s[0]['name'])
        index = int(s[0]['number_in_series'])
    else:
        series = Series(None, jsn['title'])
        index = 1
    info.add(read(jsn, series, index))
    for f in jsn['formats']:
        isbn = f['isbn']
        if link == isbn:
            continue
        page = session.get(API.format(isbn))
        info.add(read(page.json(), series, index))
    return series, info


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        site = 'https://tokyopop.com/collections/novels'
        params = {'sort_by': 'created-descending'}
        for i in range(1, limit + 1):
            params['page'] = i
            page = session.get(site, params=params, ia=True)
            soup = BeautifulSoup(page.content, 'lxml')

            results = soup.find(id='CollectionAjaxContent').find_all(
                'a', href=lambda x: x and x.startswith('/collections/novels/products/'))
            for a in results:
                title = a.find(class_='grid-product__title').text
                if not title.endswith('Light Novel)'):
                    continue
                try:
                    isbn = ISBN.fullmatch(a.get('href')).group('isbn')
                    res = parse(session, isbn)
                    if res:
                        series.add(res[0])
                        info -= res[1]
                        info |= res[1]
                except Exception as e:
                    warnings.warn(f'{isbn}: {e}', RuntimeWarning)

            if not soup.select_one('.pagination > .next') or not results:
                break
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 5)
