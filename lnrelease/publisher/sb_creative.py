from utils import Book, Info, Series

from . import check, guess, standard

NAME = 'SB Creative'


def parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    size = len(info)
    books: list[Book] = [None] * size

    standard(series, info, books)
    guess(series, info, books)
    check(series, info, books)
    return books
