import datetime
import re
from itertools import chain

from utils import Book, Info, Series

from . import check, copy, guess, omnibus, one, secondary, short, standard

NAME = 'Seven Seas Entertainment'

OMNIBUS = re.compile(r'\d+-\d+')


def _parse(series: Series, info: dict[str, list[Info]],
           links: dict[str, list[Info]], main: bool = False) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    size = len(main_info)

    standard(series, info, books)
    omnibus(series, info, books)
    short(series, info, books)
    if not main or main_books.count(None) < size - 1:
        one(series, info, books)
    else:
        secondary(series, info, links, books)
        guess(series, info, books)
    copy(series, info, books)
    for format, lst in books.items():
        if lst.count(None) == 1 and 'Vol.' not in info[format][lst.index(None)].title:
            one(series, {format: info[format]}, {format: lst})
    return books


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    today = datetime.date.today()
    alts = []
    for inf in chain.from_iterable(links.values()):
        if (inf.serieskey == series.key
            and inf.source != NAME
            and inf.publisher == NAME
                and inf.format == 'Digital'):
            alts.append(inf)
    if not alts and 'Digital' not in info and all(inf.date > today for inf in info['Physical']):
        info['Digital'] = []
        for inf in info['Physical']:
            i = Info(series.key, inf.link, inf.source, NAME, inf.title, inf.index, 'Digital', '', inf.date)
            info['Digital'].append(i)

    books = _parse(series, info, links, True)
    if alts:
        info.setdefault('Digital', [])
        digitals = {(book.name, book.volume): book for book in books.setdefault('Digital', [])}
        alt_books = {(book.name, book.volume): book for book in _parse(series, {'': alts}, links)['']}
        for physical in books['Physical']:
            digital = digitals.get((physical.name, physical.volume))
            if alt := alt_books.get((physical.name, physical.volume)):
                if digital:
                    if alt.date < digital.date == physical.date:
                        digital.date = alt.date
                else:
                    date = min(alt.date, physical.date)
                    new = Book(series.key, physical.link, NAME, alt.name, alt.volume, 'Digital', alt.isbn, date)
                    books['Digital'].append(new)
            elif not digital and not OMNIBUS.fullmatch(physical.volume):
                new = Book(series.key, physical.link, NAME, physical.name, physical.volume, 'Digital', '', physical.date)
                books['Digital'].append(new)
        for key, physical in alt_books.items():
            if digital := digitals.get(key):
                digital.isbn = digital.isbn or physical.isbn

    check(series, info, books)
    return books
