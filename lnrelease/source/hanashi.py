import datetime
import re
import warnings
from pathlib import Path
from random import random
from urllib.parse import urljoin, urlparse

import store
from bs4 import BeautifulSoup
from session import Session
from utils import Info, Key, Series, Table

NAME = 'Hanashi Media'

PAGES = Path('hanashi.csv')
LINK = re.compile(r'/light-novels/[\w-]+')


def read(session: Session, jsn: dict, series: Series, link: str,
         volumes: dict[float, int], skip: set[str]) -> tuple[int, set[Info]]:
    info = set()
    data = jsn['nodes'][2]['data']
    vol = data[data[1]['number']]
    title = f'{series.title} Volume {vol}'
    index = volumes.pop(vol, 0)
    date = datetime.date.fromisoformat(data[data[1]['release']][1][:10])

    urls = []
    for url in data:
        if not isinstance(url, str) or not url.startswith('http'):
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

    info.add(Info(series.key, link, NAME, NAME, title, index, 'Digital', '', date, alts))
    return vol, info


def parse(session: Session, link: str, skip: set[str]) -> tuple[Series, set[Info]]:
    page = session.get(f'{link}/__data.json')
    jsn = page.json()
    data = jsn['nodes'][1]['data']
    series_title = data[data[1]['title']]
    volumes = {data[data[x]['number']]: i for i, x in enumerate(data[data[1]['Volume']])}
    series = Series(None, series_title)

    vol, info = read(session, jsn, series, link, volumes, skip)
    path = link.rsplit('/', 1)[0]
    for vol in list(volumes):
        try:
            page = session.get(f'{path}/{vol}/__data.json')
            info |= read(session, page.json(), series, f'{path}/{vol}', volumes, skip)[1]
        except Exception as e:
            warnings.warn(f'({link}): {e}', RuntimeWarning)

    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    pages = Table(PAGES, Key)
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=30)
    skip = {row.key for row in pages if random() > 0.1 and row.date < cutoff}

    with Session() as session:
        page = session.get('https://hanashi.media/light-novels')
        soup = BeautifulSoup(page.content, 'lxml')
        links = filter(LINK.match, {a.get('href', '') for a in soup.select('a')})
        for link in links:
            try:
                link = urljoin(page.url, link)
                s, inf = parse(session, link, skip)

                if inf:
                    series.add(s)
                    info -= {i for i in info if i.serieskey == s.key} | inf
                    info |= inf
                    for i in inf:
                        if i.source == NAME:
                            continue
                        l = Key(i.link, i.date)
                        pages.discard(l)
                        pages.add(l)
            except Exception as e:
                warnings.warn(f'({link}): {e}', RuntimeWarning)

    pages.save()
    return series, info
