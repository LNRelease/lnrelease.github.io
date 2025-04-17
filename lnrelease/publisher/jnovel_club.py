import datetime
import re
import warnings
from collections import Counter, defaultdict
from itertools import chain, pairwise
from math import prod

from utils import Book, Info, Series

from . import check, copy, guess, letters, one, part, secondary, short, standard

NAME = 'J-Novel Club'

OMNIBUS = re.compile(r'(?P<name>.+?)(?:Collector\'s Edition )?(?:Omnibus )?:? Volume (?P<start>\d+(?:\.\d)?)-(?P<end>\d+(?:\.\d)?)')


def _parse(series: Series, info: dict[str, list[Info]],
           links: dict[str, list[Info]]) -> dict[str, list[Book]]:
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
        secondary(series, info, links, books)
        short(series, info, books)
        guess(series, info, books)

    letters(main_info, main_books)
    copy(series, info, books)
    check(series, info, books)
    return books


def geomean(dates: list[datetime.date]) -> float:
    return prod(max((b - a).days, 0.1) for a, b in
                pairwise(dates)) ** (1 / (len(dates) - 1))


def group_matches(digitals: dict[str, str], physicals: list[Book], matches: dict[re.Match, Info]) -> list[Book]:
    i = 0
    for match, inf in matches.items():
        start = match.group('start')
        end = match.group('end')
        first = True
        while i < len(physicals):
            book = physicals[i]
            if float(book.volume) > float(end):
                break
            elif float(book.volume) < float(start):
                i += 1
            elif first:  # set first
                book.volume = f'{start}-{end}'
                book.link = digitals[start]
                book.isbn = inf.isbn
                first = False
                i += 1
            else:  # delete others
                del physicals[i]

    # try to group remaining
    if i < len(physicals):
        physicals[i:] = group(physicals[i:])
    return physicals


def should_group(books: list[Book]) -> bool:
    i = 2
    date = datetime.date.min
    for book in books:
        if date == book.date:
            i += 1
        elif i == 1:  # singular volume, not omnibus
            return False
        elif i == 2:  # continue checking
            i = 1
            date = book.date
        elif i >= 3:  # 3+ assume omnibus
            break
    return True


def group(books: list[Book]) -> list[Book]:
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
            if book.date != next_book.date:
                break
            last = next_book.volume
            book.volume = f'{first}-{last}'
            del books[i]
    return books


def omnibus(series: Series, books: dict[str, list[Book]], links: dict[str, list[Info]]) -> list[Book]:
    # split into subseries
    physicals: defaultdict[str, list[Book]] = defaultdict(list)
    for book in books['Physical']:
        try:
            float(book.volume)
            physicals[book.name].append(book)
        except ValueError:
            physicals[''].append(book)

    # take omnibus from other sources
    matches: defaultdict[str, dict[re.Match, Info]] = defaultdict(dict)
    for inf in chain.from_iterable(links.values()):
        if (series.key.startswith(inf.serieskey)
                and (match := OMNIBUS.fullmatch(inf.title))):
            name = match.group('name')
            matches[name][match] = inf

    for name, lst in physicals.items():
        if not name or len(lst) == 1:
            continue

        match = sorted(matches.get(name, {}).items(),
                       key=lambda x: float(x[0].group('start')))
        match = dict({float(x[0].group('start')): x for x in match}.values())
        digitals = {b.volume: b.link for b in books['Digital'] if b.name == name}
        lst.sort(key=lambda x: float(x.volume))
        if match:
            group_matches(digitals, lst, match)
        elif should_group(lst):
            group(lst)

    return [book for x in physicals.values() for book in x]


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    books = _parse(series, info, links)
    if 'Physical' in books:
        books['Physical'] = omnibus(series, books, links)
    return books
