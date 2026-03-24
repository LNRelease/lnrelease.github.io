import datetime
import re
import warnings
from urllib.parse import urljoin

from session import Session
from utils import FORMATS, Info, Series

NAME = 'Crunchyroll'


ISBN = re.compile(r'\d{13}')
NOVEL = re.compile(r'(?<!\bThe) Novel\b')
FORMAT = re.compile(rf'(?P<title>.+) \((?P<format>{"|".join(FORMATS)})\)')
OMNIBUS = re.compile(r'(?:contains|collects)(?: novel)? volumes (?P<volume>\d+(?:\.\d)?-\d+(?:\.\d)?)')
START = re.compile(r'(?P<start>.+?)(?: Omnibus\b| Collector\'s Edition\b| Volume\b)+(?: \d+)?')

PUBLISHERS = {
    'AIRSHIP': 'Seven Seas Entertainment',
    'CROSS INFINITE WORLD': 'Cross Infinite World',
    'DARK HORSE': 'Dark Horse',
    'DARK HORSE MANGA': 'Dark Horse',
    'DIGITAL MANGA PUBLISHING': 'Digital Manga Publishing',
    'GHOST SHIP': 'Seven Seas Entertainment',
    'IZE PRESS': '',
    'JNC': 'J-Novel Club',
    'LOVELOVE': 'TOKYOPOP',
    'ONE PEACE': 'One Peace Books',
    'SEVEN SEAS': 'Seven Seas Entertainment',
    'SQUARE ENIX BOOKS': 'Square Enix',
    'STEAMSHIP': 'Seven Seas Entertainment',
    'TENTAI BOOKS': 'Tentai Books',
    'TOKYOPOP': 'TOKYOPOP',
    'VERTICAL': 'Kodansha',
    'VIZ BOOKS': 'VIZ Media',
    'YEN ON': 'Yen Press',
    'YEN PRESS': 'Yen Press',
}


def auth(session: Session) -> dict[str, str]:
    data = {'grant_type': 'client_credentials', 'channel_id': 'CrunchyrollUS', 'dnt': 'true'}
    page = session.post('https://store.crunchyroll.com/mobify/slas/private/shopper/auth/v1/organizations/f_ecom_bdgc_prd/oauth2/token', data=data)
    token = page.json()['access_token']
    return {'Authorization': f'Bearer {token}'}


def get_publisher(pub: str) -> str:
    try:
        pub = PUBLISHERS[pub]
        return pub
    except KeyError:
        warnings.warn(f'Unknown publisher: {pub}', RuntimeWarning)
        return None


def parse(session: Session, jsn: dict) -> tuple[Series, Info] | None:
    product = jsn['representedProduct']
    publisher = get_publisher(product['c_publisher'])
    isbn = product['id']
    if not publisher or not ISBN.fullmatch(isbn):
        return None
    path = f'{product["c_urlName"]}-{isbn}.html'
    link = urljoin('https://store.crunchyroll.com/products/', path)

    title = NOVEL.sub('', jsn['productName'])
    format = 'Paperback'
    if match := FORMAT.fullmatch(title):  # extract format if present
        title = match.group('title')
        format = match.group('format')
    date = datetime.datetime.fromisoformat(product['c_streetDate']).date()
    if 'Omnibus' in title:
        page = session.get(link)
        vol = OMNIBUS.search(page.text)
        start = START.fullmatch(title)
        if vol and start:
            title = f'{start.group("start")} Volume {vol.group("volume")}'

    series_title = jsn['c_brand']
    if series_title == '&nbsp;':
        series_title = title
    series = Series(None, series_title)
    info = Info(series.key, link, NAME, publisher, title, 0, format, isbn, date)
    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    isbns: dict[str, Info] = {inf.isbn: inf for inf in info}

    with Session() as session:
        link = 'https://store.crunchyroll.com/mobify/proxy/api/search/shopper-search/v1/organizations/f_ecom_bdgc_prd/product-search'
        headers = auth(session)
        params = {
            'siteId': 'CrunchyrollUS',
            'q': '',
            'refine': 'cgid=light-novels',
            'sort': 'New-to-Old',
            'currency': 'USD',
            'locale': 'en-US',
            'expand': 'variations,represented_products,custom_properties',
            'perPricebook': 'true',
            'allVariationProperties': 'true',
            'offset': 0,
            'limit': 200,
        }
        total = 1
        while params['offset'] < total:
            try:
                for _ in range(2):
                    page = session.get(link, headers=headers, params=params)
                    if page.status_code == 401:
                        headers = auth(session)
                        continue
                    break
                jsn = page.json()
                for item in jsn['hits']:
                    res = parse(session, item)
                    if res:
                        serie, inf = res
                        series.add(serie)
                        isbns[inf.isbn] = inf
                params['offset'] += len(jsn['hits'])
                total = jsn['total']
            except Exception as e:
                warnings.warn(f'({link}): {e}', RuntimeWarning)
                break

    return series, set(isbns.values())
