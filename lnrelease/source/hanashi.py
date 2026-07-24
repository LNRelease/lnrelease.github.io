import datetime
import warnings
from pathlib import Path
from random import random
from urllib.parse import urlparse

import store
from session import Session
from utils import Info, Key, Series, Table

NAME = 'Hanashi Media'

PAGES = Path('hanashi.csv')


def parse(session: Session, series: Series, jsn: dict, skip: set[str], index: int) -> set[Info]:
    info = set()
    link = 'https://hanashi.media/ebooks/' + jsn['at']
    title = jsn['title']
    date = datetime.date.fromisoformat(jsn['release'][:10])
    isbn = jsn['isbn']

    urls = []
    for key, url in jsn.items():
        if not key.endswith('Link') or not url or not url.startswith('http'):
            continue
        url = session.resolve(url)
        if norm := store.normalise(session, url, resolve=True):
            urls.append([norm, url])
        elif norm is None:
            warnings.warn(f'{url} normalise failed', RuntimeWarning)

    alts = []
    force = True
    urls.sort(key=lambda x: '.amazon' in x[0])
    for norm, url in urls:
        if urlparse(norm).netloc in store.PROCESSED:
            alts.append(norm)
            continue
        res = store.parse(session, [norm, url],
                          (force or random() < 0.1) and norm not in skip,
                          series=series, publisher=NAME,
                          title=title, index=index, format='Digital')
        if res and res[1]:
            info |= res[1]
            force = False
            alts.extend(inf.link for inf in res[1])
        else:
            alts.append(norm)

    info.add(Info(series.key, link, NAME, NAME, title, index, 'Digital', isbn, date, alts))
    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Key)
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=30)
    skip = {row.key for row in pages if random() > 0.1 and row.date < cutoff}

    with Session() as session:
        serie: dict[str, tuple[Series, int]] = {}
        url = 'https://store-api.hanashi.media/series'
        for row in session.post('https://store-api.hanashi.media/explore/series').json()['data']:
            s = Series(None, row['title'])
            for entry in session.post(url, json={'at': row['at']}).json()['data']['entries']:
                serie[entry['ebookId']] = s, entry['order']
        url = 'https://store-api.hanashi.media/explore/schedule'
        for book in session.post(url).json()['data']:
            try:
                s, index = serie.get(book['id'], (Series(None, book['title']), 0))
                if inf := parse(session, s, book, skip, index):
                    series.add(s)
                    info -= inf
                    info |= inf
                    for i in inf:
                        if i.source == NAME:
                            continue
                        l = Key(i.link, i.date)
                        pages.discard(l)
                        pages.add(l)
            except Exception as e:
                warnings.warn(f'({book['at']}): {e}', RuntimeWarning)

    pages.save()
    return series, info
