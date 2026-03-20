import datetime
import warnings
from urllib.parse import urljoin

from session import Session
from utils import FORMATS, Info, Series, find_series

NAME = 'Penguin Random House'
NON_FORMATS = ('Boxed Set', 'Non-traditional book')


def scrape_imprint(session: Session, series: set[Series], info: set[Info],
                   imprint: str, publisher: str, limit: int) -> None:
    params = {'sort': 'onsale',
              'dir': 'desc',
              'rows': limit,
              'zoom': 'https://api.penguinrandomhouse.com/title/titles/definition',
              'imprintCode': imprint}
    page = session.get('https://www.penguinrandomhouse.ca/api/enhanced/works', params=params)

    jsn = page.json()
    for book in jsn['data']:
        title = book['title'].replace(' (paperback)', '')
        serie = find_series(title, series) or Series(None, title)

        for variant in book['_embeds'][0]['titles']:
            if variant['graphicCategory'] != 'Light Novel':
                continue
            isbn = variant['isbn']
            date = datetime.date.fromisoformat(variant['onsale'])
            url = urljoin('https://www.penguinrandomhouse.com/', variant['seoFriendlyUrl'])
            format = variant['format']['description']
            if format in NON_FORMATS:
                continue
            elif format not in FORMATS:
                for f in FORMATS:
                    if f in format:
                        format = f
                        break
                else:
                    warnings.warn(f'Unknown PRH format: {format}', RuntimeWarning)
                    continue
            if language := variant['language'] != 'E':
                warnings.warn(f'Non-E PRH language: {language}', RuntimeWarning)
                continue

            inf = Info(serie.key, url, NAME, publisher, title, 0, format, isbn, date)
            info.discard(inf)
            info.add(inf)


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        scrape_imprint(session, series, info, 'VT', 'Kodansha', limit)
        scrape_imprint(session, series, info, '209', 'TOKYOPOP', limit)
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 100)
