import importlib
import warnings
from itertools import groupby
from operator import attrgetter
from pathlib import Path

import publisher
from scrape import INFO, SERIES
from utils import Book, Info, Series, Table

PUBLISHERS = {}
for file in Path('lnrelease/publisher').glob('*.py'):
    module = importlib.import_module(f'publisher.{file.stem}')
    PUBLISHERS[module.NAME] = module
PRIMARY = {'J-Novel Club', 'Seven Seas Entertainment', 'Yen Press', 'Yen On'}
SECONDARY = {'BOOK☆WALKER'}
BOOKS = Path('books.csv')


def main():
    series = {row.key: row for row in Table(SERIES, Series).rows}
    info = Table(INFO, Info).rows
    for row in info:
        if row.publisher == 'Yen On':
            row.publisher == 'Yen Press'
    alts = {i for i in info if i.source in SECONDARY and i.publisher in PRIMARY}
    info.difference_update(alts)

    BOOKS.unlink(missing_ok=True)
    books = Table(BOOKS, Book)
    for key, group in groupby(sorted(info), attrgetter('serieskey', 'publisher', 'format')):
        serieskey = key[0]
        serie = series[serieskey]
        pub = key[1]
        if pub in PUBLISHERS:
            module = PUBLISHERS[pub]
        else:
            module = publisher
            warnings.warn(f'Unknown publisher: {pub}; {serieskey}', RuntimeWarning)
        inf = sorted(group, key=attrgetter('date', 'title'))
        books.update(module.parse(serie, inf, alts))
    books.save()


if __name__ == '__main__':
    main()
