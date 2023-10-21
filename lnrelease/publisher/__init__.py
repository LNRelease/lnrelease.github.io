import datetime
import re
import warnings
from collections import Counter, defaultdict
from difflib import get_close_matches
from itertools import chain
from operator import attrgetter

from utils import EPOCH, SOURCES, Book, Info, Series

NAME = 'misc'

PARSE = re.compile(r'(?P<name>.+?)(?:,|:| -)? +(?:Vol\.|\(?Volume|\(Light Novel) *(?P<volume>\d+(?:\.\d)?)\)?(?:\s*:.+)?')
OMNIBUS = re.compile(r'.+(?:Vol\.|\(?Volume) *(?P<volume>\d+-\d+)\)?')
PART = re.compile(r'(?P<name>.+?):? Volume (?P<volume>\d+(?:\.5)?) (?P<part>.+)')
NUMBER = re.compile(r'\b(?P<volume>\d+(?:\.\d)?)\b(?:: .+)?')
SHORT = re.compile(r'\s*#?(?P<volume>\w{1,2})')
SOURCE = re.compile(r'(?P<volume>\d+(?:\.\d)?[^\s:\)]*):? ?.*')
URL = re.compile(r'-volume-(?P<volume>\d+)')

# number converter for volume parsing
NUM_DICT = {
    re.compile(r'\bzero\b', flags=re.IGNORECASE): '0',
    re.compile(r'\b(first|one|i)\b', flags=re.IGNORECASE): '1',
    re.compile(r'\b(second|two|ii)\b', flags=re.IGNORECASE): '2',
    re.compile(r'\b(third|three|iii)\b', flags=re.IGNORECASE): '3',
    re.compile(r'\b(fourth|four|iv)\b', flags=re.IGNORECASE): '4',
    re.compile(r'\b(fifth|five|v)\b', flags=re.IGNORECASE): '5',
}


def sub_nums(s: str) -> str:
    for pat, repl in NUM_DICT.items():
        s = pat.sub(repl, s)
    return s


def diff_list(titles: list[str]) -> list[str]:
    # returns list from when strings start to differ
    s1 = min(titles)
    s2 = max(titles)
    for i in range(len(s1)):
        if s1[i] != s2[i]:
            break
    else:
        i += 1
    return [t[i:] for t in titles]


def dates(info: dict[str, list[Info]], links: dict[str, list[Info]]) -> bool:
    changed = False
    for lst in info.values():
        for inf in lst:
            if inf.date != EPOCH:
                continue

            dates: Counter[str] = Counter()
            for link in inf.alts:
                for alt in links.get(link, ()):
                    dates[alt.date] += 1
            if date := dates.most_common(1):
                inf.date = date[0][0]
                changed = True
            else:
                warnings.warn(f'No dates found for {inf.title} ({inf.format})', RuntimeWarning)
    return changed


