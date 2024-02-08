import datetime
import re
import warnings
from urllib.parse import urlencode, urljoin

from session import Session
from utils import FORMATS, Info, Series

NAME = 'Right Stuf'


ISBN = re.compile(r'\d{13}')
NOVEL = re.compile(r'(?<!\bThe) Novel\b')
FORMAT = re.compile(rf'(?P<title>.+) \((?P<format>{"|".join(FORMATS)})\)')
OMNIBUS = re.compile(r'(?:contains|collects)(?: novel)? volumes (?P<volume>\d+(?:\.\d)?-\d+(?:\.\d)?)')
START = re.compile(r'(?P<start>.+?) (?:Omnibus |Collector\'s Edition |Volume )+\d+')

PUBLISHERS = {
    'ACONYTE': '',
    'AIRSHIP': 'Seven Seas Entertainment',
    'ALGONQUIN YOUNG READERS': '',
    'ATRIA BOOKS': '',
    'CROSS INFINITE WORLD': 'Cross Infinite World',
    'DARK HORSE': 'Dark Horse',
    'DARK HORSE MANGA': 'Dark Horse',
    'DEL REY': '',
    'DELACORTE BOOKS FOR YOUNG READERS': '',
    'DIGITAL MANGA PUBLISHING': 'Digital Manga Publishing',
    'EREWHON BOOKS': '',
    'J-NOVEL CLUB': 'J-Novel Club',
    'JNC': 'J-Novel Club',
    'J-NOVEL HEART': 'J-Novel Club',
    'KNOPF PUBLISHERS': '',
    'KODANSHA COMICS': '',
    'MAD NORWEGIAN PRESS': '',
    'NET COMICS': '',
    'ONE PEACE': 'One Peace Books',
    'PENGUIN WORKSHOP': '',
    'PIED PIPER': '',
    'QUIRK BOOKS': '',
    'SEVEN SEAS': 'Seven Seas Entertainment',
    'SHAMBHALA': '',
    'SQUARE ENIX BOOKS': 'Square Enix Books',
    'STEAMSHIP': 'Seven Seas Entertainment',
    'STONE BRIDGE PRESS': '',
    'TENTAI BOOKS': 'Tentai Books',
    'TITAN BOOKS': '',
    'TOKYOPOP': '',
    'TUTTLE': '',
    'UDON ENTERTAINMENT': '',
    'VERTICAL': 'Kodansha',
    'VIZ BOOKS': 'VIZ Media',
    'YAOI PRESS': '',
    'YEN ON': 'Yen Press',
}


def get_publisher(pub: str) -> str:
    try:
        pub = PUBLISHERS[pub]
        return pub
    except KeyError:
        warnings.warn(f'Unknown publisher: {pub}', RuntimeWarning)
        return None


def parse(jsn: dict) -> tuple[Series, Info] | None:
    series_title = jsn['custitem_rs_series']
    link = urljoin('https://legacy.rightstufanime.com/', jsn['urlcomponent'])

    publisher = get_publisher(jsn['custitem_rs_publisher'])
    isbn = jsn['itemid']
    if not publisher or not ISBN.fullmatch(isbn):
        return None

    title = NOVEL.sub('', jsn['storedisplayname2'])
    format = 'Paperback'
    if match := FORMAT.fullmatch(title):  # extract format if present
        title = match.group('title')
        format = match.group('format')
    if ((vol := OMNIBUS.search(jsn['storedetaileddescription']))
            and (start := START.fullmatch(title))):  # rename omnibus volume
        title = f'{start.group("start")} Volume {vol.group("volume")}'

    date = datetime.datetime.strptime(jsn['custitem_rs_release_date'], '%m/%d/%Y').date()

    if series_title == '&nbsp;':
        series_title = title
    series = Series(None, series_title)
    info = Info(series.key, link, NAME, publisher, title, 0, format, isbn, date)
    return series, info


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    isbns: dict[str, Info] = {inf.isbn: inf for inf in info}

    with Session() as session:
        params = {'country': 'US',
                  'currency': 'USD',
                  'language': 'en',
                  'custitem_rs_web_class': 'Novels',
                  'custitem_damaged_type': 'New',
                  'offset': '0',
                  'fieldset': 'details',
                  'limit': '100',
                  'sort': 'custitem_rs_release_date:desc'}
        link = f'https://legacy.rightstufanime.com/api/items?{urlencode(params)}'
        while link:
            page = session.get(link)

            jsn = page.json()
            for item in jsn['items']:
                res = parse(item)
                if res:
                    serie, inf = res
                    series.add(serie)
                    isbns[inf.isbn] = inf

            for l in jsn['links']:
                if l['rel'] == 'next':
                    link = l['href']
                    break
            else:
                link = ''

    return series, set(isbns.values())
