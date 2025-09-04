import datetime
from itertools import chain

from utils import Book, Info, Series

from . import check, copy, guess, omnibus, one, secondary, short, standard

NAME = 'Seven Seas Entertainment'


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    today = datetime.date.today()
    if 'Digital' not in info and (
            all(inf.date > today for inf in info['Physical'])
            or any(inf.serieskey == series.key and inf.publisher == NAME and inf.format == 'Digital'
                   for inf in chain.from_iterable(links.values()))):
        # copy physical dates if digital releases found elsewhere
        info['Digital'] = []
        for inf in info['Physical']:
            i = Info(series.key, inf.link, inf.source, NAME, inf.title, inf.index, 'Digital', '', inf.date)
            info['Digital'].append(i)

    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    size = len(main_info)

    standard(series, info, books)
    omnibus(series, info, books)
    short(series, info, books)
    if main_books.count(None) < size - 1:
        one(series, info, books)
    else:
        secondary(series, info, links, books)
        guess(series, info, books)
    copy(series, info, books)
    for format, lst in books.items():
        if lst.count(None) == 1 and 'Vol.' not in info[format][lst.index(None)].title:
            one(series, {format: info[format]}, {format: lst})
    check(series, info, books)
    return books
