import datetime
import json
import warnings
from dataclasses import replace
from itertools import groupby
from operator import attrgetter
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from session import Session
from store.apple import PATH, normalise
from utils import AUDIOBOOK, Info, Series

NAME = 'Apple'


def get_id(link: str) -> int:
    return int(PATH.fullmatch(urlparse(link).path).group('id'))


def read(attributes: dict[str, str], serieskey: str, publisher: str) -> Info:
    link = normalise(None, attributes['url'])
    title = attributes['name']
    isbn = attributes.get('isbn', '')
    date = datetime.date.fromisoformat(attributes['releaseDate'])
    return Info(serieskey, link, NAME, publisher, title, 0, 'Digital', isbn, date)


def parse(session: Session, series: Series | dict[int, Series], publisher: str, link: str) -> tuple[Series, set[Info]] | None:
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
            if s := series.get(int(book['id'])):
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
    audiobooks = {i for i in info if i.format in AUDIOBOOK}
    with Session() as session:
        smap = {s.key: s for s in series}
        uids = {get_id(i.link): i for i in info if i.format not in AUDIOBOOK}
        for key, group in groupby(sorted(info), attrgetter('serieskey')):
            try:
                lst = list(group)
                lst = [i for i in lst if i.format not in AUDIOBOOK]
                if len(lst) <= 1 and not any('vol' in i.title.lower() for i in lst):
                    continue
                res = parse(session, smap[key], lst[0].publisher, lst[0].link)
                uids |= {get_id(i.link): i for i in res[1]}
            except Exception as e:
                warnings.warn(f'({key}): {e}', RuntimeWarning)

        smap = {uid: smap[i.serieskey] for uid, i in uids.items()}
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
                uid = result['trackId']
                if inf := uids.get(uid):
                    title = result['trackName']
                    date = datetime.date.fromisoformat(result['releaseDate'][:10])
                    uids[uid] = replace(inf, title=title, date=date)
                elif res := parse(session, smap, 'Hanashi Media', link):
                    series.add(res[0])
                    for inf in res[1]:
                        uid = get_id(inf.link)
                        uids[uid] = inf
                        smap[uid] = res[0]
            except Exception as e:
                warnings.warn(f'({result["trackViewUrl"]}): {e}', RuntimeWarning)

    return series, set(uids.values()) | audiobooks
