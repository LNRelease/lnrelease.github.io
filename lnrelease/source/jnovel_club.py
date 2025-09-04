import datetime
import warnings
from random import random

from session import Session
from utils import Info, Series

# thanks for api
NAME = 'J-Novel Club'


def parse(session: Session, serieskey: str, slug: str) -> set[Info]:
    info = set()

    params = {
        'format': 'json',
        'limit': '500',
        'skip': '0'
    }
    while True:
        page = session.get(f'https://labs.j-novel.club/app/v2/series/{slug}/volumes', params=params)
        jsn = page.json()

        for index, book in enumerate(jsn['volumes'], start=1):
            if book['label'] == 'J-Novel Pulp':
                break

            title = book['title']
            date = datetime.date.fromisoformat(book['publishing'][:10])
            link = f'https://j-novel.club/series/{slug}#volume-{index}'
            info.add(Info(serieskey, link, NAME, NAME, title, index, 'Digital', None, date))
            if 'physicalPublishing' in book:
                date = datetime.date.fromisoformat(book['physicalPublishing'][:10])
                info.add(Info(serieskey, link, NAME, NAME, title, index, 'Physical', None, date))

        if jsn['pagination']['lastPage']:
            break
        params['skip'] = jsn['pagination']['skip'] + jsn['pagination']['limit']
    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    # everything because events only has digital releases
    today = datetime.date.today()

    with Session() as session:
        params = {
            'format': 'json',
            'limit': '500',
            'skip': '0'
        }
        while True:
            page = session.get('https://labs.j-novel.club/app/v2/series', params=params)
            jsn = page.json()
            for serie in jsn['series']:
                if (serie['type'] == 'NOVEL'
                        and 'j-novel pulp' not in serie['tags']
                        and 'pulp' not in serie['tags']):
                    s = Series(None, serie['title'])
                    series.add(s)
                    prev = {i for i in info if i.serieskey == s.key}
                    if random() > 0.5 and prev and (
                            today - max(i.date for i in prev)).days > 365:
                        continue
                    try:
                        inf = parse(session, s.key, serie['slug'])
                        info -= inf
                        info |= inf
                    except Exception as e:
                        warnings.warn(f'{serie["slug"]}: {e}', RuntimeWarning)

            if jsn['pagination']['lastPage']:
                break
            params['skip'] = jsn['pagination']['skip'] + jsn['pagination']['limit']
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    # get recentish series
    with Session() as session:
        page = session.get('https://labs.j-novel.club/app/v2/events?format=json')
        jsn = page.json()
        for event in jsn['events']:
            serie = event['serie']
            if (serie['type'] == 'NOVEL'
                    and 'j-novel pulp' not in serie['tags']
                    and 'pulp' not in serie['tags']):
                s = Series(None, serie['title'])
                series.add(s)
                inf = parse(session, s.key, serie['slug'])
                info -= inf
                info |= inf
    return series, info
