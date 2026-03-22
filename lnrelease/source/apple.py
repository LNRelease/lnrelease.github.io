import datetime
import json
import warnings
from itertools import groupby
from operator import attrgetter

from bs4 import BeautifulSoup
from session import Session
from store.apple import normalise
from utils import AUDIOBOOK, Info, Series

NAME = 'Apple'


def read(attributes: dict[str, str], serieskey: str, publisher: str) -> Info:
    link = normalise(None, attributes['url'])
    title = attributes['name']
    isbn = attributes.get('isbn', '')
    date = datetime.date.fromisoformat(attributes['releaseDate'])
    return Info(serieskey, link, NAME, publisher, title, 0, 'Digital', isbn, date)


def parse(session: Session, series: Series, lst: list[Info]) -> set[Info]:
    lst = [inf for inf in lst if inf.format not in AUDIOBOOK]
    if len(lst) <= 1 and not any('vol' in inf.title.lower() for inf in lst):
        return set()

    info = set()
    publisher = lst[0].publisher
    page = session.get(lst[0].link, params={'see-all': 'other-books-in-book-series'})
    soup = BeautifulSoup(page.content, 'lxml')
    data = json.loads(soup.select_one('#shoebox-media-api-cache-amp-books').text)
    jsn = json.loads(list(data.values())[0])
    info.add(read(jsn['d'][0]['attributes'], series.key, publisher))
    for book in jsn['d'][0]['relationships']['other-books-in-book-series']['data']:
        info.add(read(book['attributes'], series.key, publisher))

    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    smap = {s.key: s for s in series}
    with Session() as session:
        for key, group in groupby(sorted(info), attrgetter('serieskey')):
            try:
                inf = parse(session, smap[key], list(group))
                info -= inf
                info |= inf
            except Exception as e:
                warnings.warn(f'({key}): {e}', RuntimeWarning)

    return set(), info
