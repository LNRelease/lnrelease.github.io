import datetime
import re

from utils import Book, Format, Info, Series

from . import bookwalker, check, guess, one, part, short, standard

NAME = 'J-Novel Club'

BOOKWALKER = re.compile(r'(?P<volume>\d+\.?5?[^\s:\)]*)(?:: )?(?P<title>.+)?')


def _parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    size = len(info)
    books: list[Book] = [None] * size

    standard(series, info, books)
    todo = [i for i, book in enumerate(books) if not book]
    if len(todo) == 0:  # done
        pass
    elif all(' Volume ' in info[i].title for i in todo):  # multipart volume
        part(series, info, books)
    elif len(todo) < size:  # probably short stories
        one(series, info, books)
    else:  # special volume name
        bookwalker(series, info, alts, books)
        short(series, info, books)
        guess(series, info, books)

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


def parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    books = _parse(series, info, alts)
    if books[0].format == Format.PHYSICAL:
        omnibus(books)
    return books
