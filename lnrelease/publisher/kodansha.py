import re
from collections import Counter

from utils import Book, Info, Series

from . import check, copy

NAME = 'Kodansha'

PARSE = re.compile(r'(?P<name>.+?),? (Volume |Part |part |)(?P<volume>\d+)')
BRACKET = re.compile(r'(?P<name>.+?)(?: \(.+?\))?')


def parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)
    names: Counter[str] = Counter()

    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    size = len(main_info)
    numbered = False

    for i, inf in enumerate(main_info):
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
            vol = str(i + 1)
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)

    copy(series, info, books)
    check(series, info, books)
    return books
