from dataclasses import replace
from itertools import chain

from utils import DIGITAL, Book, Info, Series

from . import check, copy, dates, guess, standard

NAME = 'TOKYOPOP'


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    digitals: dict[str, Info] = {}
    fisbns = {f: {inf.isbn for inf in lst} for f, lst in info.items()}
    fdates = {f: {inf.date for inf in lst} for f, lst in info.items()}
    for inf in chain.from_iterable(links.values()):
        if inf.serieskey == series.key and inf.publisher == NAME and inf.isbn:
            if 'Digital' not in info and inf.format in DIGITAL:
                digitals[inf.title] = replace(inf, format='Digital')
            elif inf.isbn not in fisbns.get(inf.format, ()) and inf.date not in fdates.get(inf.format, ()):
                info[inf.format].append(replace(inf, index=0))
                fisbns[inf.format].add(inf.isbn)
    if digitals:
        info['Digital'] = []
        for inf in info['Paperback']:
            info['Digital'].append(digitals.get(inf.title) or
                                   replace(inf, format='Digital', isbn=''))

    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)

    standard(series, info, books)
    guess(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