def copy(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # apply volume in longest format to others
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    main_diff = diff_list([i.title for i in main_info])
    poss = {d: b for d, b in zip(main_diff, main_books) if b}
    titles = {inf.title: book for inf, book in zip(main_info, main_books)}

    for key, lst in books.items():
        # single volume
        if len(lst) == 1 and not lst[0]:
            inf = info[key][0]
            lst[0] = Book(series.key, inf.link, inf.publisher, inf.title, '1', inf.format, inf.isbn, inf.date)
            continue

        # find close match
        diff = diff_list([i.title for i in info[key]])
        for i, (inf, book) in enumerate(zip(info[key], lst)):
            if book:
                continue

            if inf.title in titles:
                book = titles[inf.title]
            elif match := get_close_matches(diff[i], poss, n=1, cutoff=0.95):
                book = poss[match[0]]
            else:
                continue
            lst[i] = Book(series.key, inf.link, inf.publisher, book.name, book.volume, inf.format, inf.isbn, inf.date)
            changed = True

        # assume same order
        if all(x is None for x in lst) and len(lst) == len(main_books):
            for i, (inf, book) in enumerate(zip(info[key], main_books)):
                lst[i] = Book(series.key, inf.link, inf.publisher, book.name, book.volume, inf.format, inf.isbn, inf.date)

    return changed


def standard(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # simple parsing
    changed = False
    for key, lst in info.items():
        for i, inf in enumerate(lst):
            if match := PARSE.fullmatch(inf.title):
                name = match.group('name')
                vol = match.group('volume')
            elif i == 0 and series.title == inf.title:
                name = inf.title
                vol = '1'
            else:
                continue
            books[key][i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def omnibus(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # omnibus voluems
    changed = False
    for key, lst in info.items():
        for i, inf in enumerate(lst):
            if match := OMNIBUS.fullmatch(inf.title):
                name = series.title
                vol = match.group('volume')
                books[key][i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
                changed = True
    return changed


def one(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # assume remaining volumes are individual
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)

    for i, (inf, book) in enumerate(zip(main_info, main_books)):
        if book:
            continue

        name = inf.title
        vol = '1'
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def _guess(series: Series, info: list[Info], books: list[Book]) -> bool:
    # guess volume by looking at previous
    changed = False
    for i, (inf, book) in enumerate(zip(info, books)):
        if book:
            continue

        if i == 0:
            vol = '1'
        else:
            vol = str(int(float(books[i-1].volume)) + 1)
            if i+1 < len(books) and (b := books[i+1]) and float(vol) >= float(b.volume):
                warnings.warn(f'Volume parsing error: {inf.title}', RuntimeWarning)
        books[i] = Book(series.key, inf.link, inf.publisher, inf.title, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def guess(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # guess volume by looking at previous
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    return _guess(series, main_info, main_books)


def short(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # finds short string that looks right
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    diff = diff_list([sub_nums(i.title) for i in main_info])

    for i, (inf, book) in enumerate(zip(main_info, main_books)):
        if book:
            continue

        match = NUMBER.fullmatch(diff[i]) or SHORT.fullmatch(diff[i])
        if not match:
            continue
        name = series.title
        vol = match.group('volume')
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def part(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # multipart volumes
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)

    for i, (inf, book) in enumerate(zip(main_info, main_books)):
        if book:
            continue

        if match := PART.fullmatch(inf.title):
            name = match.group('name')
            vol = match.group('volume')
            part = sub_nums(match.group('part'))
            if match := NUMBER.search(part):
                vol += f'.{match.group("volume")}'
        else:
            name = inf.title
            vol = '1'
            warnings.warn(f'Part volume parsing error: {inf.title}', RuntimeWarning)
        main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
        changed = True
    return changed


def url(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # searches url for volume
    changed = False
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)

    for i, (inf, book) in enumerate(zip(main_info, main_books)):
        if book:
            continue

        if match := URL.search(inf.link):
            name = inf.title
            vol = match.group('volume')
            main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    return changed


def secondary(series: Series, info: dict[str, list[Info]],
              links: dict[str, list[Info]], books: dict[str, list[Book]]) -> bool:
    # check secondary sources
    changed = False
    sources: defaultdict[str, list[Info]] = defaultdict(list)
    for inf in chain.from_iterable(links.values()):
        if inf.serieskey == series.key:
            sources[inf.source].append(inf)
    if not sources:
        return False
    sources = dict(sorted(sources.items(), key=lambda x: SOURCES[x[0]]))

    poss: dict[str, dict[str, Info]] = {}
    for source, lst in sources.items():
        diff = diff_list([i.title for i in lst])
        poss[source] = {x: i for x, i in zip(diff, lst)}
    today = datetime.date.today()
    cutoff = today.replace(year=today.year-5)

    # replace index if unset
    for value in info.values():
        diff = diff_list([i.title for i in value])
        for dif, inf in zip(diff, value):
            if inf.index == 0:
                indices: Counter[int] = Counter()
                for source, pos in poss.items():
                    if ((close := get_close_matches(dif, pos, n=1, cutoff=0.01))
                            and (p := pos[close[0]]) and p.index != 0):
                        indices[p.index] += 1 + (inf.format == p.format) + (inf.publisher == p.publisher)
                if index := indices.most_common(1):
                    inf.index = index[0][0]

        # trust index if old series and multiple with same date
        if (len({inf.date for inf in value}) != len(value)
                and all(inf.date < cutoff for inf in value)):
            value.sort(key=attrgetter('publisher', 'source', 'index'))
        else:  # index unreliable for current series
            value.sort()

    # find volume in sources
    main_info = max(info.values(), key=len)
    main_books = max(books.values(), key=len)
    diff = diff_list([i.title for i in main_info])

    for i, (dif, inf) in enumerate(zip(diff, main_info)):
        volumes: Counter[str] = Counter()
        for source, pos in poss.items():
            if ((close := get_close_matches(dif, pos, n=1, cutoff=0.01))
                    and (match := SOURCE.fullmatch(close[0]))):
                p = pos[close[0]]
                vol = match.group('volume')
                volumes[vol] += 1 + (inf.format == p.format) + (inf.publisher == p.publisher)
        if volume := volumes.most_common(1):
            name = series.title
            vol = volume[0][0]
            main_books[i] = Book(series.key, inf.link, inf.publisher, name, vol, inf.format, inf.isbn, inf.date)
            changed = True
    dupes(main_books)

    return changed


def dupes(books: list[Book]) -> bool:
    # assume consecutive dupes are multipart
    changed = False
    start = 0
    end = 1
    while end < len(books):
        end += 1
        dupe = False
        while end < len(books) and books[start] == books[end]:
            end += 1
            if books[start] is not None:
                dupe = True
                changed = True
        if dupe:
            part = 0
            for i in range(start, end):
                part += 1
                books[i].volume += f'.{part}'
        start = end
    return changed


def check(series: Series, info: dict[str, list[Info]], books: dict[str, list[Book]]) -> list[Book]:
    # check for errors
    for key, lst in books.items():
        if _guess(series, info[key], lst):
            warnings.warn(f'None volume found: {series.title}', RuntimeWarning)
        if len(set(lst)) != len(lst):
            dupes(lst)
            warnings.warn(f'Duplicate volume found: {series.title}', RuntimeWarning)
    return books


def parse(series: Series, info: dict[str, list[Info]],
          links: dict[str, list[Info]]) -> dict[str, list[Book]]:
    books: dict[str, list[Book]] = {}
    for format, lst in info.items():
        books[format] = [None] * len(lst)

    standard(series, info, books)
    guess(series, info, books)
    copy(series, info, books)
    check(series, info, books)
    return books
