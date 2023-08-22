import datetime
import re
from collections import Counter

from utils import Book, Info, Series, SOURCES

from . import check, copy

NAME = 'Kodansha'

PARSE = re.compile(r'(?P<name>.+?),? (Volume |vol |Part |part |)(?P<volume>\d+)')
BRACKET = re.compile(r'(?P<name>.+?)(?: \(.+?\))?')


def parse(series: Series, info: dict[str, list[Info]], alts: set[Info]) -> dict[str, list[Book]]:
    today = datetime.date.today()
    isbns = {inf.isbn for lst in info.values() for inf in lst}
    for alt in sorted(alts, key=lambda x: (SOURCES.get(x.source, 0), x.title)):
        if (alt.serieskey == series.key
            and alt.publisher == NAME
            and alt.isbn
            and alt.isbn not in isbns
                and alt.date > today):
            i = Info(series.key, alt.link, alt.source, NAME, alt.title, 0, alt.format, alt.isbn, alt.date)
            info[alt.format].append(i)
            isbns.add(i.isbn)

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
