from utils import Book, Info, Series

from . import check, one, standard, url

NAME = 'VIZ Media'


def parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    size = len(info)
    books: list[Book] = [None] * size

    standard(series, info, books)
    url(series, info, books)
    one(series, info, books)
    check(series, info, books)
    return books
