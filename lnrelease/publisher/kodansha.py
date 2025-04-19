import datetime
import re
from collections import Counter
from itertools import chain

from utils import FORMATS, Book, Info, Series

from . import check, copy, dates

NAME = 'Kodansha'

PARSE = re.compile(rf'(?P<name>.+?),? (?:[Vv]ol(?:ume)? |[Pp]art |\((?:{"|".join(FORMATS)})\) )?(?P<volume>\d+)(?:\s*[:–\-\(].+)?')
BRACKET = re.compile(r'(?P<name>.+?)(?: \(.+?\))?')


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    today = datetime.date.today()
    fisbns = {f: {inf.isbn for inf in lst} for f, lst in info.items()}
    fdates = {f: {inf.date for inf in lst} for f, lst in info.items()}
    for inf in chain.from_iterable(links.values()):
        if (inf.serieskey == series.key
            and inf.publisher == NAME
            and inf.isbn
            and (isbns := fisbns.get(inf.format))
            and inf.isbn not in isbns
            and inf.date > today
                and (d := fdates.get(inf.format)) and inf.date not in d):
            i = Info(series.key, inf.link, inf.source, NAME, inf.title, 0, inf.format, inf.isbn, inf.date)
            info[inf.format].append(i)
            isbns.add(i.isbn)
    dates(info, links)

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
