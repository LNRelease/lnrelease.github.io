import datetime
import re
import warnings

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

    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    isbns: dict[str, Series] = {inf.isbn: inf for inf in info}

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
                    for inf in parse(session, serie, link, format):
                        isbns[inf.isbn] = inf
                except Exception as e:
                    warnings.warn(f'({link}): {e}', RuntimeWarning)

    info = set()
    for inf in isbns.values():
        if inf in info:
            warnings.warn(f'Kodansha duplicate: {inf}', RuntimeWarning)
        info.add(inf)
    return series, info
