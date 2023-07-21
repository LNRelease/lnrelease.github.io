import importlib
import warnings
from collections import defaultdict
from itertools import groupby
from operator import attrgetter
from pathlib import Path

import publisher
from scrape import INFO, SERIES
from utils import FORMATS, Book, Info, Series, Table

PUBLISHERS = {}
for file in Path('lnrelease/publisher').glob('*.py'):
    module = importlib.import_module(f'publisher.{file.stem}')
    PUBLISHERS[module.NAME] = module
PRIMARY = {'J-Novel Club', 'Kodansha', 'Seven Seas Entertainment', 'VIZ Media', 'Yen Press'}
SECONDARY = {'BOOK☆WALKER', 'Right Stuf'}
BOOKS = Path('books.csv')


def main():
    series = {row.key: row for row in Table(SERIES, Series)}
    info = Table(INFO, Info)
    for row in info:
        if row.publisher == 'Yen On':
            row.publisher = 'Yen Press'
    alts = {i for i in info if i.source in SECONDARY and i.publisher in PRIMARY}
    info.difference_update(alts)

    BOOKS.unlink(missing_ok=True)
    books = Table(BOOKS, Book)
    for key, group in groupby(sorted(info), attrgetter('serieskey', 'publisher')):
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
        inf = dict(sorted(inf.items(), key=lambda x: FORMATS[x[0]]))
        for x in module.parse(serie, inf, alts).values():
            books.update(x)
    books.save()


if __name__ == '__main__':
    main()
