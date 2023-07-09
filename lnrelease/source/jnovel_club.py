import datetime
import warnings

from utils import Format, Info, Series, Session

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
        page = session.get(f'https://labs.j-novel.club/app/v1/series/{slug}/volumes', params=params)
        jsn = page.json()

        for book in jsn['volumes']:
            if book['label'] == 'J-Novel Pulp':
                break

            title = book['title']
            date = datetime.datetime.fromisoformat(book['publishing'][:10]).date()
            index = book['number']
            link = f'https://j-novel.club/series/{slug}#volume-{index}'
            info.add(Info(serieskey, link, NAME, NAME, title, index, Format.DIGITAL, None, date))
            if 'physicalPublishing' in book:
                date = datetime.datetime.fromisoformat(book['physicalPublishing'][:10]).date()
                info.add(Info(serieskey, link, NAME, NAME, title, index, Format.PHYSICAL, None, date))

        if jsn['pagination']['lastPage']:
            break
        params['skip'] = jsn['pagination']['skip'] + jsn['pagination']['limit']
    return info


def scrape_full() -> tuple[set[Series], set[Info]]:
    # everything because events only has digital releases
    series = set()
    info = set()

    with Session() as session:
        params = {
            'format': 'json',
            'limit': '500',
            'skip': '0'
        }
        while True:
            page = session.get('https://labs.j-novel.club/app/v1/series', params=params)
            jsn = page.json()
            for serie in jsn['series']:
                if (serie['type'] == 'NOVEL'
                        and 'j-novel pulp' not in serie['tags']
                        and 'pulp' not in serie['tags']):
                    s = Series(None, serie['title'])
                    series.add(s)
                    try:
                        info |= parse(session, s.key, serie['slug'])
                    except Exception as e:
                        warnings.warn(f'{serie["slug"]}: {e}', RuntimeWarning)

            if jsn['pagination']['lastPage']:
                break
            params['skip'] = jsn['pagination']['skip'] + jsn['pagination']['limit']
    return series, info


def scrape() -> tuple[set[Series], set[Info]]:
    # get recentish series
    series = set()
    info = set()

    with Session() as session:
        page = session.get('https://labs.j-novel.club/app/v1/events?format=json')
        jsn = page.json()
        for event in jsn['events']:
            serie = event['serie']
            if (serie['type'] == 'NOVEL'
                    and 'j-novel pulp' not in serie['tags']
                    and 'pulp' not in serie['tags']):
                s = Series(None, serie['title'])
                series.add(s)
                info |= parse(session, s.key, serie['slug'])
    return series, info
