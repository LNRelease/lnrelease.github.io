import importlib
import warnings
from collections import defaultdict
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from typing import Callable

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
    for i in info:
        links[i.link].append(i)
    # sort by source then title
    links = dict(sorted(links.items(), key=lambda x: (SOURCES[x[1][0].source], x[1][0].title)))

    BOOKS.unlink(missing_ok=True)
    books = Table(BOOKS, Book)
    info = [i for i in info if i.source not in SECONDARY or i.publisher not in PRIMARY]
    info.sort()

    for key, group in groupby(info, attrgetter('serieskey', 'publisher')):
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

    jnc_key: Callable[[Book], tuple] = lambda b: (b.name, b.volume, Format.from_str(b.format))
    jnc = {jnc_key(b): b for b in books if b.publisher == 'J-Novel Club'}
    books -= {b for b in books if b.publisher == 'Yen Press' and jnc.get(jnc_key(b))}

    books.save()


if __name__ == '__main__':
    main()
