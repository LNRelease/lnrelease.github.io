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


def parse(session: Session, series: Series | dict[str, Series], publisher: str, link: str) -> tuple[Series, set[Info]] | None:
    info = set()
    page = session.get(link, params={'see-all': 'other-books-in-book-series'})
    soup = BeautifulSoup(page.content, 'lxml')
    data = json.loads(soup.select_one('#shoebox-media-api-cache-amp-books').text)
    jsn = json.loads(list(data.values())[0])
    item = jsn['d'][0]['attributes']
    others = jsn['d'][0]['relationships']['other-books-in-book-series']['data']

    if isinstance(series, dict):
        if publisher not in item['publisher']:
            warnings.warn(f'Unknown Apple publisher: {item["publisher"]}')
            return None
        for book in others:
            link = normalise(None, book['attributes']['url'])
            if s := series.get(link):
                series = s
                break
        else:
            s = item.get('seriesInfo', {}).get('seriesName')
            series = Series(None, s or item['name'])
    info.add(read(item, series.key, publisher))
    for book in others:
        info.add(read(book['attributes'], series.key, publisher))

    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    smap = {s.key: s for s in series}
    with Session() as session:
        for key, group in groupby(sorted(info), attrgetter('serieskey')):
            try:
                lst = list(group)
                lst = [inf for inf in lst if inf.format not in AUDIOBOOK]
                if len(lst) <= 1 and not any('vol' in inf.title.lower() for inf in lst):
                    continue
                res = parse(session, smap[key], lst[0].publisher, lst[0].link)
                info -= res[1]
                info |= res[1]
            except Exception as e:
                warnings.warn(f'({key}): {e}', RuntimeWarning)

        links = {i.link: smap[i.serieskey] for i in info}
        params = {
            'term': '"Hanashi Media"',
            'country': 'US',
            'media': 'ebook',
            'limit': '200',
        }
        page = session.get('https://itunes.apple.com/search', params=params)
        for result in page.json()['results']:
            try:
                link = normalise(None, result['trackViewUrl'])
                if link in links:
                    continue
                if res := parse(session, links, 'Hanashi Media', link):
                    series.add(res[0])
                    for inf in res[1]:
                        info.add(inf)
                        links[inf.link] = res[0]
            except Exception as e:
                warnings.warn(f'({result["trackViewUrl"]}): {e}', RuntimeWarning)

    return series, info
