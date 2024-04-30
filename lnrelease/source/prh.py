import datetime
import warnings
from urllib.parse import urljoin

from session import Session
from utils import FORMATS, Info, Series, find_series

NAME = 'Penguin Random House'


def scrape_full(series: set[Series], info: set[Info], limit: int = 1000) -> tuple[set[Series], set[Info]]:
    with Session() as session:
        params = {'sort': 'onsale',
                  'dir': 'desc',
                  'rows': limit,
                  'zoom': 'https://api.penguinrandomhouse.com/title/titles/definition',
                  'imprintCode': 'VT'}
        page = session.get('https://www.penguinrandomhouse.ca/api/enhanced/works', params=params)

        jsn = page.json()
        for book in jsn['data']:
            title = book['title'].replace(' (paperback)', '')
            serie = find_series(title, series)
            if not serie:
                continue

            for variant in book['_embeds'][0]['titles']:
                isbn = variant['isbn']
                date = datetime.date.fromisoformat(variant['onsale'])
                url = urljoin('https://www.penguinrandomhouse.com/', variant['seoFriendlyUrl'])
                format = variant['format']['description']
                if format == 'Boxed Set':
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

                inf = Info(serie.key, url, NAME, 'Kodansha', title, 0, format, isbn, date)
                info.discard(inf)
                info.add(inf)
    return series, info


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info, 100)
