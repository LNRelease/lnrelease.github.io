from utils import Book, Info, Series

from . import check, copy, one, standard

NAME = 'Square Enix Books'


def parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)

    standard(series, info, books)
    one(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
