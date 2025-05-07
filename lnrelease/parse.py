import importlib
import warnings
from collections import defaultdict
from collections.abc import Callable
from itertools import groupby
from operator import attrgetter
from pathlib import Path

import publisher
from scrape import INFO, SERIES
from utils import FORMATS, PRIMARY, SECONDARY, SOURCES, Book, Format, Info, Series, Table

PUBLISHERS = {}
for file in Path('lnrelease/publisher').glob('*.py'):
    module = importlib.import_module(f'publisher.{file.stem}')
    PUBLISHERS[module.NAME] = module

BOOKS = Path('books.csv')


def main() -> None:
    series = {row.key: row for row in Table(SERIES, Series)}
    info = Table(INFO, Info)
    links: defaultdict[str, list[Info]] = defaultdict(list)
    lst: list[Info] = []
    for i in info:
        links[i.link].append(i)
        if ((i.source not in SECONDARY or i.publisher not in PRIMARY)
            or (i.source == 'BOOK☆WALKER'
                and i.publisher == 'J-Novel Club'
                and i.format == 'Audiobook')):
            lst.append(i)
    lst.sort()
    # sort by source then title
    links = dict(sorted(links.items(), key=lambda x: (SOURCES[x[1][0].source], x[1][0].title)))
    BOOKS.unlink(missing_ok=True)
    books = Table(BOOKS, Book)

    for key, group in groupby(lst, attrgetter('serieskey', 'publisher')):
        serieskey = key[0]
        serie = series[serieskey]
        pub = key[1]
        if pub in PUBLISHERS:
            module = PUBLISHERS[pub]
        else:
            module = publisher
            warnings.warn(f'Unknown publisher: {pub}; {serieskey}', RuntimeWarning)
        inf: defaultdict[str, list[Info]] = defaultdict(list)
        for i in group:
            inf[i.format].append(i)
        inf = dict(sorted(inf.items(), key=lambda x: FORMATS.get(x[0], 0)))
        for x in module.parse(serie, inf, links).values():
            books.update(x)

    def jnc_key(book: Book) -> tuple[str, str, str]:
        return book.name, book.volume, Format.from_str(book.format)
    jnc_keys = set()
    jnc_isbns = set()
    jnc_series = set()
    for book in books:
        if book.publisher == 'J-Novel Club':
            jnc_keys.add(jnc_key(book))
            jnc_isbns.add(book.isbn)
            jnc_series.add(book.serieskey)
    books -= {b for b in books
              if b.publisher == 'Yen Press'
              and ((b.isbn in jnc_isbns or jnc_key(b) in jnc_keys)
                   or ' Omnibus ' in b.name and b.serieskey in jnc_series)}

    books.save()


if __name__ == '__main__':
    main()
