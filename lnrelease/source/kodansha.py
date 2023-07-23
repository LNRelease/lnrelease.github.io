import datetime
import re
import warnings

from utils import FORMATS, Info, Series, Session

NAME = 'Kodansha'

FORMAT = re.compile(f'(?P<title>.+) \((?P<format>{"|".join(FORMATS)})\)')


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
            serie = Series(None, title)

            if serie in series:  # filter for light novels
                link = f'https://api.kodansha.us/product/{content["id"]}'
                try:
                    for inf in parse(session, serie, link, format):
                        isbns[inf.isbn] = inf
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

    return series, set(isbns.values())
