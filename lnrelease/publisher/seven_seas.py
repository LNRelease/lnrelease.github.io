from utils import Book, Info, Series

from . import bookwalker, check, guess, omnibus, one, short, standard

NAME = 'Seven Seas Entertainment'


def parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    size = len(info)
    books: list[Book] = [None] * size

    standard(series, info, books)
    omnibus(series, info, books)
    short(series, info, books)
    if books.count(None) < size:
        one(series, info, books)
    else:
        bookwalker(series, info, alts, books)
        guess(series, info, books)
    check(series, info, books)
    return books
