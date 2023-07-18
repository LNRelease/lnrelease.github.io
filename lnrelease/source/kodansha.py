import datetime
import re
import warnings

from utils import FORMATS, Info, Series, Session

NAME = 'Kodansha'

BRACKETS = re.compile(f'(?P<title>.+) \((?P<format>{"|".join(FORMATS)})\)')


def parse(session: Session, series: Series, link: str, format: str = '') -> set[Info]:
    info = set()

    page = session.get(link)
    jsn = page.json()

    for index, book in enumerate(jsn, start=1):
        slug = book['readableUrl'] if 'readableUrl' in book else book['id']
        url = f'https://kodansha.us/product/{slug}'
        title = book['name']
        readable = book['readable']
        isbn = readable['isbn']
        date = datetime.date.fromisoformat(readable['releaseDate'][:10])
        format = format or readable['coverType']
        info.add(Info(series.key, url, NAME, NAME, title, index, format, isbn, date))

        if eisbn := readable['eisbn']:
            if 'digitalReleaseDate' in readable:
                date = datetime.date.fromisoformat(readable['digitalReleaseDate'][:10])
            info.add(Info(series.key, url, NAME, NAME, title, index, 'Digital', eisbn, date))

    return info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        params = {'subCategory': 'Book',
                  'includeSeries': 'True',
                  'fromIndex': '0',
                  'count': '1000'}
        page = session.get('https://api.kodansha.us/discover/v2', params=params)
        jsn = page.json()
        for serie in jsn['response']:
            content = serie['content']
            title = content['title']
            link = f'https://api.kodansha.us/product/forSeries/{content["id"]}'
            format = ''
            if match := BRACKETS.fullmatch(title):
                title = match.group('title')
                format = match.group('format')
            s = Series(None, title)
            if s in series:  # filter for light novels
                try:
                    info |= parse(session, s, link, format)
                except Exception as e:
                    warnings.warn(f'{link}: {e}', RuntimeWarning)

    return series, info
