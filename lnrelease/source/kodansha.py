import datetime
import re
import warnings
from urllib.parse import urlparse

import store
from session import Session
from utils import FORMATS, Info, Series, find_series

NAME = 'Kodansha'

FORMAT = re.compile(rf'(?P<title>.+) \((?P<format>{"|".join(FORMATS)})\)')


def parse(session: Session, series: Series, link: str, format: str = '') -> set[Info]:
    info = set()

    page = session.get(link)
    jsn = page.json()['response']

    slug = jsn['readableUrl'] if 'readableUrl' in jsn else jsn['id']
    url = f'https://kodansha.us/product/{slug}'
    title = jsn['name']
    readable = jsn['readable']
    isbn = readable['isbn']
    date = datetime.date.fromisoformat(readable['printReleaseDate'][:10])
    format = format or readable['coverType']
    info.add(Info(series.key, url, NAME, NAME, title, 0, format, isbn, date))

    if eisbn := readable['eisbn']:
        edate = datetime.date.fromisoformat(readable['digitalReleaseDate'][:10])
        info.add(Info(series.key, url, NAME, NAME, title, 0, 'Digital', eisbn, edate))

    for group in jsn['assetLinkGroups']:
        format = group['name']
        if format in ('Digital', 'Print'):
            continue
        alts = []
        for alt in group['assetLinks']:
            norm = store.normalise(session, alt['url'], resolve=True)
            if not norm:
                continue
            if urlparse(norm).netloc in store.PROCESSED:
                alts.append(norm)
            else:
                res = store.parse(session, [norm], series=series, publisher=NAME, title=title, format=format)
                if res and res[1]:
                    info |= res[1]
                    alts.extend(inf.link for inf in res[1])
                else:
                    alts.append(norm)
        info.add(Info(series.key, url, NAME, NAME, title, 0, format, '', None, alts))

    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        params = {'subCategory': 'Book',
                  'fromIndex': '0',
                  'count': '1000'}
        page = session.get('https://api.kodansha.us/discover/v2', params=params)
        jsn = page.json()
        for book in jsn['response']:
            content = book['content']
            if 'seriesName' not in content:
                continue

            title = content['seriesName']
            format = ''
            if match := FORMAT.fullmatch(title):
                title = match.group('title')
                format = match.group('format')
            serie = find_series(title, series)

            if serie:
                link = f'https://api.kodansha.us/product/{content["id"]}'
                try:
                    info.update(parse(session, serie, link, format))
                except Exception as e:
                    warnings.warn(f'({link}): {e}', RuntimeWarning)

    return series, info
