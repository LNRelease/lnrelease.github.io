import re
from collections import Counter

from utils import Book, Info, Series

from . import check

NAME = 'Kodansha'

PARSE = re.compile(r'(?P<name>.+?),? (Volume |Part |part |)(?P<volume>\d+)')
BRACKET = re.compile(r'(?P<name>.+?)(?: \(.+?\))?')


def parse(series: Series, info: list[Info], alts: set[Info]) -> list[Book]:
    size = len(info)
    books: list[Book] = [None] * size
    names: Counter[str] = Counter()
    numbered = False

    for i, inf in enumerate(info):
        if match := PARSE.fullmatch(inf.title):
            name = match.group('name')
            vol = match.group('volume')
            numbered = True
        elif size == 1:
            name = inf.title
            vol = '1'
        elif numbered:  # monogatari
            name = inf.title
            key = BRACKET.fullmatch(inf.title).group('name')
            names[key] += 1
            vol = str(names[key])
        else:
            name = inf.title
            vol = str(i)
        books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)

    check(series, info, books)
    return books
