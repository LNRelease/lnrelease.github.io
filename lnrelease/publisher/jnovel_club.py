import datetime
import re

from utils import Book, Info, Series

from . import check, copy, guess, one, part, secondary, short, standard

NAME = 'J-Novel Club'

BOOKWALKER = re.compile(r'(?P<volume>\d+\.?5?[^\s:\)]*)(?:: )?(?P<title>.+)?')


def _parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    size = len(main_info)

    standard(series, info, books)
    todo = [i for i, book in enumerate(main_books) if not book]
    if len(todo) == 0:  # done
        pass
    elif all(' Volume ' in main_info[i].title for i in todo):  # multipart volume
        part(series, info, books)
    elif len(todo) < size - 1:  # probably short stories
        one(series, info, books)
    else:  # special volume name
        secondary(series, info, alts, books)
        short(series, info, books)
        guess(series, info, books)

    copy(series, info, books)
    check(series, info, books)
    return books


def omnibus(books: list[Book]) -> list[Book]:
    # assume omnibus if 3+ releases on the same date or all in pairs
    books.sort(key=lambda x: (x.name, float(x.volume)))
    i = 2
    date = datetime.date.min
    for book in books:
        if date == book.date:
            i += 1
        elif i == 1:  # singular volume not omnibus
            return books
        elif i == 2:  # continue checking
            i = 1
            date = book.date
        elif i >= 3:  # 3+ assume omnibus
            break

    # group volumes
    i = 0
    while i < len(books):
        book = books[i]
        volume = book.volume
        first = volume
        last = ''
        i += 1
        while i < len(books):
            next_book = books[i]
            if book.name != next_book.name or book.date != next_book.date:
                break
            last = next_book.volume
            book.volume = f'{first}-{last}'
            books.remove(next_book)
    return books


def parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    books = _parse(series, info, alts)
    if 'Physical' in books:
        omnibus(books['Physical'])
    return books
