import datetime
import re
import sqlite3
import unicodedata
import warnings
from itertools import groupby
from urllib.parse import urlparse

import zstandard as zstd
from session import Session
from utils import Info, Series

NAME = 'BookWalker'

PATH = re.compile(r'/(?:volume|chapter|series)/(?P<id>[A-Z\d]{12})/[\w-]+')
ISBN = re.compile(r'97[89][-\d]{10,}')
SLUG = re.compile(r'[^\w -]')
HYPENS = re.compile(r'[ -]+')
PUBLISHERS = {
    'Cross Infinite World': 'Cross Infinite World',
    'Crossed Hearts': '',
    'Dark Horse Comics': 'Dark Horse',
    'Graphic Audio': 'Dark Horse',
    'Denshobato': '',
    'Dreamscape Lore': 'J-Novel Club',
    'J-Novel Club': 'J-Novel Club',
    'JNC Audio': 'J-Novel Club',
    'Tantor Media': 'J-Novel Club',
    'Kodansha': 'Kodansha',
    'One Peace Books': 'One Peace Books',
    'One Peace Books (Audiobooks)': 'One Peace Books',
    'Seven Seas Entertainment': 'Seven Seas Entertainment',
    'Seven Seas Siren': 'Seven Seas Entertainment',
    'Tokyopop': 'TOKYOPOP',
    'VIZ Media': 'VIZ Media',
    'Ize Press': '',
    'JY': 'Yen Press',
    'Yen Press': 'Yen Press',
}


def get_id(link: str) -> str:
    return PATH.fullmatch(urlparse(link).path).group('id')


def get_link(uid: str, title: str) -> str:
    slug = unicodedata.normalize('NFKD', title)
    slug = SLUG.sub('', slug).lower().strip('-')
    slug = HYPENS.sub('-', slug)
    return f'https://bookwalker.com/volume/{uid}/{slug}'


def get_format(format: int) -> str:
    match format:
        case 2:
            return 'Digital'
        case 4:
            return 'Audiobook'
        case _:
            warnings.warn(f'Unknown format: {format}', RuntimeWarning)
            return None


def scrape_full(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    uids = {get_id(inf.link): inf for inf in info}
    with Session() as session:
        page = session.get('https://static.bookwalker.com/data/bkwk-db.sqlite.zst')
    data = zstd.decompress(page.content)
    con = sqlite3.connect(':memory:')
    con.deserialize(data)
    cur = con.cursor()

    cur.execute('SELECT id, display_title FROM series')
    names = dict(cur.fetchall())
    cur.execute('SELECT labels.id, publishers.display_name FROM labels'
                ' JOIN publishers ON labels.publisher_id = publishers.id')
    labels = {i: PUBLISHERS.get(n) for i, n in cur.fetchall()}
    cur.execute('SELECT product_id, external_id FROM product_external_ids WHERE type IN (7, 3) ORDER BY type')
    isbns = {pid: isbn for pid, isbn in cur.fetchall() if ISBN.fullmatch(isbn)}

    cur.execute('SELECT id, content_id, series_id, content_type, display_title, label_id, on_sale_at'
                ' FROM products WHERE content_type IN (2, 4) AND level != 3 AND add_on = 0'
                ' ORDER BY series_id, display_order')
    rows = cur.fetchall()
    con.close()

    for sid, group in groupby(rows, lambda x: x[2]):
        serie = Series(None, names.get(sid))
        series.add(serie)
        for index, row in enumerate(group, start=1):
            uid = row[1][4:]
            title = row[4]
            if title.startswith('BOOK☆WALKER Exclusive: '):
                continue
            link = get_link(uid, title)
            title = title.removesuffix(' [Dramatized Adaptation]')
            publisher = labels.get(row[5])
            if not publisher:
                if publisher is None:
                    warnings.warn(f'Unknown publisher: {row[5]}', RuntimeWarning)
                continue
            format = get_format(row[3])
            if not format:
                continue
            isbn = isbns.get(row[0], '')
            date = datetime.date.fromisoformat(row[6][:10])
            uids[uid] = Info(serie.key, link, NAME, publisher, title, index, format, isbn, date)

    return series, set(uids.values())


def scrape(series: set[Series], info: set[Info]) -> tuple[set[Series], set[Info]]:
    return scrape_full(series, info)
