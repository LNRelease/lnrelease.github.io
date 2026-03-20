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
    format = 'Audiobook' if format == 'Other audio format' else format
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
        sitemap = session.get('https://tokyopop.com/sitemap.xml', cf=True, ia=True)
        for loc in BeautifulSoup(sitemap.content, 'xml').select('sitemap > loc'):
            if 'sitemap_products' not in loc.text:
                continue

            page = session.get(loc.text, cf=True, ia=True)
            soup = BeautifulSoup(page.content, 'xml')
            for loc in soup.select('urlset > url > loc'):
                if '-light-novel' not in loc.text:
                    continue

                try:
                    isbn = ISBN.fullmatch(loc.text).group('isbn')
                    if res := parse(session, isbn):
                        series.add(res[0])
                        info -= res[1]
                        info |= res[1]
                except Exception as e:
                    warnings.warn(f'{isbn}: {e}', RuntimeWarning)

    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info)
